from datetime import date, datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from outreach.db.models import Company, Send
from outreach.db.session import get_session_factory
from outreach.web.routes import campaigns, companies, sends

app = FastAPI(title="Рассылка труб — Дашборд")
templates = Jinja2Templates(directory="src/outreach/web/templates")

app.include_router(companies.router)
app.include_router(campaigns.router)
app.include_router(sends.router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    factory = get_session_factory()
    today = datetime.now(timezone.utc).date()

    async with factory() as session:
        sent_today = (await session.execute(
            select(func.count(Send.id))
            .where(func.date(Send.sent_at) == today)
            .where(Send.status == "sent")
        )).scalar_one()

        replied = (await session.execute(
            select(func.count(Send.id)).where(Send.status == "replied")
        )).scalar_one()

        bounced = (await session.execute(
            select(func.count(Send.id)).where(Send.status == "bounced")
        )).scalar_one()

        total_companies = (await session.execute(
            select(func.count(Company.id))
        )).scalar_one()

        recent_sends = (await session.execute(
            select(Send).order_by(Send.queued_at.desc()).limit(10)
        )).scalars().all()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "sent_today": sent_today,
        "replied": replied,
        "bounced": bounced,
        "total_companies": total_companies,
        "recent_sends": recent_sends,
    })
