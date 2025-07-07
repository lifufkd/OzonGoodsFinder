from pydantic import BaseModel


class Product(BaseModel):
    ozon_url: str


class FullProduct(Product):
    pass
