import pytest
from unittest.mock import AsyncMock, MagicMock

from outreach.dedup.merger import merge_raw_companies


@pytest.mark.asyncio
async def test_merge_by_inn_deduplicates() -> None:
    """Two raw records with same INN produce one Company add call."""
    session = AsyncMock()

    raw1 = MagicMock()
    raw1.inn = "7700000001"
    raw1.name = "Металл Трейд"
    raw1.domain = "metal.ru"
    raw1.region = "Москва"
    raw1.source = "2gis"

    raw2 = MagicMock()
    raw2.inn = "7700000001"
    raw2.name = "МеталлТрейд"
    raw2.domain = None
    raw2.region = "Москва"
    raw2.source = "listorg"

    # Simulate no existing company in DB
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=scalar_result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    await merge_raw_companies([raw1, raw2], session)

    # Only one company should be added (raw2 merges into raw1's company)
    assert session.add.call_count == 1
    added = session.add.call_args[0][0]
    assert added.inn == "7700000001"
    assert "2gis" in added.sources
    assert "listorg" in added.sources


@pytest.mark.asyncio
async def test_merge_by_domain_when_no_inn() -> None:
    """Records without INN are merged by domain."""
    session = AsyncMock()

    raw1 = MagicMock()
    raw1.inn = None
    raw1.name = "Трубная компания"
    raw1.domain = "truba.ru"
    raw1.region = "Екатеринбург"
    raw1.source = "2gis"

    raw2 = MagicMock()
    raw2.inn = None
    raw2.name = "Трубная компания"
    raw2.domain = "truba.ru"
    raw2.region = "Екатеринбург"
    raw2.source = "2gis"

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=scalar_result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    await merge_raw_companies([raw1, raw2], session)

    # Both have same domain, should produce one add
    assert session.add.call_count == 1


@pytest.mark.asyncio
async def test_existing_company_not_duplicated() -> None:
    """If company already exists in DB by INN, no new row is added."""
    session = AsyncMock()

    raw1 = MagicMock()
    raw1.inn = "7700000099"
    raw1.name = "Уже в базе"
    raw1.domain = "existing.ru"
    raw1.region = "Москва"
    raw1.source = "2gis"

    existing_company = MagicMock()
    existing_company.inn = "7700000099"
    existing_company.sources = ["listorg"]
    existing_company.domain = "existing.ru"

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=existing_company)
    session.execute = AsyncMock(return_value=scalar_result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    await merge_raw_companies([raw1], session)

    # No new company added — found existing
    assert session.add.call_count == 0
    assert "2gis" in existing_company.sources
