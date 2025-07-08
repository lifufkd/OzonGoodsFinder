import pytz
import re
from datetime import datetime, time
from itertools import islice
from loguru import logger

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


async def chunk_generator(iterable, n):
    itterator = iter(iterable)
    while chunk := list(islice(itterator, n)):
        yield chunk


def format_proxy(proxy_url: str) -> dict | None:
    pattern = re.compile(
        r'^(?P<scheme>https?|socks5?|socks4)://(?:((?P<username>[^:]+):(?P<password>[^@]+)@)?)?(?P<ip>[^:]+):('
        r'?P<port>\d+)$'
    )

    match = pattern.match(proxy_url)
    if not match:
        return None

    result = {
        "server": f"{match.group('ip')}:{match.group('port')}",
    }

    if match.group("username") and match.group("password"):
        result["username"] = match.group("username")
        result["password"] = match.group("password")

    return result


def extract_number(text: str) -> int | None:
    try:
        return int(re.sub(r"\D", "", text))
    except Exception as e:
        logger.warning(f"Cannot extract number: {e}")
