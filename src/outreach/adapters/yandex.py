"""
Yandex Business adapter — Phase 2.

Planned approach:
  - Yandex Places API (https://yandex.ru/dev/geocode/doc)
  - Endpoint: https://search-maps.yandex.ru/v1/?text={query}&lang=ru_RU
  - Requires API key from developer.tech.yandex.ru
  - Pitfalls: tight rate limits (1000/day free), session cookies sometimes required
"""
from collections.abc import AsyncIterator

from outreach.adapters.base import Adapter, RawCompanyDTO


class YandexAdapter:
    name = "yandex"

    async def fetch(
        self, query: str, region: str | None = None, limit: int = 100
    ) -> AsyncIterator[RawCompanyDTO]:
        raise NotImplementedError("Phase 2")
        yield


_: Adapter = YandexAdapter()  # type: ignore[assignment]
