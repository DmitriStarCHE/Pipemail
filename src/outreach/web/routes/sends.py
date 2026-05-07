from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from outreach.db.models import Send
from outreach.db.session import get_session_factory

router = APIRouter(prefix="/sends")
templates = Jinja2Templates(directory="src/outreach/web/templates")


@router.get("", response_class=HTMLResponse)
async def sends_list(
    request: Request,
    status: str = "",
    campaign_id: int = 0,
    page: int = 1,
) -> HTMLResponse:
    factory = get_session_factory()
    page_size = 100

    async with factory() as session:
        q = select(Send).order_by(Send.queued_at.desc())
        if status:
            q = q.where(Send.status == status)
        if campaign_id:
            q = q.where(Send.campaign_id == campaign_id)

        sends = (await session.execute(
            q.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

    return templates.TemplateResponse(request, "sends.html", {
        "sends": sends,
        "status": status,
        "campaign_id": campaign_id,
        "page": page,
    })
