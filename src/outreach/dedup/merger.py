from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outreach.db.models import Company, RawCompany


async def merge_raw_companies(
    raws: list[RawCompany], session: AsyncSession
) -> None:
    """Merge a batch of RawCompany rows into the companies table.

    Dedup priority: INN → domain → (name + region).
    """
    seen_inns: dict[str, Company] = {}
    seen_domains: dict[str, Company] = {}

    for raw in raws:
        company = await _find_or_build(raw, session, seen_inns, seen_domains)
        if raw.source not in company.sources:
            company.sources = [*company.sources, raw.source]
        if raw.domain and not company.domain:
            company.domain = raw.domain


async def _find_or_build(
    raw: RawCompany,
    session: AsyncSession,
    seen_inns: dict[str, Company],
    seen_domains: dict[str, Company],
) -> Company:
    if raw.inn and raw.inn in seen_inns:
        return seen_inns[raw.inn]
    if raw.domain and raw.domain in seen_domains:
        return seen_domains[raw.domain]

    company: Company | None = None

    if raw.inn:
        result = await session.execute(
            select(Company).where(Company.inn == raw.inn)
        )
        company = result.scalar_one_or_none()

    if company is None and raw.domain:
        result = await session.execute(
            select(Company).where(Company.domain == raw.domain)
        )
        company = result.scalar_one_or_none()

    if company is None:
        company = Company(
            inn=raw.inn,
            name=raw.name,
            domain=raw.domain,
            region=raw.region,
            sources=[],
        )
        session.add(company)
        await session.flush()

    if raw.inn:
        seen_inns[raw.inn] = company
    if raw.domain:
        seen_domains[raw.domain] = company

    return company
