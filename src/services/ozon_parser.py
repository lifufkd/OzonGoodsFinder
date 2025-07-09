import asyncio
from loguru import logger
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from src.schemas.categories import Catalog, CatalogWithProducts, CatalogWithFullProducts, CatalogWithDBProducts
from src.schemas.products import Product, FullProduct, ExistedProduct
from src.repositories.products import ProductsRepository
from src.core.orm_to_dto import many_sqlalchemy_to_pydantic, sqlalchemy_to_pydantic
from src.core.config import generic_settings
from src.parsers.ozon import OzonParser
from src.core.utils import chunk_generator
from src.core.proxy_manager import ProxyManager
from src.core.redis_client import redis_client
from src.core.logger import setup_logger
from src.schemas.enums import SourceTypes
from src.database.session import get_session


class OzonParserService:
    def __init__(self):
        self.browser = None

    def get_catalogs(self) -> list[Catalog]:
        result = []

        for category in generic_settings.CATEGORIES:
            tg_group_id = category.get('TG_GROUP_ID')
            for first_sub_category in category.get("SUB_CATEGORIES"):
                tg_topic_id = first_sub_category.get('TG_TOPIC_ID')
                for second_sub_category in first_sub_category.get("SUB_CATEGORIES"):
                    if second_sub_category.get("PARSE_SOURCE") != "OZON":
                        continue

                    result.append(
                        Catalog(
                            tg_group_id=tg_group_id,
                            tg_topic_id=tg_topic_id,
                            source_type=SourceTypes.OZON,
                            url=second_sub_category.get("URL")
                        )
                    )

        return result

    async def get_new_products_links(self, catalog: Catalog, timeout: int) -> CatalogWithProducts | None:
        ozon_parser = OzonParser(self.browser)
        products_urls = []
        catalog_with_products = None
        page = 1
        collected_products = 0

        try:
            while collected_products < generic_settings.MAX_PRODUCTS_FROM_CATEGORY:
                temp_products_urls = await ozon_parser.allocate_browser(ozon_parser.parse_products_urls, catalog.url, page, timeout)
                if not temp_products_urls:
                    break

                existed_urls = await self.get_products_by_urls_from_db(temp_products_urls)
                for product in existed_urls:
                    temp_products_urls.remove(product.url)

                collected_products += len(temp_products_urls)
                page += 1
                products_urls.append(temp_products_urls)

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
        existed_products_urls = None

        try:
            existed_products = await self.get_products_from_db()
            existed_products_urls = [product.url for product in existed_products]
        except Exception as e:
            logger.warning(f"Error getting all products from DB: {e}")

        try:
            if existed_products_urls is not None:
                raw_product = await ozon_parser.allocate_browser(
                    ozon_parser.parse_product,
                    product.url,
                    existed_products_urls,
                    timeout
                )
                result = FullProduct(
                    url=product.url,
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
            data = await asyncio.gather(*tasks)  # TODO: Отфильтровать по имеющимся в БД
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
                    source_type=catalog.source_type,
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

        return catalogs_with_db_products

    async def get_products_by_urls_from_db(self, urls: list[str]) -> list[ExistedProduct] | list:
        products = []

        try:
            async with get_session() as session:
                products_repository = ProductsRepository(session)
                data = await products_repository.get_by_urls(urls)
                products = await many_sqlalchemy_to_pydantic(
                    data,
                    ExistedProduct
                )
        except Exception as e:
            logger.error(f"Error getting products from DB: {e}")

        return products

    async def add_products_to_db(self, products: list[FullProduct]) -> list[ExistedProduct]:
        updated_products = []

        async with get_session() as session:
            try:
                products_repository = ProductsRepository(session)
                for product in products:
                    orm_product = await products_repository.add(product)
                    updated_products.append(
                        await sqlalchemy_to_pydantic(
                            orm_product,
                            ExistedProduct
                        )
                    )
            except Exception as e:
                logger.error(f"Error adding products to DB: {e}")
                await session.rollback()
            else:
                await session.commit()

        return updated_products

    async def get_new_products(self) -> list[CatalogWithDBProducts]:
        settings = generic_settings.BROWSER_SETTINGS
        catalogs = self.get_catalogs()

        logger.info(f"Starting updating products...")
        async with Stealth().use_async(async_playwright()) as session:

            logger.debug("Launching browser...")
            self.browser = await session.chromium.launch(headless=settings.get("HEADLESS"))
            logger.debug("Browser successfully launched!")

            logger.info(f"Starting parsing new products links from {len(catalogs)} catalogs...")
            catalogs_with_products = await self.get_catalogs_with_products(
                catalogs,
                settings.get("MAX_CONCURRENT_TABS"),
                settings.get("TIMEOUT")
            )
            logger.info(f"Products links parsed!")

            logger.info(f"Starting parsing new products...")
            catalogs_with_full_products = await self.get_catalogs_with_full_products(
                catalogs_with_products,
                settings.get("MAX_CONCURRENT_TABS"),
                settings.get("TIMEOUT")
            )
            logger.info(f"Products parsed!")

            logger.info(f"Starting saving new products to db...")
            catalogs_with_db_products = await self.save_products_to_db(catalogs_with_full_products)
            logger.info(f"Products saved!")

        logger.info(f"Products updated successfully finished!")

        return catalogs_with_db_products


async def update_products():
    setup_logger()
    logger.info("Starting update products")

    proxy_manager = ProxyManager(redis_client)
    await proxy_manager.init_proxies()
    ozon_parser = OzonParserService()

    new_products = await ozon_parser.get_new_products()


if __name__ == '__main__':
    asyncio.run(update_products())
