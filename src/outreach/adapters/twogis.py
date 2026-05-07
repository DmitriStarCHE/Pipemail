import asyncio
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from outreach.adapters.base import RawCompanyDTO

log = structlog.get_logger(__name__)

_TWOGIS_URL = "https://catalog.api.2gis.com/3.0/items"
_FIELDS = "items.org,items.contact_groups,items.point,items.adm_div,items.region_id"
_PAGE_SIZE = 50


class TwoGISAdapter:
    name = "2gis"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def fetch(
        self, query: str, region: str | None = None, limit: int = 100
    ) -> AsyncIterator[RawCompanyDTO]:
        fetched = 0
        page = 1

        async with httpx.AsyncClient(timeout=15) as client:
            while fetched < limit:
                params: dict[str, str | int] = {
                    "q": query,
                    "fields": _FIELDS,
                    "key": self._api_key,
                    "page_size": min(_PAGE_SIZE, limit - fetched),
                    "page": page,
                    "type": "branch",
                }
                if region:
                    params["region_id"] = region

                resp = await client.get(_TWOGIS_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

                result = data.get("result", {})
                items = result.get("items", [])
                if not items:
                    break

                for item in items:
                    if fetched >= limit:
                        return
                    dto = self._parse_item(item)
                    if dto:
                        fetched += 1
                        yield dto

                total = result.get("total", 0)
                if fetched >= total:
                    break
                page += 1
                await asyncio.sleep(0.5)

    def _parse_item(self, item: dict[str, Any]) -> RawCompanyDTO | None:
        org = item.get("org") or item.get("name_ex")
        if not org:
            return None
        name = org.get("name", "").strip()
        if not name:
            return None

        domain: str | None = None
        phone: str | None = None
        for group in item.get("contact_groups", []):
            for contact in group.get("contacts", []):
                ctype = contact.get("type", "")
                value = contact.get("value", "")
                if ctype == "website" and not domain:
                    parsed = urlparse(value if "://" in value else f"https://{value}")
                    domain = parsed.netloc or parsed.path
                    domain = domain.removeprefix("www.").rstrip("/").split("/")[0] or None
                elif ctype == "phone" and not phone:
                    phone = value

        adm_div = item.get("adm_div", [])
        city = next(
            (d.get("name") for d in adm_div if d.get("type") == "city"), None
        )

        address_obj = item.get("address", {})
        address = address_obj.get("name") if isinstance(address_obj, dict) else None

        return RawCompanyDTO(
            source="2gis",
            source_id=str(item.get("id", "")),
            name=name,
            domain=domain,
            phone=phone,
            address=address,
            region=city,
            raw=item,
        )
