"""
List-org.com adapter — Phase 2.

Planned approach:
  - URL: https://www.list-org.com/search?type=all&val={query}&region={region}
  - Parse HTML table rows; extract INN, name, address from columns
  - Pitfalls: rate limiting; CAPTCHAs on bulk queries; no official API
"""
from collections.abc import AsyncIterator

from outreach.adapters.base import Adapter, RawCompanyDTO


class ListOrgAdapter:
    name = "listorg"

    async def fetch(
        self, query: str, region: str | None = None, limit: int = 100
    ) -> AsyncIterator[RawCompanyDTO]:
        raise NotImplementedError("Phase 2")
        yield  # make type checkers happy — unreachable


_: Adapter = ListOrgAdapter()
