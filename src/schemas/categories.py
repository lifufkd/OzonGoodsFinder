from pydantic import BaseModel


class Catalog(BaseModel):
    tg_group_id: int
    tg_topic_id: int
    tag: str
    url: str


class CatalogWithProducts(Catalog):
    products: list["Product"]


class CatalogWithFullProducts(Catalog):
    products: list["FullProduct"]


class CatalogWithDBProducts(Catalog):
    products: list["DBProduct"]


class CatalogWithTgProducts(Catalog):
    products: list["TgProduct"]
