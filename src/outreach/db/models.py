from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawCompany(Base):
    __tablename__ = "raw_companies"
    __table_args__ = (UniqueConstraint("source", "source_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(128))
    inn: Mapped[str | None] = mapped_column(String(12), index=True)
    name: Mapped[str] = mapped_column(String(512))
    domain: Mapped[str | None] = mapped_column(String(256), index=True)
    phone: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(128))
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    inn: Mapped[str | None] = mapped_column(String(12), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(512))
    domain: Mapped[str | None] = mapped_column(String(256), unique=True, index=True)
    region: Mapped[str | None] = mapped_column(String(128))
    segment: Mapped[str | None] = mapped_column(String(32), index=True)
    products: Mapped[list[str]] = mapped_column(JSONB, default=list)
    classified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    sources: Mapped[list[str]] = mapped_column(JSONB, default=list)


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(256), unique=True)
    is_role: Mapped[bool] = mapped_column(default=False)
    is_free_provider: Mapped[bool] = mapped_column(default=False)
    mx_valid: Mapped[bool | None] = mapped_column(nullable=True)
    bounced: Mapped[bool] = mapped_column(default=False)
    unsubscribed: Mapped[bool] = mapped_column(default=False)
    priority: Mapped[int] = mapped_column(default=50)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    template_key: Mapped[str] = mapped_column(String(64))
    target_segment: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(default=True)
    daily_limit: Mapped[int] = mapped_column(default=100)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Send(Base):
    __tablename__ = "sends"
    __table_args__ = (UniqueConstraint("company_id", "campaign_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"))
    status: Mapped[str] = mapped_column(String(32), index=True)
    message_id: Mapped[str | None] = mapped_column(String(256), unique=True, index=True)
    subject_used: Mapped[str] = mapped_column(String(512))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ImapState(Base):
    """Tracks last seen IMAP UID to avoid reprocessing messages."""

    __tablename__ = "imap_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    folder: Mapped[str] = mapped_column(String(128), default="INBOX")
    last_uid: Mapped[int] = mapped_column(default=0)
