import email.utils
from dataclasses import dataclass
from uuid import uuid4

import aiosmtplib
import structlog

from outreach.config import get_settings

log = structlog.get_logger(__name__)


@dataclass
class SendResult:
    ok: bool
    message_id: str | None = None
    error: str | None = None


async def send_email(to_addr: str, subject: str, body: str) -> SendResult:
    """Send a plain-text email. Returns SendResult with ok/message_id/error."""
    settings = get_settings()
    sender_domain = settings.sender_email.split("@")[-1]
    message_id = f"<{uuid4()}@{sender_domain}>"

    msg_lines = [
        f"From: {settings.sender_name} <{settings.sender_email}>",
        f"To: {to_addr}",
        f"Reply-To: {settings.reply_to}",
        f"Message-ID: {message_id}",
        f"Date: {email.utils.formatdate(localtime=False)}",
        "MIME-Version: 1.0",
        "Content-Type: text/plain; charset=utf-8",
        "Content-Transfer-Encoding: 8bit",
        f"List-Unsubscribe: <mailto:unsubscribe@{sender_domain}?subject=unsubscribe>",
        "List-Unsubscribe-Post: List-Unsubscribe=One-Click",
        f"Subject: {subject}",
        "",
        body,
    ]
    raw = "\r\n".join(msg_lines)

    try:
        if settings.smtp_port == 465:
            await aiosmtplib.send(
                raw,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password,
                use_tls=True,
            )
        else:
            await aiosmtplib.send(
                raw,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password,
                start_tls=True,
            )
        log.info("smtp.sent", to=to_addr, message_id=message_id)
        return SendResult(ok=True, message_id=message_id)
    except Exception as exc:
        log.error("smtp.failed", to=to_addr, error=str(exc))
        return SendResult(ok=False, error=str(exc))
