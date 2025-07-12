from loguru import logger
from telebot.async_telebot import AsyncTeleBot

from src.schemas.tg_messages import TgMessages


class CleanupTelegramService:
    def __init__(self, bot_session: AsyncTeleBot):
        self.bot_session = bot_session

    async def delete_outdated_messages(self, tg_message: TgMessages) -> None:
        try:
            await self.bot_session.delete_message(
                chat_id=tg_message.tg_group_id,
                message_id=tg_message.tg_message_id
            )
        except Exception as e:
            logger.error(f"Error delete outdated messages: {e}")
