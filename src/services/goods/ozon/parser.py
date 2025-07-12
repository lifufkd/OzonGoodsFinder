from loguru import logger

from src.schemas.categories import Catalog, CatalogWithProducts
from src.schemas.products import Product, FullProduct
from src.repositories.products import ProductsRepository
from src.core.config import generic_settings
from src.parsers.ozon import OzonParser
from src.schemas.enums import SourceTypes
from src.database.session import get_session


class OzonParserService:
    def __init__(self, browser_session):
        self.browser = browser_session

    async def get_products_from_db(self) -> list[str] | list:
        products = []

        try:
            async for session in get_session():
                products_repository = ProductsRepository(session)
                data = await products_repository.get_all()
                products.extend(data)
        except Exception as e:
            logger.error(f"Error getting products: {e}")

        return products

    async def get_products_links(self, catalog: Catalog, timeout: int) -> CatalogWithProducts | None:
        ozon_parser = OzonParser(self.browser)
        products_urls = []
        catalog_with_products = None
        page = 1
        collected_products = 0

        try:
            existed_urls = set(await self.get_products_from_db())

            while collected_products < generic_settings.MAX_PRODUCTS_FROM_CATEGORY:
                temp_products_urls = await ozon_parser.allocate_browser(ozon_parser.parse_products_urls, catalog.url, page, timeout)
                if not temp_products_urls:
                    break

                temp_products_urls = list(set(url for url in temp_products_urls if url not in existed_urls))

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
