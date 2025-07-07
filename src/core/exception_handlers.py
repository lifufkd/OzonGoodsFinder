from loguru import logger


async def monitor_network_errors(page):
    @page.on("requestfailed")
    async def on_request_failed(request):
        failure = request.failure
        error_text = failure.get("errorText") if failure else "Unknown error"
        logger.error(f"❌ Request failed: {request.method} {request.url} — {error_text}")

    @page.on("response")
    async def on_response(response):
        if response.status >= 400:
            try:
                body = await response.text()
            except Exception:
                body = "<could not decode body>"
            logger.warning(f"⚠️ Bad response: {response.status} {response.url}\nBody: {body[:200]}")

    @page.on("pageerror")
    async def on_page_error(error):
        logger.error(f"💥 Page error: {error}")

    @page.on("console")
    async def on_console_message(msg):
        if msg.type == "error":
            logger.error(f"🧩 Console error: {msg.text}")
        elif msg.type == "warning":
            logger.warning(f"🔶 Console warning: {msg.text}")
        else:
            logger.debug(f"📜 Console: {msg.type} — {msg.text}")

    @page.on("requestfinished")
    async def on_request_finished(request):
        logger.debug(f"✅ Request finished: {request.method} {request.url}")
