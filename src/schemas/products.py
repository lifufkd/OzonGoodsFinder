from pydantic import BaseModel, Field
from typing import Optional

from src.schemas.enums import SourceTypes


class Product(BaseModel):
    url: str


class FullProduct(Product):
    source_type: SourceTypes
    title: str
    hashtag: list[str] = Field(min_length=2)
    rating: Optional[float] = None
    reviews: Optional[int] = None
    discount: int
    price: int
    unit_of_measure: Optional[str] = None
    unit_variants: Optional[list] = None
    characteristics: Optional[dict] = None
    photos_urls: Optional[list] = None
    video_url: Optional[str] = None


class DBProduct(FullProduct):
    id: int


class TgProduct(DBProduct):
    tg_message_id: int
