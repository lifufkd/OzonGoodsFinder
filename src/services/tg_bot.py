import asyncio
from loguru import logger
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton

from src.uow.tg_bot_uow import TgBotUow
from src.schemas.products import DBProduct, TgProduct
from src.schemas.categories import CatalogWithDBProducts, CatalogWithTgProducts
from src.schemas.tg_messages import AddTgMessage
from src.core.config import generic_settings
from src.core.utils import chunk_generator
from src.database.session import get_session
from src.repositories.tg_messages import TgMessagesRepository


class TgBotService:
    def __init__(self, tg_bot_uow: TgBotUow):
        self.tg_bot_uow = tg_bot_uow

    def _build_message_body(self, product: DBProduct, enable_link: bool = False) -> str:
        def build_characteristics(characteristics: dict) -> str:
            return "\n".join(f"<b>{key}:</b> {value}" for key, value in characteristics.items())

        msg = ""
        msg += f"#{product.hashtag}\n\n"
        msg += f"<b>{product.title}</b>\n\n"
        msg += f"<b>Скидка:</b> -{product.discount}%\n"
        msg += f"<b>Рейтинг продавца:</b> {product.rating} ⭐\n" if product.rating else ""
        msg += f"<b>Количество отзывов:</b> {product.reviews}\n\n" if product.reviews else ""
        msg += f"<b>Варианты товаров:</b>\n\n{product.unit_of_measure}\n" if product.unit_of_measure else ""
        msg += f"{', '.join(product.unit_variants)}\n\n" if product.unit_variants else ""
        msg += f"<b>Характеристики товара:</b>\n\n{build_characteristics(product.characteristics)}\n\n" if product.characteristics else ""
        msg += f"<b>Цена:</b> {product.price} ₽\n"
        if enable_link:
            msg += f"<a href=\"{product.url}\">Ссылка на товар</a>"

        return msg

    def _build_photo_pack(self, photos: list[str], caption: str) -> list[InputMediaPhoto]:
        result = []

        for index, photo in enumerate(photos):
            if index == 0:
                result.append(InputMediaPhoto(photo, caption=caption, parse_mode="HTML"))
            else:
                result.append(InputMediaPhoto(photo))

        return result

    def _build_url_button(self, url: str) -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🛒 КУПИТЬ", url=url))

        return keyboard

    async def send_message(self, chat_id: int, topic_id: int, product: DBProduct, tg_bot_session: AsyncTeleBot) -> TgProduct | None:
        try:
            if product.video_url:
                message = await tg_bot_session.send_video(
                    chat_id=chat_id,
                    message_thread_id=topic_id,
                    video=product.video_url,
                    caption=self._build_message_body(product),
                    parse_mode="HTML",
                    reply_markup=self._build_url_button(product.url)
                )
            elif product.photos_urls:
                if len(product.photos_urls) == 1:
                    message = await tg_bot_session.send_photo(
                        chat_id=chat_id,
                        message_thread_id=topic_id,
                        photo=product.photos_urls[0],
                        caption=self._build_message_body(product),
                        parse_mode="HTML",
                        reply_markup=self._build_url_button(product.url)
                    )
                else:
                    message = await tg_bot_session.send_media_group(
                        chat_id=chat_id,
                        message_thread_id=topic_id,
                        media=self._build_photo_pack(
                            product.photos_urls,
                            self._build_message_body(product, enable_link=True)
                        )
                    )
            else:
                message = await tg_bot_session.send_message(
                    chat_id=chat_id,
                    message_thread_id=topic_id,
                    text=self._build_message_body(product),
                    parse_mode="HTML",
                    reply_markup=self._build_url_button(product.url)
                )
        except Exception as e:
            logger.error(f"Error sending message to tg: {e}")
        else:
            tg_product = TgProduct(
                tg_message_id=message.message_id,
                **product.model_dump()
            )
            return tg_product

    async def save_send_messages_to_db(self, catalogs: list[CatalogWithTgProducts]) -> None:
        async for session in get_session():
            try:
                tg_messages_repository = TgMessagesRepository(session)
                for catalog in catalogs:
                    for product in catalog.products:
                        tg_message = AddTgMessage(
                            product_id=product.id,
                            tg_message_id=product.tg_message_id,
                            tg_group_id=catalog.tg_group_id,
                            tg_topic_id=catalog.tg_topic_id
                        )
                        await tg_messages_repository.add(tg_message)
            except Exception as e:
                logger.error(f"Error adding send tg messages to DB: {e}")
                await session.rollback()
            else:
                await session.commit()

    async def send_products(self, catalogs: list[CatalogWithDBProducts]) -> None:
        settings = generic_settings.TG_BOT_SETTINGS
        result = []

        try:
            async with self.tg_bot_uow as tg_bot:
                for index, catalog in enumerate(catalogs):
                    success_send = []
                    async for products_chunk in chunk_generator(catalog.products, settings.get("MAX_CONCURRENT_SENDING_TASKS")):
                        tasks = [asyncio.create_task(self.send_message(catalog.tg_group_id, catalog.tg_topic_id, product, tg_bot.bot)) for product in products_chunk]
                        send_products = await asyncio.gather(*tasks)

                        for send_product in send_products:
                            if not send_product:
                                continue

                            success_send.append(send_product)

                        await asyncio.sleep(settings.get("TIMEOUT"))

                    catalog_with_products = CatalogWithTgProducts(
                        tg_group_id=catalog.tg_group_id,
                        tg_topic_id=catalog.tg_topic_id,
                        url=catalog.url,
                        products=success_send
                    )
                    result.append(catalog_with_products)

            await self.save_send_messages_to_db(result)
        except Exception as e:
            logger.error(f"Error send messages to TG: {e}")
