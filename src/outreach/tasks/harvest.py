async def task_harvest(ctx: dict[str, object]) -> None:
    from outreach.cli import _harvest

    await _harvest(50, None)
