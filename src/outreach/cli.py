import asyncio
from datetime import UTC, datetime
from typing import Annotated

import structlog
import typer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from outreach.config import get_settings
from outreach.db.models import Campaign, Company, Email, RawCompany, Send
from outreach.db.session import get_session_factory
from outreach.logging_setup import configure_logging

app = typer.Typer(help="Инструмент B2B рассылки стальных труб")
campaign_app = typer.Typer()
app.add_typer(campaign_app, name="campaign")

log = structlog.get_logger(__name__)


def _setup() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


# ─── discover ────────────────────────────────────────────────────────────────


@app.command("discover")
def discover(
    source: Annotated[str, typer.Option(help="Источник: 2gis")] = "2gis",
    query: Annotated[str, typer.Option(help="Поисковый запрос")] = "",
    region: Annotated[str, typer.Option(help="ID региона")] = "",
    limit: Annotated[int, typer.Option(help="Максимум компаний")] = 100,
    all_defaults: Annotated[bool, typer.Option("--all-defaults")] = False,
) -> None:
    """Обнаружить компании через выбранный источник и сохранить в raw_companies."""
    _setup()
    asyncio.run(_discover(source, query, region, limit, all_defaults))


async def _discover(
    source: str, query: str, region: str, limit: int, all_defaults: bool
) -> None:
    from outreach.adapters.twogis import TwoGISAdapter
    from outreach.dedup.merger import merge_raw_companies

    settings = get_settings()
    factory = get_session_factory()

    if source == "2gis":
        adapter = TwoGISAdapter(api_key=settings.twogis_api_key)
    else:
        typer.echo(f"Источник '{source}' не поддерживается в v1", err=True)
        raise typer.Exit(1)

    default_query = settings.twogis_default_categories if all_defaults else ["трубы стальные"]
    queries = [query] if query else default_query
    regions_list = [region] if region else (
        [str(r) for r in settings.twogis_default_regions] if all_defaults else [""]
    )

    total = 0
    async with factory() as session:
        for q in queries:
            for reg in regions_list:
                raw_batch: list[RawCompany] = []
                async for dto in adapter.fetch(q, region=reg or None, limit=limit):
                    stmt = pg_insert(RawCompany).values(
                        source=dto.source,
                        source_id=dto.source_id,
                        inn=dto.inn,
                        name=dto.name,
                        domain=dto.domain,
                        phone=dto.phone,
                        address=dto.address,
                        region=dto.region,
                        raw=dto.raw,
                    ).on_conflict_do_nothing(index_elements=["source", "source_id"])
                    await session.execute(stmt)
                    raw_batch.append(
                        RawCompany(
                            source=dto.source,
                            source_id=dto.source_id,
                            inn=dto.inn,
                            name=dto.name,
                            domain=dto.domain,
                            phone=dto.phone,
                            address=dto.address,
                            region=dto.region,
                            raw=dto.raw,
                        )
                    )
                    total += 1

                await merge_raw_companies(raw_batch, session)
                await session.commit()

    typer.echo(f"Обнаружено и сохранено: {total} компаний")


# ─── harvest ─────────────────────────────────────────────────────────────────


@app.command("harvest")
def harvest(
    limit: Annotated[int, typer.Option(help="Максимум компаний")] = 50,
    company_id: Annotated[int | None, typer.Option(help="ID конкретной компании")] = None,
) -> None:
    """Собрать email-адреса с сайтов компаний."""
    _setup()
    asyncio.run(_harvest(limit, company_id))


async def _harvest(limit: int, company_id: int | None) -> None:
    from outreach.harvest.extractor import extract_emails
    from outreach.harvest.scraper import scrape_domain
    from outreach.harvest.verifier import has_valid_mx

    factory = get_session_factory()
    harvested = 0

    async with factory() as session:
        if company_id:
            result = await session.execute(
                select(Company).where(Company.id == company_id)
            )
            companies = [result.scalar_one()]
        else:
            result = await session.execute(
                select(Company)
                .where(Company.domain.isnot(None))
                .outerjoin(Email, Email.company_id == Company.id)
                .where(Email.id.is_(None))
                .limit(limit)
            )
            companies = list(result.scalars().all())

        for company in companies:
            if not company.domain:
                continue
            typer.echo(f"Обрабатываем: {company.name} ({company.domain})")
            pages = await scrape_domain(company.domain)
            combined_html = " ".join(pages)
            if not combined_html:
                continue

            email_results = extract_emails(combined_html, company.domain)
            for er in email_results:
                _, _, domain = er.email.partition("@")
                mx = await has_valid_mx(domain)
                stmt = pg_insert(Email).values(
                    company_id=company.id,
                    email=er.email,
                    is_role=er.is_role,
                    is_free_provider=er.is_free_provider,
                    mx_valid=mx,
                    priority=er.priority,
                ).on_conflict_do_nothing(index_elements=["email"])
                await session.execute(stmt)
            await session.commit()
            harvested += len(email_results)

    typer.echo(f"Собрано адресов: {harvested}")


# ─── classify ────────────────────────────────────────────────────────────────


@app.command("classify")
def classify(
    limit: Annotated[int, typer.Option(help="Максимум компаний")] = 20,
    company_id: Annotated[int | None, typer.Option(help="ID конкретной компании")] = None,
) -> None:
    """Классифицировать компании по сегментам через Ollama."""
    _setup()
    asyncio.run(_classify(limit, company_id))


async def _classify(limit: int, company_id: int | None) -> None:
    from outreach.classify.llm import classify_company

    factory = get_session_factory()

    async with factory() as session:
        if company_id:
            result = await session.execute(
                select(Company).where(Company.id == company_id)
            )
            companies = [result.scalar_one()]
        else:
            result = await session.execute(
                select(Company).where(Company.segment.is_(None)).limit(limit)
            )
            companies = list(result.scalars().all())

        for company in companies:
            typer.echo(f"Классифицируем: {company.name}")
            segment, products = await classify_company(company)
            company.segment = segment
            company.products = products
            company.classified_at = datetime.now(UTC)

        await session.commit()

    typer.echo(f"Классифицировано: {len(companies)} компаний")


# ─── campaign ────────────────────────────────────────────────────────────────


@campaign_app.command("create")
def campaign_create(
    name: Annotated[str, typer.Option(help="Название кампании")],
    segment: Annotated[str, typer.Option(help="Сегмент: trader | end_user")],
    template: Annotated[str, typer.Option(help="Ключ шаблона: trader | end_user")],
    daily_limit: Annotated[int, typer.Option(help="Лимит в день")] = 100,
) -> None:
    """Создать новую кампанию рассылки."""
    _setup()
    if segment not in ("trader", "end_user"):
        typer.echo("Сегмент должен быть 'trader' или 'end_user'", err=True)
        raise typer.Exit(1)
    asyncio.run(_campaign_create(name, segment, template, daily_limit))


async def _campaign_create(
    name: str, segment: str, template: str, daily_limit: int
) -> None:
    factory = get_session_factory()
    async with factory() as session:
        campaign = Campaign(
            name=name,
            template_key=template,
            target_segment=segment,
            daily_limit=daily_limit,
        )
        session.add(campaign)
        await session.flush()
        campaign_id = campaign.id
        await session.commit()
    typer.echo(f"Кампания создана, ID: {campaign_id}")


# ─── send ─────────────────────────────────────────────────────────────────────


@app.command("send")
def send_cmd(
    campaign_id: Annotated[int, typer.Option(help="ID кампании")] = 0,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    all_active: Annotated[bool, typer.Option("--all-active")] = False,
) -> None:
    """Отправить письма по активной кампании."""
    _setup()
    if all_active:
        asyncio.run(_send_all_active(dry_run))
    elif campaign_id:
        asyncio.run(_send(campaign_id, dry_run))
    else:
        typer.echo("Укажите --campaign-id или --all-active", err=True)
        raise typer.Exit(1)


async def _send_all_active(dry_run: bool) -> None:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Campaign).where(Campaign.is_active.is_(True))
        )
        campaigns = result.scalars().all()
    for campaign in campaigns:
        await _send(campaign.id, dry_run)


async def _send(campaign_id: int, dry_run: bool) -> None:
    from outreach.send.smtp import send_email
    from outreach.send.templates import render_template
    from outreach.send.throttle import can_send_now, count_sent_today, send_delay_seconds

    factory = get_session_factory()

    async with factory() as session:
        result = await session.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one()

        sent_today = await count_sent_today(campaign_id, session)
        remaining = campaign.daily_limit - sent_today

        if remaining <= 0:
            typer.echo("Дневной лимит исчерпан")
            return

        if not can_send_now(campaign):
            typer.echo("Не рабочее время — отправка отложена")
            return

        subq = select(Send.company_id).where(Send.campaign_id == campaign_id)
        result = await session.execute(
            select(Company, Email)
            .join(Email, Email.company_id == Company.id)
            .where(Company.segment == campaign.target_segment)
            .where(Email.mx_valid.is_(True))
            .where(Email.bounced.is_(False))
            .where(Email.unsubscribed.is_(False))
            .where(Company.id.not_in(subq))
            .order_by(Company.created_at.asc(), Email.priority.asc())
            .limit(remaining)
        )
        rows = result.all()

        sent = 0
        for company, email in rows:
            subject, body, is_html = render_template(campaign.template_key, company)
            if dry_run:
                typer.echo(f"[dry-run] → {email.email} | {subject}")
                continue

            await asyncio.sleep(send_delay_seconds())
            send_result = await send_email(email.email, subject, body, is_html=is_html)
            status = "sent" if send_result.ok else "failed"

            send_row = Send(
                campaign_id=campaign_id,
                company_id=company.id,
                email_id=email.id,
                status=status,
                message_id=send_result.message_id,
                subject_used=subject,
                error=send_result.error,
            )
            if status == "sent":
                send_row.sent_at = datetime.now(UTC)
            session.add(send_row)
            await session.commit()
            sent += 1
            typer.echo(f"Отправлено: {email.email}")

        if not dry_run:
            typer.echo(f"Итого отправлено: {sent}")


# ─── replies ──────────────────────────────────────────────────────────────────


@app.command("check-replies")
def check_replies() -> None:
    """Проверить входящие ответы через IMAP (однократно)."""
    _setup()
    asyncio.run(_check_replies())


@app.command("poll-replies")
def poll_replies() -> None:
    """Непрерывно проверять ответы (интервал 60 минут)."""
    _setup()

    async def _loop() -> None:
        while True:
            await _check_replies()
            typer.echo("Следующая проверка через 60 минут...")
            await asyncio.sleep(3600)

    asyncio.run(_loop())


async def _check_replies() -> None:
    from outreach.replies.imap_poller import poll_inbox

    found = await poll_inbox()
    typer.echo(f"Обработано ответов: {found}")


if __name__ == "__main__":
    app()
