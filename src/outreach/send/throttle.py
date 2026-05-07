import random
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from outreach.config import get_settings
from outreach.db.models import Campaign, Send


def can_send_now(campaign: Campaign) -> bool:
    """Return True if current local time is within configured working hours."""
    settings = get_settings()
    import zoneinfo

    tz = zoneinfo.ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    return settings.work_hours_start <= now.hour < settings.work_hours_end


async def count_sent_today(campaign_id: int, session: AsyncSession) -> int:
    """Return number of emails sent today for this campaign."""
    settings = get_settings()
    import zoneinfo

    tz = zoneinfo.ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_of_day.astimezone(UTC)

    result = await session.execute(
        select(func.count(Send.id))
        .where(Send.campaign_id == campaign_id)
        .where(Send.status == "sent")
        .where(Send.sent_at >= start_utc)
    )
    return result.scalar_one()


def send_delay_seconds() -> float:
    """Return seconds to wait between sends: 30s ± 15s jitter."""
    return 30.0 + random.uniform(-15.0, 15.0)
