from pydantic import BaseModel


class Catalog(BaseModel):
    tg_group_id: int
    tg_topic_id: int
    ozon_url: str


class CatalogWithProducts(Catalog):
    ozon_products: list["Product"]


class CatalogWithFullProducts(Catalog):
    ozon_products: list["FullProduct"]

