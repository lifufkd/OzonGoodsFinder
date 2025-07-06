from taskiq_redis import ListQueueBroker, RedisScheduleSource
from taskiq import TaskiqScheduler

from src.core.config import redis_settings

broker = ListQueueBroker(redis_settings.redis_url)
taskiq_redis_source = RedisScheduleSource(redis_settings.redis_url)
scheduler = TaskiqScheduler(broker, sources=[taskiq_redis_source])

import src.scheduler.tasks # noqa
