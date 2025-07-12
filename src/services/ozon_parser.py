import asyncio
from loguru import logger
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from src.services.tg_bot import TgBotService
from src.services.utils import get_catalogs
from src.schemas.categories import Catalog, CatalogWithProducts, CatalogWithFullProducts, CatalogWithDBProducts
from src.schemas.products import Product, FullProduct, DBProduct
from src.repositories.products import ProductsRepository
from src.core.orm_to_dto import sqlalchemy_to_pydantic
from src.core.config import generic_settings
from src.parsers.ozon import OzonParser
from src.core.utils import chunk_generator
from src.schemas.enums import SourceTypes
from src.database.session import get_session


class OzonParserService:
    def __init__(self, tg_bot_service: TgBotService):
        self.tg_bot_service = tg_bot_service
        self.browser = None

    async def get_new_products_links(self, catalog: Catalog, timeout: int) -> CatalogWithProducts | None:
        ozon_parser = OzonParser(self.browser)
        products_urls = []
        catalog_with_products = None
        page = 1
        collected_products = 0

        try:
            existed_urls = await self.get_products_from_db()

            while collected_products < generic_settings.MAX_PRODUCTS_FROM_CATEGORY:
                temp_products_urls = await ozon_parser.allocate_browser(ozon_parser.parse_products_urls, catalog.url, page, timeout)
                if not temp_products_urls:
                    break

                for existed_url in existed_urls:
                    if existed_url not in temp_products_urls:
                        continue

                    temp_products_urls.remove(existed_url)

                page += 1
                collected_products += len(temp_products_urls)

                products_urls.extend(temp_products_urls)

            products = [Product(url=product_url) for product_url in products_urls[:generic_settings.MAX_PRODUCTS_FROM_CATEGORY]]
            catalog_with_products = CatalogWithProducts(
                products=products,
                **catalog.model_dump()
            )
        except Exception as e:
            logger.warning(f"Error parsing products links from catalog {catalog.url}: {e}")

        return catalog_with_products

    async def get_product(self, product: Product, timeout: int) -> FullProduct | None:
        ozon_parser = OzonParser(self.browser)
        result = None

        try:
            raw_product = await ozon_parser.allocate_browser(
                ozon_parser.parse_product,
                product.url,
                timeout
            )
            result = FullProduct(
                url=product.url,
                source_type=SourceTypes.OZON,
                **raw_product
            )
        except Exception as e:
            logger.warning(f"Error parsing product {product.url}: {e}")

        return result

    async def get_catalogs_with_products(
            self,
            catalogs: list[Catalog],
            max_threads: int,
            timeout: int) -> list[CatalogWithProducts]:
        catalogs_with_products = []
        count = 0

        async for catalogs_chunk in chunk_generator(catalogs, max_threads):
            tasks = [asyncio.create_task(self.get_new_products_links(catalog, timeout)) for catalog in catalogs_chunk]
            data = await asyncio.gather(*tasks)
            data = list(filter(None, data))  # Filter empty catalogs

            catalogs_with_products.extend(data)
            count += len(data)

        logger.debug(f"Parsed {count} products links from all categories")
        return catalogs_with_products

    async def get_catalogs_with_full_products(
            self,
            catalogs_with_products: list[CatalogWithProducts],
            max_threads: int,
            timeout: int) -> list[CatalogWithFullProducts]:
        catalogs_with_full_products = []
        count = 0

        for catalog in catalogs_with_products:
            catalog_full_product = []
            async for product_chunk in chunk_generator(catalog.products, max_threads):
                tasks = [asyncio.create_task(self.get_product(product, timeout)) for product in product_chunk]
                full_products = await asyncio.gather(*tasks)
                full_products = list(filter(None, full_products))

                catalog_full_product.extend(full_products)

            catalogs_with_full_products.append(
                CatalogWithFullProducts(
                    tg_group_id=catalog.tg_group_id,
                    tg_topic_id=catalog.tg_topic_id,
                    url=catalog.url,
                    products=catalog_full_product
                )
            )
            count += len(catalog_full_product)
            logger.debug(f"Parsed {len(catalog_full_product)} for catalog {catalog.url}")

        logger.debug(f"Parsed {count} products from all categories")
        return catalogs_with_full_products

    async def save_products_to_db(self, catalogs_with_full_products: list[CatalogWithFullProducts]) -> list[CatalogWithDBProducts]:
        catalogs_with_db_products = []

        try:
            for catalog in catalogs_with_full_products:
                updated_products = await self.add_products_to_db(catalog.products)
                if not updated_products:
                    continue

                catalogs_with_db_products.append(
                    CatalogWithDBProducts(
                        products=updated_products,
                        **catalog.model_dump(exclude={"products"})
                    )
                )
        except Exception as e:
            logger.critical(f"Error adding products to db: {e}")

        return catalogs_with_db_products

    async def get_products_from_db(self) -> list[str] | list:
        products = []

        try:
            async for session in get_session():
                products_repository = ProductsRepository(session)
                data = await products_repository.get_by_urls()
                products.extend(data)
        except Exception as e:
            logger.error(f"Error getting products from DB: {e}")

        return products

    async def add_products_to_db(self, products: list[FullProduct]) -> list[DBProduct]:
        updated_products = []

        async for session in get_session():
            try:
                products_repository = ProductsRepository(session)
                for product in products:
                    try:
                        orm_product = await products_repository.add(product)
                        updated_products.append(
                            await sqlalchemy_to_pydantic(
                                orm_product,
                                DBProduct
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Product is duplicated, skipping save to DB: {e}")
            except Exception as e:
                logger.error(f"Error adding products to DB: {e}")
                await session.rollback()
            else:
                await session.commit()

        return updated_products

    async def get_new_products(self) -> list[CatalogWithDBProducts]:
        catalogs_with_full_products = None
        catalogs_with_db_products = None

        try:
            settings = generic_settings.BROWSER_SETTINGS

            logger.debug("Getting products catalogs from config...")
            catalogs = await get_catalogs(self.tg_bot_service)
            logger.debug("Catalogs successfully retrieved!")

            async with Stealth().use_async(async_playwright()) as session:

                logger.debug("Launching browser...")
                self.browser = await session.chromium.launch(
                    headless=settings.get("HEADLESS"),
                    args=[
                        '--enable-webgl',
                        '--use-gl=swiftshader',
                        '--enable-accelerated-2d-canvas'
                    ]
                )
                logger.debug("Browser successfully launched!")

                logger.info(f"Starting parsing new products links from {len(catalogs)} catalogs...")
                catalogs_with_products = await self.get_catalogs_with_products(
                    catalogs,
                    settings.get("MAX_CONCURRENT_PARSING_TASKS"),
                    generic_settings.OZON_PARSER_SETTINGS.get("CATALOGS_TIMEOUT")
                )
                logger.info(f"Products links parsed!")

                if catalogs_with_products:
                    logger.info(f"Starting parsing new products...")
                    catalogs_with_full_products = await self.get_catalogs_with_full_products(
                        catalogs_with_products,
                        settings.get("MAX_CONCURRENT_PARSING_TASKS"),
                        generic_settings.OZON_PARSER_SETTINGS.get("PRODUCTS_TIMEOUT")
                    )
                    logger.info(f"Products parsed!")

            if catalogs_with_full_products:
                logger.info(f"Starting saving new products to db...")
                catalogs_with_db_products = await self.save_products_to_db(catalogs_with_full_products)
                logger.info(f"Products saved!")
        except Exception as e:
            logger.critical(f"Error getting new products: {e}")

        return catalogs_with_db_products
