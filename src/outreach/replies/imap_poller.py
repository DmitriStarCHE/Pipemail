import re
from datetime import datetime, timezone

import structlog
from imap_tools import AND, MailBox, MailMessage
from sqlalchemy import select

from outreach.config import get_settings
from outreach.db.models import Email, ImapState, Send
from outreach.db.session import get_session_factory

log = structlog.get_logger(__name__)

_UNSUB_RE = re.compile(r"отписаться|unsubscribe|не присылать", re.IGNORECASE)
_BOUNCE_SENDER_RE = re.compile(r"mailer-daemon|postmaster", re.IGNORECASE)


async def poll_inbox() -> int:
    """Check INBOX for replies/bounces/unsubscribes. Returns count of processed messages."""
    settings = get_settings()
    factory = get_session_factory()
    processed = 0

    # Get last seen UID from DB
    async with factory() as session:
        state_result = await session.execute(select(ImapState).limit(1))
        state = state_result.scalar_one_or_none()
        if state is None:
            state = ImapState(folder="INBOX", last_uid=0)
            session.add(state)
            await session.flush()
            await session.commit()
        last_uid = state.last_uid

    # Connect to IMAP (synchronous imap-tools)
    with MailBox(settings.imap_host, port=settings.imap_port).login(
        settings.imap_user, settings.imap_password
    ) as mailbox:
        mailbox.folder.set("INBOX")
        uid_criteria = f"{last_uid + 1}:*" if last_uid > 0 else "1:*"
        messages = list(
            mailbox.fetch(
                criteria=AND(uid=uid_criteria),
                mark_seen=False,
                bulk=True,
            )
        )

    max_uid = last_uid
    for msg in messages:
        try:
            await _process_message(msg)
            processed += 1
            if msg.uid:
                uid_int = int(msg.uid)
                if uid_int > max_uid:
                    max_uid = uid_int
        except Exception as exc:
            log.error("imap.process_error", uid=msg.uid, error=str(exc))

    # Update last seen UID
    if max_uid > last_uid:
        async with factory() as session:
            state_result = await session.execute(select(ImapState).limit(1))
            state = state_result.scalar_one()
            state.last_uid = max_uid
            await session.commit()

    return processed


async def _process_message(msg: MailMessage) -> None:
    factory = get_session_factory()
    in_reply_to = (msg.headers.get("in-reply-to") or [""])[0]
    references_raw = (msg.headers.get("references") or [""])[0]
    sender = msg.from_ or ""
    body = msg.text or ""

    async with factory() as session:
        matched_send: Send | None = None

        candidates = [in_reply_to, *references_raw.split()]
        for mid in candidates:
            mid = mid.strip()
            if not mid:
                continue
            result = await session.execute(
                select(Send).where(Send.message_id == mid)
            )
            matched_send = result.scalar_one_or_none()
            if matched_send:
                break

        is_bounce = bool(_BOUNCE_SENDER_RE.search(sender.lower()))

        if matched_send:
            if is_bounce:
                matched_send.status = "bounced"
                email_result = await session.execute(
                    select(Email).where(Email.id == matched_send.email_id)
                )
                email_row = email_result.scalar_one_or_none()
                if email_row:
                    email_row.bounced = True
            elif _UNSUB_RE.search(body):
                matched_send.status = "unsubscribed"
                email_result = await session.execute(
                    select(Email).where(Email.id == matched_send.email_id)
                )
                email_row = email_result.scalar_one_or_none()
                if email_row:
                    email_row.unsubscribed = True
            else:
                matched_send.status = "replied"
                matched_send.replied_at = datetime.now(timezone.utc)

            await session.commit()
            log.info("imap.processed", sender=sender, status=matched_send.status)
        else:
            log.debug("imap.no_match", sender=sender, in_reply_to=in_reply_to)
