import asyncio
from loguru import logger
from datetime import datetime, timedelta
from telebot.async_telebot import AsyncTeleBot

from src.uow.tg_bot_uow import TgBotUow
from src.core.orm_to_dto import many_sqlalchemy_to_pydantic
from src.schemas.tg_messages import TgMessages
from src.core.config import generic_settings
from src.database.session import get_session
from src.repositories.tg_messages import TgMessagesRepository
from src.repositories.products import ProductsRepository
from src.core.utils import chunk_generator


class CleanupService:
    def __init__(self, tg_bot_uow: TgBotUow):
        self.tg_bot_uow = tg_bot_uow

    async def get_outdated_tg_messages(self) -> list[TgMessages] | None:
        async for session in get_session():
            try:
                tg_messages_repository = TgMessagesRepository(session)

                max_age = datetime.utcnow() - timedelta(seconds=generic_settings.TG_BOT_SETTINGS.get("MAX_MESSAGES_AGE"))
                orm_tg_messages = await tg_messages_repository.get_outdated(max_age)
                tg_messages = await many_sqlalchemy_to_pydantic(
                    orm_tg_messages,
                    TgMessages
                )
            except Exception as e:
                logger.error(f"Error get outdated tg messages from DB: {e}")
            else:
                return tg_messages

    async def delete_tg_messages_from_tg(self, tg_message: TgMessages, tg_bot_session: AsyncTeleBot) -> None:
        try:
            await tg_bot_session.delete_message(
                chat_id=tg_message.tg_group_id,
                message_id=tg_message.tg_message_id
            )
        except Exception as e:
            logger.error(f"Error delete outdated tg message from TG: {e}")

    async def delete_tg_messages_from_db(self, tg_messages: list[TgMessages]) -> None:
        async for session in get_session():
            try:
                tg_messages_repository = TgMessagesRepository(session)
                products_repository = ProductsRepository(session)

                tg_messages_ids = [tg_message.id for tg_message in tg_messages]
                products_ids = [tg_message.product_id for tg_message in tg_messages]

                if tg_messages_ids:
                    orm_tg_messages = await tg_messages_repository.get_by_ids(tg_messages_ids)
                    for orm_tg_message in orm_tg_messages:
                        await tg_messages_repository.delete(orm_tg_message)
                if products_ids:
                    orm_products = await products_repository.get_by_ids(products_ids)
                    for orm_product in orm_products:
                        await products_repository.delete(orm_product)

            except Exception as e:
                logger.error(f"Error delete outdated tg message from DB: {e}")
                await session.rollback()
            else:
                await session.commit()

    async def cleanup_old_products(self) -> None:
        settings = generic_settings.TG_BOT_SETTINGS

        try:
            outdated_tg_messages = await self.get_outdated_tg_messages()
            if not outdated_tg_messages:
                return None

            async with self.tg_bot_uow as tg_bot:
                async for tg_messages_chunk in chunk_generator(outdated_tg_messages, settings.get("MAX_CONCURRENT_SENDING_TASKS")):
                    tasks = [
                        asyncio.create_task(self.delete_tg_messages_from_tg(tg_message, tg_bot.bot))
                        for tg_message in tg_messages_chunk]
                    await asyncio.gather(*tasks)

            await self.delete_tg_messages_from_db(outdated_tg_messages)
        except Exception as e:
            logger.error(f"Error cleanup: {e}")
