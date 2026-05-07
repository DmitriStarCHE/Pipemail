import pytest


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block accidental real HTTP calls in tests.

    Tests that need real HTTP must explicitly un-patch or use VCR cassettes.
    """
    import httpx

    async def blocked(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError(
            "Real network call blocked in tests — use mock or VCR cassette"
        )

    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
