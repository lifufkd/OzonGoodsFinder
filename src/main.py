import asyncio
from loguru import logger

from src.core.logger import setup_logger
from src.scheduler.queue import taskiq_redis_source
from src.scheduler.tasks import update_products, clean_old_products
from src.core.utils import build_tasks_cron_expression, delete_schedule_keys
from src.core.config import generic_settings


__version__ = "1.0.0"


async def main():
    setup_logger()
    logger.info("Starting OzonGoodsFinder v" + __version__)

    await delete_schedule_keys()
    logger.info("Old scheduled tasks successfully cleaned!\n")

    await taskiq_redis_source.startup()

    logger.info("Starting scheduling new tasks...\n")
    for update_time in generic_settings.UPDATE_TIMES:
        await update_products.schedule_by_cron(
            taskiq_redis_source,
            build_tasks_cron_expression(update_time, generic_settings.TIME_ZONE)
        )
        logger.info(f"Update task successfully scheduled for {update_time} every day!")

    await clean_old_products.schedule_by_cron(
        taskiq_redis_source,
        build_tasks_cron_expression(generic_settings.CLEANUP_TIME, generic_settings.TIME_ZONE)
    )
    logger.info(f"Cleanup task successfully scheduled for {generic_settings.CLEANUP_TIME} every day!\n")

    logger.info("All new tasks created, finishing...")


if __name__ == '__main__':
    asyncio.run(main())
