async def task_classify(ctx: dict[str, object]) -> None:
    from outreach.cli import _classify

    await _classify(20, None)
