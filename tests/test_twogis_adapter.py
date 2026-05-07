import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from outreach.adapters.twogis import TwoGISAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "twogis_response.json"


@pytest.fixture()
def twogis_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.mark.asyncio
async def test_fetch_returns_dtos(twogis_fixture: dict) -> None:
    adapter = TwoGISAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = twogis_fixture
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        results = []
        async for dto in adapter.fetch("трубы стальные", region="38", limit=5):
            results.append(dto)

    assert len(results) >= 1
    assert results[0].source == "2gis"
    assert results[0].name != ""


@pytest.mark.asyncio
async def test_fetch_extracts_domain(twogis_fixture: dict) -> None:
    adapter = TwoGISAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = twogis_fixture
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        results = []
        async for dto in adapter.fetch("трубы", limit=10):
            results.append(dto)

    domains = [r.domain for r in results if r.domain]
    for d in domains:
        assert "://" not in d
        assert "/" not in d
