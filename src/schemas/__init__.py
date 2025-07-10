from src.schemas.categories import CatalogWithProducts, CatalogWithFullProducts, CatalogWithDBProducts, CatalogWithTgProducts
from src.schemas.products import Product, FullProduct, DBProduct, TgProduct # noqa

CatalogWithProducts.model_rebuild()
CatalogWithFullProducts.model_rebuild()
CatalogWithDBProducts.model_rebuild()
CatalogWithTgProducts.model_rebuild()
