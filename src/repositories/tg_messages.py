from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from src.models.tg_messages import TgMessages
from src.schemas.tg_messages import AddTgMessage


class TgMessagesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_outdated(self, max_age: datetime) -> list[TgMessages]:
        query = (
            select(TgMessages)
            .where(TgMessages.created_at < max_age)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_ids(self, tg_message_ids: list[int]) -> list[TgMessages]:
        query = (
            select(TgMessages)
            .where(TgMessages.id.in_(tg_message_ids))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def add(self, tg_message: AddTgMessage) -> TgMessages:
        data = TgMessages(
            **tg_message.model_dump()
        )
        self.session.add(data)
        await self.session.flush()

        return data

    async def delete(self, tg_message: TgMessages) -> None:
        await self.session.delete(tg_message)
