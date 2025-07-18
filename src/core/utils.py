from urllib.parse import urlparse, urlunparse
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
        r'^(?P<scheme>https?|socks5?|socks4)://'
        r'(?:((?P<username>[^:]+):(?P<password>[^@]+)@)?)?'
        r'(?P<ip>[^:]+):(?P<port>\d+)$'
    )

    match = pattern.match(proxy_url)
    if not match:
        return None

    scheme = match.group('scheme')
    ip = match.group('ip')
    port = match.group('port')

    result = {
        "server": f"{scheme}://{ip}:{port}"
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


def clean_url(url: str) -> str:
    parsed = urlparse(url)
    cleaned = parsed._replace(query="")
    return str(urlunparse(cleaned))


def text_escape(text: str) -> str:
    return re.sub(r'[^\w_]+', '', text)


def remove_all_whitespace(text: str) -> str:
    return re.sub(r'\s+', '', text)


def normalize_hashtag(raw_hashtag: str) -> str:
    hashtag = remove_all_whitespace(raw_hashtag)
    hashtag = hashtag.lower()
    hashtag = text_escape(hashtag)
    return hashtag


def build_hashtag(raw_hashtag: list[str]) -> str | None:
    match len(raw_hashtag):
        case 0 | 1:
            selected_parts = None
        case 2:
            selected_parts = [raw_hashtag[1]]
        case 3:
            selected_parts = [raw_hashtag[1], raw_hashtag[-1]]
        case _:
            selected_parts = [raw_hashtag[1]] + raw_hashtag[-2:]

    if not selected_parts:
        return None

    hashtag = '_'.join(selected_parts)
    normalized_hashtag = normalize_hashtag(hashtag)
    return normalized_hashtag
