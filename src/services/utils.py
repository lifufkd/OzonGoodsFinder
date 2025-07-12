from loguru import logger
import sys

from src.core.exceptions import TgPermissionsError, TgChatIdInvalid, TgChatTopicIdInvalid
from src.schemas.enums import SourceTypes
from src.schemas.categories import Catalog
from src.core.config import generic_settings
from src.uow.tg_bot_uow import TgBotUow
from src.services.telegram import GenericTelegramService


async def get_catalogs(telegram_uow: TgBotUow) -> list[Catalog]:
    result = []
    telegram_service = GenericTelegramService(telegram_uow)

    try:
        for category in generic_settings.CATEGORIES:
            tg_group_id = category.get('TG_GROUP_ID')
            if not isinstance(tg_group_id, int) or tg_group_id > 0:
                raise TgChatIdInvalid(detail=f"Tg group id ({tg_group_id}) is invalid")
            if not await telegram_service.verify_tg_permissions(chat_id=tg_group_id):
                raise TgPermissionsError(detail=f"Tg bot does not have permission to access Tg group id ({tg_group_id})")

            for first_sub_category in category.get("SUB_CATEGORIES"):
                tg_topic_id = first_sub_category.get('TG_TOPIC_ID')
                if not isinstance(tg_topic_id, int) or tg_topic_id < 0:
                    raise TgChatTopicIdInvalid(detail=f"Tg group topic id ({tg_topic_id}) is invalid")

                for second_sub_category in first_sub_category.get("SUB_CATEGORIES"):
                    if second_sub_category.get("PARSE_SOURCE") != SourceTypes.OZON.value:
                        continue

                    result.append(
                        Catalog(
                            tg_group_id=tg_group_id,
                            tg_topic_id=tg_topic_id,
                            url=second_sub_category.get("URL")
                        )
                    )
    except Exception as e:
        logger.critical(f"Error getting catalogs from config: {e}")
        sys.exit(1)

    return result
