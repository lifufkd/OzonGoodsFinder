import re
import asyncio
import json
from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import Error

from src.core.config import generic_settings
from src.core.proxy_manager import ProxyManager
from src.core.redis_client import redis_client
from src.core.exceptions import ProxyError
from src.core.utils import format_proxy, extract_number, clean_url, remove_all_whitespace


class OzonParser:
    def __init__(self, browser_session):
        self.browser_session = browser_session

    async def allocate_browser(self, func, *args, **kwargs):
        extracted_proxy = False
        proxy_manager = ProxyManager(redis_client)

        selected_proxy = await proxy_manager.get_next_proxy()
        if selected_proxy is None:
            browser_tab = None
            logger.debug(f"Try 1/1. Run without proxy")

            try:
                context = await self.browser_session.new_context(
                    **generic_settings.BROWSER_SETTINGS.get("CONTEXT_SETTINGS")
                )
                browser_tab = await context.new_page()
                await browser_tab.add_init_script("""
                    const getParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(param) {
                      if (param === 37445) return "Intel Inc.";        // UNMASKED_VENDOR_WEBGL
                      if (param === 37446) return "Intel Iris OpenGL"; // UNMASKED_RENDERER_WEBGL
                      return getParameter.call(this, param);
                    };
                """)
                await browser_tab.add_init_script(
                    """
                    Object.defineProperty(navigator, 'plugins', {
                      get: () => [1, 2, 3, 4, 5],
                    });

                    Object.defineProperty(navigator, 'mimeTypes', {
                      get: () => [1, 2, 3],
                    });
                    """
                )

                return await func(*args, browser_tab=browser_tab, **kwargs)
            except ProxyError:
                logger.critical(f"Host IP was banned, can't continue")
                return None
            finally:
                if browser_tab:
                    await browser_tab.close()
        else:
            proxy = format_proxy(selected_proxy)
            for attempt in range(generic_settings.PROXY_RETRIES_COUNT):
                browser_tab = None
                logger.debug(f"Try {attempt + 1}/{generic_settings.PROXY_RETRIES_COUNT}. Run with proxy: {proxy}")

                try:
                    context = await self.browser_session.new_context(
                        proxy=proxy,
                        **generic_settings.BROWSER_SETTINGS.get("CONTEXT_SETTINGS")
                    )
                    browser_tab = await context.new_page()
                    await browser_tab.add_init_script("""
                        const getParameter = WebGLRenderingContext.prototype.getParameter;
                        WebGLRenderingContext.prototype.getParameter = function(param) {
                          if (param === 37445) return "Intel Inc.";        // UNMASKED_VENDOR_WEBGL
                          if (param === 37446) return "Intel Iris OpenGL"; // UNMASKED_RENDERER_WEBGL
                          return getParameter.call(this, param);
                        };
                    """)
                    await browser_tab.add_init_script(
                        """
                        Object.defineProperty(navigator, 'plugins', {
                          get: () => [1, 2, 3, 4, 5],
                        });
    
                        Object.defineProperty(navigator, 'mimeTypes', {
                          get: () => [1, 2, 3],
                        });
                        """
                    )

                    result = await func(*args, browser_tab=browser_tab, **kwargs)
                    if extracted_proxy:
                        await proxy_manager.return_proxy(selected_proxy)

                    return result
                except ProxyError:
                    if not extracted_proxy:
                        await proxy_manager.remove_proxy(selected_proxy)
                        extracted_proxy = True

                    backoff = generic_settings.OZON_PARSER_SETTINGS.get("TIMEOUT") * (2 ** attempt)
                    logger.warning(f"Proxy {selected_proxy} has been temporarily banned, retry after {backoff} seconds")
                    await asyncio.sleep(backoff)
                finally:
                    if browser_tab:
                        await browser_tab.close()

        logger.warning(f"Proxy {selected_proxy} has been banned")
        return None

    def _extract_discount(self, raw_discount: str) -> int | None:
        match = re.search(r"[−-](\d+)%", raw_discount)
        try:
            if match:
                return int(match.group(1))
        except Exception as e:
            logger.debug(f"Cannot extract discount: {e}")

    def _replace_ozon_cover_url(self, url: str) -> str:
        parts = url.split('/')
        if len(parts) >= 2:
            parts[-2] = 'wc1000'
        return '/'.join(parts)

    def _find_hashtag(self, soup: BeautifulSoup) -> str | None:
        hashtag = None
        try:
            div = soup.find("div", id=re.compile(r"^state-breadCrumbs-"))
            if not div:
                logger.warning(f"Cannot find div with id = state-breadCrumbs")
                return hashtag
            data_state = div.get("data-state")
            if not data_state:
                logger.warning(f"Cannot find attribute data-state for div with id = state-breadCrumbs")
                return hashtag

            data = json.loads(data_state)
            breadcrumbs = data.get("breadcrumbs")

            raw_pre_last_hashtag = breadcrumbs[-2]["text"]
            raw_last_hashtag = breadcrumbs[-1]["text"]
            hashtag = f"{remove_all_whitespace(raw_pre_last_hashtag)}_{remove_all_whitespace(raw_last_hashtag)}"
        except Exception as e:
            logger.warning(f"Cannot find hashtag: {e}")
        finally:
            return hashtag

    def _find_title(self, soup: BeautifulSoup) -> str | None:
        title = None
        try:
            div = soup.find("div", id=re.compile(r"^state-webStickyProducts-"))
            if not div:
                logger.warning(f"Cannot find div with id = state-webStickyProducts")
                return title
            data_state = div.get("data-state")
            if not data_state:
                logger.warning(f"Cannot find attribute data-state for div with id = state-webStickyProducts")
                return title

            data = json.loads(data_state)
            title = data["name"]
        except Exception as e:
            logger.warning(f"Cannot find title: {e}")
        finally:
            return title

    def _find_discount(self, soup: BeautifulSoup) -> int | None:
        discounts = []
        try:
            blocks = soup.find_all(attrs={"data-widget": "webMarketingLabels"})
            for block in blocks:
                text = block.get_text()
                discount = self._extract_discount(text)
                if discount:
                    discounts.append(discount)

            if discounts:
                return max(discounts)
            else:
                logger.warning(f"Cannot find discount, because all tags are empty")
        except Exception as e:
            logger.warning(f"Cannot find discount: {e}")

    def _find_rating_and_review(self, soup: BeautifulSoup) -> tuple | None:
        rating, reviews = None, None
        try:
            for script in soup.find_all("script"):
                if script.string and '"aggregateRating"' in script.string:
                    try:
                        data = json.loads(script.string.strip())
                        rating = float(data.get("aggregateRating", {}).get("ratingValue"))
                        reviews = int(data.get("aggregateRating", {}).get("reviewCount"))
                        break
                    except Exception as e:
                        logger.debug(f"Cannot find rating or review: {e}")
                        continue
        except Exception as e:
            logger.debug(f"Cannot find rating and review: {e}")
        finally:
            return rating, reviews

    def _find_price(self, soup: BeautifulSoup) -> int | None:
        price = None
        try:
            div = soup.find("div", id=re.compile(r"^state-webPrice-"))
            if not div:
                logger.warning(f"Cannot find div with id = state-webPrice")
                return price
            data_state = div.get("data-state")
            if not data_state:
                logger.warning(f"Cannot find attribute data-state for div with id = state-webPrice")
                return price

            data = json.loads(data_state)
            extracted_price = extract_number(data.get("cardPrice"))
            if extracted_price:
                price = extracted_price
            else:
                logger.warning(f"Cannot extract price")
        except Exception as e:
            logger.warning(f"Cannot find prices: {e}")
        finally:
            return price

    def _find_unit_of_measure(self, soup: BeautifulSoup) -> tuple:
        unit_of_measure, unit_variants = None, []
        try:
            div = soup.find("div", id=re.compile(r"^state-webAspects-"))
            if not div:
                logger.debug(f"Cannot find div with id = state-webAspects")
                return None, unit_variants
            data_state = div.get("data-state")
            if not data_state:
                logger.debug(f"Cannot find attribute data-state for div with id = state-webAspects")
                return None, unit_variants

            data = json.loads(data_state)
            aspects = data.get("aspects")
            for aspect in aspects:
                for product_type in generic_settings.OZON_PARSER_SETTINGS.get("PRODUCT_UNIT_OF_MEASURES"):
                    if product_type not in aspect.get("aspectKey"):
                        continue

                    unit_of_measure = aspect.get("aspectName")
                    for variant in aspect.get("variants"):
                        if generic_settings.ALLOW_ONLY_IN_STOCK_MEASURE and variant.get("availability") != "inStock":
                            logger.debug(f"Unit variant skipped because its out of stock")
                            continue

                        data = variant.get("data").get("searchableText")
                        if not data:
                            continue

                        unit_variants.append(data)

                    return unit_of_measure, unit_variants
        except Exception as e:
            logger.debug(f"Cannot find prices: {e}")
        finally:
            return unit_of_measure, unit_variants

    def _find_characteristics(self, soup: BeautifulSoup, filter: list | None = None) -> dict:
        result = {}
        try:
            div = soup.find("div", id=re.compile(r"^state-webShortCharacteristics-"))
            if not div:
                logger.debug(f"Cannot find div with id = state-webShortCharacteristics")
                return result
            data_state = div.get("data-state")
            if not data_state:
                logger.debug(f"Cannot find attribute data-state for div with id = state-webShortCharacteristics")
                return result

            data = json.loads(data_state)
            for char in data.get("characteristics"):
                try:
                    name = char.get("title").get("textRs")[0].get("content")
                    value = ""
                    for part_value in char.get("values"):
                        value += part_value.get("text", "")

                    if not name or not value:
                        continue
                    if filter and name in filter:
                        continue

                    result[name] = value
                except Exception as e:
                    logger.debug(f"Cannot find name or value for characteristic: {e}")
        except Exception as e:
            logger.debug(f"Cannot find characteristics: {e}")
        finally:
            return result

    def _find_photos(self, soup: BeautifulSoup) -> list[str] | list:
        image_urls = list()
        try:
            gallery_div = soup.find("div", attrs={"data-widget": "webGallery"})
            if gallery_div:
                for img in gallery_div.find_all("img", src=True):
                    src = img["src"]
                    if not src:
                        continue

                    image_urls.append(self._replace_ozon_cover_url(src))
            else:
                logger.warning(f"Cannot find webGallery attribute")
        except Exception as e:
            logger.warning(f"Cannot find images: {e}")
        finally:
            return image_urls

    def _find_video(self, soup: BeautifulSoup) -> str | None:
        video_url = None
        try:
            tag = soup.find("video-player")
            if tag:
                video_url = tag["src"]
            else:
                logger.debug(f"Cannot find video-player tag")
        except Exception as e:
            logger.debug(f"Cannot find video: {e}")
        finally:
            return video_url

    async def parse_products_urls(self, catalog_url, page: int, timeout: int = 3, browser_tab=None) -> list[str] | list:
        links = []

        try:
            settings = generic_settings.OZON_PARSER_SETTINGS

            await browser_tab.goto(catalog_url + f"&page={page}", timeout=timeout*10*1000, wait_until="networkidle")
            await asyncio.sleep(timeout)
            await browser_tab.wait_for_selector(settings.get("PRODUCTS_SELECTOR"), timeout=timeout*1000)

            cards = await browser_tab.query_selector_all(settings.get("CARDS_SELECTOR"))
            logger.debug(f"Find {len(cards)} products in category {catalog_url}")

            for card in cards:
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
        except Error as e:
            if "proxy" in str(e).lower() or "net" in str(e) or "timeout" in str(e).lower():
                raise ProxyError()
            else:
                logger.warning(f"Error parse products links: {e}")
        except Exception as e:
            logger.warning(f"Error parse products links: {e}")

        return links

    async def parse_product(self, product_url: str, timeout: int = 3, browser_tab=None) -> dict | None:

        try:
            await browser_tab.goto(product_url, timeout=timeout*10*1000, wait_until="networkidle")
            await asyncio.sleep(timeout)

            content = await browser_tab.content()
            soup = BeautifulSoup(content, "html.parser")

            hashtag = self._find_hashtag(soup)
            title = self._find_title(soup)
            rating, reviews = self._find_rating_and_review(soup)
            discount = self._find_discount(soup)
            price = self._find_price(soup)
            # unit_of_measure, unit_variants = self._find_unit_of_measure(soup)  # Disabled because not used anymore
            # characteristics = self._find_characteristics(soup, filter=[unit_of_measure])  # Disabled because not used anymore
            characteristics = self._find_characteristics(soup)
            video_src = self._find_video(soup)
            photos = []
            if not video_src:
                photos = list(dict.fromkeys(self._find_photos(soup)))[:generic_settings.PRODUCTS_PHOTOS_QUANTITY]

            return {
                "title": title,
                "hashtag": hashtag,
                "rating": rating,
                "reviews": reviews,
                "discount": discount,
                "price": price,
                # "unit_of_measure": unit_of_measure,  # Disabled because not used anymore
                # "unit_variants": unit_variants if unit_variants else None,  # Disabled because not used anymore
                "characteristics": characteristics if characteristics else None,
                "photos_urls": photos if photos else None,
                "video_url": video_src
            }
        except Error as e:
            if "proxy" in str(e).lower() or "net" in str(e) or "timeout" in str(e).lower():
                raise ProxyError()
            else:
                logger.warning(f"Error parse product: {e}")
        except Exception as e:
            logger.warning(f"Error parse product: {e}")

