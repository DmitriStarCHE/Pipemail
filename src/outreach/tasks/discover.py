async def task_discover(ctx: dict) -> None:
    from outreach.cli import _discover
    from outreach.config import get_settings

    settings = get_settings()
    await _discover("2gis", "", "", 200, True)
