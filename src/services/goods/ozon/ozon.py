import asyncio
from loguru import logger
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from src.services.goods.ozon.telegram import OzonTelegramService
from src.services.goods.ozon.parser import OzonParserService
from src.repositories.products import ProductsRepository
from src.repositories.tg_messages import TgMessagesRepository
from src.uow.tg_bot_uow import TgBotUow
from src.services.utils import get_catalogs
from src.schemas.tg_messages import AddTgMessage
from src.schemas.products import FullProduct, DBProduct
from src.schemas.categories import (
    Catalog,
    CatalogWithProducts,
    CatalogWithFullProducts,
    CatalogWithTgProducts,
    CatalogWithDBProducts
)
from src.core.config import generic_settings
from src.core.utils import chunk_generator
from src.database.session import get_session
from src.core.orm_to_dto import sqlalchemy_to_pydantic


class OzonService:
    def __init__(self, tg_bot_uow: TgBotUow):
        self.tg_bot_uow = tg_bot_uow
        self.telegram_service = OzonTelegramService(tg_bot_uow)
        self.browser = None
        self.parser_service = None

    async def insert_tg_messages(self, catalog: CatalogWithTgProducts) -> None:
        async for session in get_session():
            try:
                tg_messages_repository = TgMessagesRepository(session)
                for product in catalog.products:
                    tg_message = AddTgMessage(
                        product_id=product.id,
                        tg_message_id=product.tg_message_id,
                        tg_group_id=catalog.tg_group_id,
                        tg_topic_id=catalog.tg_topic_id
                    )
                    await tg_messages_repository.add(tg_message)
            except Exception as e:
                logger.critical(f"Error insert tg message to DB: {e}")
                await session.rollback()
            else:
                await session.commit()

    async def insert_products(self, products: list[FullProduct]) -> list[DBProduct]:
        updated_products = []

        async for session in get_session():
            try:
                products_repository = ProductsRepository(session)
                for product in products:
                    orm_product = await products_repository.add(product)
                    updated_products.append(
                        await sqlalchemy_to_pydantic(
                            orm_product,
                            DBProduct
                        )
                    )
            except Exception as e:
                logger.error(f"Error insert products: {e}")
                await session.rollback()
            else:
                await session.commit()

        return updated_products

    async def insert_catalog(self, catalogs: CatalogWithFullProducts) -> CatalogWithDBProducts:
        catalog_with_db_products = None

        try:
            updated_products = await self.insert_products(catalogs.products)
            if updated_products:
                catalog_with_db_products = CatalogWithDBProducts(
                    products=updated_products,
                    **catalogs.model_dump(exclude={"products"})
                )
        except Exception as e:
            logger.critical(f"Error insert catalog: {e}")

        return catalog_with_db_products

    async def get_products_links(
            self,
            catalogs: list[Catalog],
            max_threads: int,
            timeout: int) -> list[CatalogWithProducts]:
        catalogs_with_products = []
        count = 0

        async for catalogs_chunk in chunk_generator(catalogs, max_threads):
            tasks = [asyncio.create_task(self.parser_service.get_products_links(catalog, timeout)) for catalog in catalogs_chunk]
            data = await asyncio.gather(*tasks)
            data = list(filter(None, data))  # Filter empty catalogs

            catalogs_with_products.extend(data)
            count += len(data)

        logger.debug(f"Parsed {count} products links from all categories")
        return catalogs_with_products

    async def process_products(self, catalogs_with_products: list[CatalogWithProducts], max_threads: int, timeout: int) -> None:

        catalog_full_product = None

        async def parse_full_products():
            data = []
            async for product_chunk in chunk_generator(catalog.products, max_threads):
                _tasks = [asyncio.create_task(self.parser_service.get_product(product, timeout)) for product in product_chunk]
                _full_products = await asyncio.gather(*_tasks)
                _full_products = list(filter(None, _full_products))

                data.extend(_full_products)

            return data

        for index, catalog in enumerate(catalogs_with_products):
            db_products = None

            if isinstance(catalog_full_product, list) and catalog_full_product:
                full_products = CatalogWithFullProducts(
                    tg_group_id=catalogs_with_products[index-1].tg_group_id,
                    tg_topic_id=catalogs_with_products[index-1].tg_topic_id,
                    url=catalogs_with_products[index-1].url,
                    products=catalog_full_product
                )

                db_products = await self.insert_catalog(full_products)
                catalog_full_product.clear()

            tasks = [asyncio.create_task(parse_full_products()), asyncio.create_task(self.telegram_service.send(db_products))]
            results = await asyncio.gather(*tasks)
            catalog_full_product = results[0]
            tg_products = results[1]
            if tg_products:
                await self.insert_tg_messages(tg_products)

        if isinstance(catalog_full_product, list) and catalog_full_product:
            full_products = CatalogWithFullProducts(
                tg_group_id=catalogs_with_products[-1].tg_group_id,
                tg_topic_id=catalogs_with_products[-1].tg_topic_id,
                url=catalogs_with_products[-1].url,
                products=catalog_full_product
            )

            db_products = await self.insert_catalog(full_products)
            tg_products = await self.telegram_service.send(db_products)
            if tg_products:
                await self.insert_tg_messages(tg_products)

    async def get_new_products(self):

        try:
            settings = generic_settings.BROWSER_SETTINGS

            logger.debug("Getting products catalogs from config...")
            catalogs = await get_catalogs(self.tg_bot_uow)
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
                self.parser_service = OzonParserService(self.browser)
                logger.debug("Browser successfully launched!")

                logger.info(f"Starting parsing new products links from {len(catalogs)} catalogs...")
                catalogs_with_products = await self.get_products_links(
                    catalogs,
                    settings.get("MAX_CONCURRENT_PARSING_TASKS"),
                    generic_settings.OZON_PARSER_SETTINGS.get("CATALOG_TIMEOUT")
                )
                logger.info(f"Products links parsed!")

                if catalogs_with_products:
                    logger.info(f"Starting processing products...")
                    await self.process_products(
                        catalogs_with_products,
                        settings.get("MAX_CONCURRENT_PARSING_TASKS"),
                        generic_settings.OZON_PARSER_SETTINGS.get("PRODUCT_TIMEOUT")
                    )
                    logger.info(f"Products processed!")

        except Exception as e:
            logger.critical(f"Error getting new products: {e}")
