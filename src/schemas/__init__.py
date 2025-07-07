from src.schemas.categories import CatalogWithProducts, CatalogWithFullProducts
from src.schemas.products import Product, FullProduct # noqa

CatalogWithProducts.model_rebuild()
CatalogWithFullProducts.model_rebuild()
