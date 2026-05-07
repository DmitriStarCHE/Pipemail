import asyncio
import time

import httpx
import structlog

log = structlog.get_logger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_PATHS = [
    "",
    "/contacts",
    "/contact",
    "/kontakty",
    "/about",
    "/o-kompanii",
    "/o-nas",
    "/svyaz",
    "/contacts/",
]

_domain_last_request: dict[str, float] = {}
_ua_index = 0


async def scrape_domain(domain: str) -> list[str]:
    """Return list of HTML page contents from the domain.

    Tries common contact paths. Respects 3-second per-domain rate limit.
    Skips on 403/SSL/connection errors without retrying.
    """
    global _ua_index
    pages: list[str] = []

    async with httpx.AsyncClient(
        timeout=10,
        max_redirects=3,
        http2=True,
        follow_redirects=True,
    ) as client:
        for path in _PATHS:
            url = f"https://{domain}{path}"
            await _rate_limit(domain)
            ua = _USER_AGENTS[_ua_index % len(_USER_AGENTS)]
            _ua_index += 1
            try:
                resp = await client.get(url, headers={"User-Agent": ua})
                if resp.status_code in (403, 429):
                    log.info("scraper.skipped", url=url, status=resp.status_code)
                    break
                if resp.status_code == 200:
                    pages.append(resp.text)
            except (httpx.SSLError, httpx.ConnectError, httpx.TimeoutException) as exc:
                log.info("scraper.error", url=url, error=str(exc))

    return pages


async def _rate_limit(domain: str) -> None:
    now = time.monotonic()
    last = _domain_last_request.get(domain, 0.0)
    wait = 3.0 - (now - last)
    if wait > 0:
        await asyncio.sleep(wait)
    _domain_last_request[domain] = time.monotonic()
