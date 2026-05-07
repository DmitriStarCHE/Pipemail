"""
ЕИС (Единая информационная система закупок) adapter — Phase 3.

Planned approach:
  - REST API: https://zakupki.gov.ru/epz/order/extendedsearch/results.html
  - Search by OKPD2 code for pipes: 24.20 (Трубы стальные)
  - Extract customer INN from tender docs
  - Pitfalls: XML-heavy responses; paging with up to 10k results per query
"""
from collections.abc import AsyncIterator

from outreach.adapters.base import Adapter, RawCompanyDTO


class EisAdapter:
    name = "eis"

    async def fetch(
        self, query: str, region: str | None = None, limit: int = 100
    ) -> AsyncIterator[RawCompanyDTO]:
        raise NotImplementedError("Phase 3")
        yield


_: Adapter = EisAdapter()
