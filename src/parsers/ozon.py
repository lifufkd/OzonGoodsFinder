import re
import asyncio
from loguru import logger

from src.core.config import generic_settings
from src.core.proxy_manager import ProxyManager
from src.core.redis_client import redis_client
from src.core.utils import format_proxy, clean_url
from src.core.exception_handlers import monitor_network_errors


class OzonParser:
    def __init__(self, browser_session):
        self.browser_session = browser_session

    async def allocate_browser(self, func, *args, **kwargs):
        proxy_manager = ProxyManager(redis_client)

        selected_proxy = await proxy_manager.get_next_proxy()
        formated_proxy = format_proxy(selected_proxy) if selected_proxy else None
        proxy = formated_proxy if formated_proxy else None

        logger.debug(f"Running parse task with proxy {selected_proxy}")

        context = await self.browser_session.new_context(proxy=proxy)
        browser_tab = await context.new_page()
        await monitor_network_errors(browser_tab)

        return await func(*args, browser_tab=browser_tab, **kwargs)

    def _extract_discount(self, raw_discount: str) -> int | None:
        match = re.search(r"−?(\d+)%", raw_discount)

        try:
            if match:
                return int(match.group(1))
        except ValueError:
            return None

    async def parse_products_urls(self, catalog_url, timeout: int = 3, browser_tab=None) -> list[str]:
        links = []
        settings = generic_settings.OZON_PARSER_SETTINGS

        await browser_tab.goto(catalog_url)
        await browser_tab.wait_for_selector(settings.get("PRODUCTS_SELECTOR"), timeout=10000)
        await asyncio.sleep(timeout)

        cards = await browser_tab.query_selector_all(settings.get("CARDS_SELECTOR"))
        logger.debug(f"Find {len(cards)} products in category {catalog_url}")

        for card in cards[:generic_settings.MAX_PRODUCTS_FROM_CATEGORY]:
            link_tag = await card.query_selector("a")
            link = await link_tag.get_attribute("href") if link_tag else None
            discount_span = await card.query_selector(settings.get("CARDS_DISCOUNT_SELECTOR"))
            raw_discount: str = await discount_span.inner_text() if discount_span else None

            if not link or not raw_discount:
                logger.debug(f"Product with link = {'https://www.ozon.ru' + link} and "
                             f"discount = {raw_discount} invalid!!!, skip")
                continue

            discount = self._extract_discount(raw_discount)
            if not discount or discount < generic_settings.MIN_PRODUCT_DISCOUNT:
                logger.debug(f"Product with link = {'https://www.ozon.ru' + link} and discount = {raw_discount} not "
                             f"satisfied min discount!!!, skip")
                continue

            result_link = clean_url("https://www.ozon.ru" + link)
            links.append(result_link)

        return links
