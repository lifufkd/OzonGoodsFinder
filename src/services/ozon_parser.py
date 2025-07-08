import asyncio
from loguru import logger
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from src.schemas.categories import Catalog, CatalogWithProducts, CatalogWithFullProducts
from src.schemas.products import Product, FullProduct
from src.core.config import generic_settings
from src.parsers.ozon import OzonParser
from src.core.utils import chunk_generator
from src.core.proxy_manager import ProxyManager
from src.core.redis_client import redis_client
from src.core.logger import setup_logger


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
                    result.append(
                        Catalog(
                            tg_group_id=tg_group_id,
                            tg_topic_id=tg_topic_id,
                            ozon_url=second_sub_category.get("OZON_URL")
                        )
                    )

        return result

    async def get_new_products_links(self, catalog: Catalog, timeout: int) -> CatalogWithProducts | None:
        ozon_parser = OzonParser(self.browser)
        products_urls = await ozon_parser.allocate_browser(ozon_parser.parse_products_urls, catalog.ozon_url, timeout)
        products = [Product(ozon_url=product_url) for product_url in products_urls]

        if not products:
            return None

        return CatalogWithProducts(
            ozon_products=products,
            **catalog.model_dump()
        )

    async def get_products(self, catalog: CatalogWithProducts, timeout: int) -> CatalogWithFullProducts:
        result = []
        ozon_parser = OzonParser(self.browser)

        for product in catalog.ozon_products:
            raw_product = await ozon_parser.allocate_browser(ozon_parser.parse_product, product.ozon_url, timeout)
            logger.info(raw_product)
            try:
                result.append(
                    FullProduct(
                        ozon_url=product.ozon_url,
                        **raw_product
                    )
                )
            except Exception as e:
                logger.warning(f"Error converting product: {e}")

        catalog_with_full_products = CatalogWithFullProducts(
            tg_group_id=catalog.tg_group_id,
            tg_topic_id=catalog.tg_topic_id,
            ozon_url=catalog.ozon_url,
            ozon_products=result
        )
        return catalog_with_full_products

    async def get_new_products(self) -> list[CatalogWithFullProducts]:
        settings = generic_settings.BROWSER_SETTINGS
        catalogs = self.get_catalogs()

        async with Stealth().use_async(async_playwright()) as session:

            logger.debug("Launching browser...")
            self.browser = await session.chromium.launch(headless=settings.get("HEADLESS"))
            logger.debug("Browser successfully launched!")

            logger.info(f"Starting parse products from {len(catalogs)} catalogs...")
            async for catalogs_chunk in chunk_generator(catalogs, settings.get("MAX_CONCURRENT_TABS")):
                tasks = [asyncio.create_task(self.get_new_products_links(catalog, settings.get("TIMEOUT"))) for catalog in catalogs_chunk]
                catalogs_with_products = await asyncio.gather(*tasks)

                for catalog in catalogs_with_products:
                    if not catalog:
                        await self.get_products(catalog, settings.get("MAX_CONCURRENT_TABS"))
            logger.info(f"Finished parsing {len(catalogs)} catalogs!")


async def update_products():
    setup_logger()
    logger.info("Starting update products")

    proxy_manager = ProxyManager(redis_client)
    await proxy_manager.init_proxies()
    ozon_parser = OzonParserService()

    new_products = await ozon_parser.get_new_products()


if __name__ == '__main__':
    asyncio.run(update_products())
