from loguru import logger
from telebot.types import ChatMemberAdministrator

from src.uow.tg_bot_uow import TgBotUow


class GenericTelegramService:
    def __init__(self, tg_bot_uow: TgBotUow):
        self.tg_bot_uow = tg_bot_uow

    async def verify_tg_permissions(self, chat_id: int) -> bool:
        try:
            async with self.tg_bot_uow as tg_bot:
                me = await tg_bot.bot.get_chat_member(chat_id, (await tg_bot.bot.get_me()).id)
                if not isinstance(me, ChatMemberAdministrator):
                    return False
                if me.status in ("administrator", "creator"):
                    return True
                else:
                    return False
        except Exception as e:
            logger.error(f"Error check permissions: {e}")
            return False
