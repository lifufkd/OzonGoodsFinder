import asyncio
from loguru import logger
from telebot.asyncio_helper import ApiTelegramException
from telebot.async_telebot import AsyncTeleBot

from src.schemas.tg_messages import TgMessages
from src.core.config import generic_settings


class CleanupTelegramService:
    def __init__(self, bot_session: AsyncTeleBot):
        self.bot_session = bot_session

    async def delete_outdated_messages(self, tg_message: TgMessages) -> None:
        attempt = 1

        while True:
            try:
                await self.bot_session.delete_message(
                    chat_id=tg_message.tg_group_id,
                    message_id=tg_message.tg_message_id
                )
                return None
            except ApiTelegramException as e:
                if e.error_code == 429:
                    backoff = generic_settings.TG_BOT_SETTINGS.get("API_BASE_TIMEOUT") * (2 ** attempt)
                    attempt += 1

                    logger.debug(f"Telegram API timeout, continue after {backoff} seconds")
                    await asyncio.sleep(backoff)

                    continue
                else:
                    logger.error(f"Error delete outdated messages: {e}")
                    return None
            except Exception as e:
                logger.error(f"Error delete outdated messages: {e}")
                return None
