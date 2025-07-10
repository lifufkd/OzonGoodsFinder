from telebot.async_telebot import AsyncTeleBot


class TgBotUow:
    def __init__(self, token: str):
        self.token = token
        self.bot = AsyncTeleBot(token)

    async def __aenter__(self):
        self.bot = AsyncTeleBot(self.token)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.bot.close_session()

    async def start_polling(self):
        await self.bot.infinity_polling()

    # async def send_message(self, chat_id: int, text: str):
    #     await self.bot.send_message(chat_id, text)
