from loguru import logger

from src.scheduler.queue import broker


@broker.task
async def update_products():
    logger.info("Task started 1")


@broker.task
async def clean_old_products():
    logger.info("Task started 2")
