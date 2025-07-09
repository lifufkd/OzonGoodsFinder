from pydantic import BaseModel

from src.schemas.enums import SourceTypes


class Catalog(BaseModel):
    tg_group_id: int
    tg_topic_id: int
    source_type: SourceTypes
    url: str


class CatalogWithProducts(Catalog):
    products: list["Product"]


class CatalogWithFullProducts(Catalog):
    products: list["FullProduct"]


class CatalogWithDBProducts(Catalog):
    products: list["ExistedProduct"]
