from pydantic import BaseModel
from typing import Optional


class Product(BaseModel):
    url: str


class FullProduct(Product):
    title: str
    hashtag: str
    rating: Optional[float] = None
    reviews: Optional[int] = None
    discount: int
    price: int
    unit_of_measure: Optional[str] = None
    unit_variants: Optional[list] = None
    characteristics: Optional[dict] = None
    photos_urls: Optional[list] = None
    video_url: Optional[str] = None


class ExistedProduct(FullProduct):
    id: int
