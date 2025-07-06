from redis.asyncio import Redis

from src.core.config import redis_settings

redis_client = Redis.from_url(redis_settings.redis_url)
