async def task_discover(ctx: dict[str, object]) -> None:
    from outreach.cli import _discover

    await _discover("2gis", "", "", 200, True)
