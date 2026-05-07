from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from outreach.db.models import Campaign
from outreach.db.session import get_session_factory

router = APIRouter(prefix="/campaigns")
templates = Jinja2Templates(directory="src/outreach/web/templates")


@router.get("", response_class=HTMLResponse)
async def campaigns_list(request: Request) -> HTMLResponse:
    factory = get_session_factory()
    async with factory() as session:
        campaigns = (await session.execute(select(Campaign))).scalars().all()
    return templates.TemplateResponse("campaigns.html", {
        "request": request,
        "campaigns": campaigns,
    })


@router.post("")
async def campaign_create(
    name: str = Form(...),
    segment: str = Form(...),
    template_key: str = Form(...),
    daily_limit: int = Form(100),
) -> RedirectResponse:
    factory = get_session_factory()
    async with factory() as session:
        campaign = Campaign(
            name=name,
            template_key=template_key,
            target_segment=segment,
            daily_limit=daily_limit,
        )
        session.add(campaign)
        await session.commit()
    return RedirectResponse("/campaigns", status_code=303)


@router.post("/{campaign_id}/toggle")
async def campaign_toggle(campaign_id: int) -> RedirectResponse:
    factory = get_session_factory()
    async with factory() as session:
        campaign = (await session.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )).scalar_one()
        campaign.is_active = not campaign.is_active
        await session.commit()
    return RedirectResponse("/campaigns", status_code=303)
