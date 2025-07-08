from pydantic import BaseModel
from typing import Optional


class Product(BaseModel):
    ozon_url: str


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
    photos: Optional[list] = None
    video: Optional[str] = None
