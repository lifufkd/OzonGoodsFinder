import asyncio
from loguru import logger

from src.uow.tg_bot_uow import TgBotUow
from src.core.config import tg_settings
from src.core.logger import setup_logger
from src.core.proxy_manager import ProxyManager
from src.core.redis_client import redis_client
from src.scheduler.task_queue import broker
from src.services.goods.ozon.ozon import OzonService
from src.services.cleanup.cleanup import CleanupService


@broker.task
async def update_products():
    setup_logger()
    logger.info(f"Starting updating products...")

    proxy_manager = ProxyManager(redis_client)
    await proxy_manager.init_proxies()

    tg_bot_uow = TgBotUow(tg_settings.TG_BOT_TOKEN)
    ozon = OzonService(tg_bot_uow)

    await ozon.get_new_products()

    logger.info(f"Products updated finished!")


@broker.task
async def clean_old_products():
    setup_logger()
    logger.info(f"Starting cleanup...")

    tg_bot_uow = TgBotUow(tg_settings.TG_BOT_TOKEN)
    cleanup_service = CleanupService(tg_bot_uow)
    await cleanup_service.cleanup()

    logger.info(f"Cleanup finished!")


if __name__ == '__main__':
    asyncio.run(update_products())
