from collections.abc import AsyncIterator
from typing import Protocol

from pydantic import BaseModel


class RawCompanyDTO(BaseModel):
    source: str
    source_id: str
    inn: str | None = None
    name: str
    domain: str | None = None
    phone: str | None = None
    address: str | None = None
    region: str | None = None
    raw: dict = {}


class Adapter(Protocol):
    name: str

    async def fetch(
        self, query: str, region: str | None = None, limit: int = 100
    ) -> AsyncIterator[RawCompanyDTO]: ...
