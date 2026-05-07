async def task_check_replies(ctx: dict[str, object]) -> None:
    from outreach.cli import _check_replies

    await _check_replies()
