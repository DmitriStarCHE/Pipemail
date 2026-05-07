async def task_classify(ctx: dict) -> None:
    from outreach.cli import _classify

    await _classify(20, None)
