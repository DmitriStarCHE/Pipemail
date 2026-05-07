from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from outreach.db.models import Company, Email, Send
from outreach.db.session import get_session_factory

router = APIRouter(prefix="/companies")
templates = Jinja2Templates(directory="src/outreach/web/templates")


@router.get("", response_class=HTMLResponse)
async def companies_list(
    request: Request,
    segment: str = "",
    region: str = "",
    has_email: str = "",
    page: int = 1,
) -> HTMLResponse:
    factory = get_session_factory()
    page_size = 50

    async with factory() as session:
        q = select(Company)
        if segment:
            q = q.where(Company.segment == segment)
        if region:
            q = q.where(Company.region.ilike(f"%{region}%"))
        if has_email == "1":
            q = q.join(Email, Email.company_id == Company.id).distinct()

        companies = (await session.execute(
            q.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

    return templates.TemplateResponse(request, "companies.html", {
        "companies": companies,
        "page": page,
        "page_size": page_size,
        "segment": segment,
        "region": region,
        "has_email": has_email,
    })


@router.get("/{company_id}", response_class=HTMLResponse)
async def company_detail(request: Request, company_id: int) -> HTMLResponse:
    factory = get_session_factory()

    async with factory() as session:
        company = (await session.execute(
            select(Company).where(Company.id == company_id)
        )).scalar_one()

        emails = (await session.execute(
            select(Email).where(Email.company_id == company_id)
        )).scalars().all()

        sends = (await session.execute(
            select(Send).where(Send.company_id == company_id)
            .order_by(Send.queued_at.desc())
        )).scalars().all()

    return templates.TemplateResponse(request, "company_detail.html", {
        "company": company,
        "emails": emails,
        "sends": sends,
    })
