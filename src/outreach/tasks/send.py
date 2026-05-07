from sqlalchemy import select

from outreach.db.models import Campaign
from outreach.db.session import get_session_factory


async def task_send(ctx: dict) -> None:
    from outreach.cli import _send

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Campaign).where(Campaign.is_active.is_(True))
        )
        campaigns = result.scalars().all()
    for campaign in campaigns:
        await _send(campaign.id, dry_run=False)
