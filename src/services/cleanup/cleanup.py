import asyncio
from datetime import datetime, timedelta
from loguru import logger

from src.repositories.tg_messages import TgMessagesRepository
from src.repositories.products import ProductsRepository
from src.schemas.tg_messages import TgMessages
from src.database.session import get_session
from src.core.config import generic_settings
from src.core.orm_to_dto import many_sqlalchemy_to_pydantic
from src.core.utils import chunk_generator
from src.uow.tg_bot_uow import TgBotUow
from src.services.cleanup.telegram import CleanupTelegramService


class CleanupService:
    def __init__(self, tg_bot_uow: TgBotUow):
        self.tg_bot_uow = tg_bot_uow

    async def get_outdated_messages(self) -> list[TgMessages] | None:
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
                logger.error(f"Error get outdated messages: {e}")
            else:
                return tg_messages

    async def delete_outdated_messages(self, tg_messages: list[TgMessages]) -> None:
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
                logger.error(f"Error delete outdated message: {e}")
                await session.rollback()
            else:
                await session.commit()

    async def cleanup(self) -> None:
        try:
            settings = generic_settings.TG_BOT_SETTINGS

            outdated_messages = await self.get_outdated_messages()
            if not outdated_messages:
                return None

            async with self.tg_bot_uow as tg_bot:
                cleanup_telegram_service = CleanupTelegramService(tg_bot.bot)
                async for tg_messages_chunk in chunk_generator(outdated_messages, settings.get("MAX_CONCURRENT_SENDING_TASKS")):
                    tasks = [
                        asyncio.create_task(cleanup_telegram_service.delete_outdated_messages(tg_message))
                        for tg_message in tg_messages_chunk]
                    await asyncio.gather(*tasks)

            await self.delete_outdated_messages(outdated_messages)

        except Exception as e:
            logger.error(f"Error cleanup: {e}")
