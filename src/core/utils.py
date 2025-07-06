import pytz
from datetime import datetime, time

from src.core.redis_client import redis_client


async def delete_schedule_keys():
    cursor = b"0"
    pattern = "schedule:*"

    while cursor:
        cursor, keys = await redis_client.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            await redis_client.delete(*keys)


def build_tasks_cron_expression(time_hh_mm: str, local_tz) -> str:
    hours, minutes = map(int, time_hh_mm.split(":"))
    local = pytz.timezone(local_tz)
    dt = local.localize(datetime.combine(datetime.today(), time(hour=hours, minute=minutes)))
    dt_utc = dt.astimezone(pytz.utc)
    return f"{dt_utc.minute} {dt_utc.hour} * * *"
