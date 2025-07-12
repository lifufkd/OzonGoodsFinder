from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.products import Product
from src.schemas.products import FullProduct


class ProductsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_urls(self, urls: list[str]) -> list[Product]:
        query = (
            select(Product)
            .where(Product.url.in_(urls))
        )
        result = await self.session.execute(query)

        return list(result.scalars().all())

    async def get_all(self) -> list[str]:
        query = (
            select(
                Product.url
            )
        )
        result = await self.session.execute(query)

        return list(result.scalars().all())

    async def get_by_ids(self, products_ids: list[int]) -> list[Product]:
        query = (
            select(Product)
            .where(Product.id.in_(products_ids))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def add(self, product: FullProduct) -> Product:
        data = Product(
            **product.model_dump()
        )
        self.session.add(data)
        await self.session.flush()

        return data

    async def delete(self, product: Product) -> None:
        await self.session.delete(product)
