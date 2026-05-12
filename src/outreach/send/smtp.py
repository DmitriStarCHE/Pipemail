import email.utils
import re
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import unescape
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


def _html_to_plain(html: str) -> str:
    """Strip HTML tags to generate a readable plain-text fallback."""
    text = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<(?:br|p|div|h[1-6]|li|tr|td)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def send_email(
    to_addr: str,
    subject: str,
    body: str,
    *,
    is_html: bool = False,
) -> SendResult:
    """Send email (plain-text or HTML multipart/alternative). Returns SendResult."""
    settings = get_settings()
    sender_domain = settings.sender_email.split("@")[-1]
    message_id = f"<{uuid4()}@{sender_domain}>"
    unsubscribe = f"<mailto:unsubscribe@{sender_domain}?subject=unsubscribe>"

    if is_html:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.sender_name} <{settings.sender_email}>"
        msg["To"] = to_addr
        msg["Reply-To"] = settings.reply_to
        msg["Message-ID"] = message_id
        msg["Date"] = email.utils.formatdate(localtime=False)
        msg["List-Unsubscribe"] = unsubscribe
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        msg["Subject"] = subject
        msg.attach(MIMEText(_html_to_plain(body), "plain", "utf-8"))
        msg.attach(MIMEText(body, "html", "utf-8"))
        raw = msg.as_string()
    else:
        msg_lines = [
            f"From: {settings.sender_name} <{settings.sender_email}>",
            f"To: {to_addr}",
            f"Reply-To: {settings.reply_to}",
            f"Message-ID: {message_id}",
            f"Date: {email.utils.formatdate(localtime=False)}",
            "MIME-Version: 1.0",
            "Content-Type: text/plain; charset=utf-8",
            "Content-Transfer-Encoding: 8bit",
            f"List-Unsubscribe: {unsubscribe}",
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
