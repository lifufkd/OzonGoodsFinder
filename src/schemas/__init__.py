from src.schemas.categories import CatalogWithProducts, CatalogWithFullProducts, CatalogWithDBProducts
from src.schemas.products import Product, FullProduct, ExistedProduct # noqa

CatalogWithProducts.model_rebuild()
CatalogWithFullProducts.model_rebuild()
CatalogWithDBProducts.model_rebuild()
