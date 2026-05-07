import json

import httpx
import ollama
import structlog

from outreach.classify.prompts import SYSTEM, USER_TEMPLATE
from outreach.config import get_settings
from outreach.db.models import Company

log = structlog.get_logger(__name__)

_VALID_SEGMENTS = {"producer", "trader", "end_user", "unknown"}
_VALID_PRODUCTS = {
    "НКТ", "обсадная", "профильная", "бесшовная",
    "электросварная", "г/к лист", "х/к лист", "арматура",
}
_MAX_TEXT = 4000


async def classify_company(company: Company) -> tuple[str, list[str]]:
    """Return (segment, products) for a company. Falls back to ('unknown', [])."""
    settings = get_settings()

    text = _get_company_text(company)
    if not text:
        return "unknown", []

    prompt = USER_TEMPLATE.format(name=company.name, text=text[:_MAX_TEXT])
    client = ollama.AsyncClient(host=settings.ollama_url)

    try:
        response = await client.chat(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
            format="json",
        )
        raw: str = response.message.content or ""
        return _parse_response(raw)
    except Exception as exc:
        log.warning("classify.ollama_error", error=str(exc), company=company.name)
        # Retry once with stricter prompt
        try:
            stricter = prompt + "\n\nВажно: ответь ТОЛЬКО валидным JSON, без пояснений."
            response = await client.chat(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": stricter},
                ],
                format="json",
            )
            raw = response.message.content or ""
            return _parse_response(raw)
        except Exception:
            log.error("classify.failed", company=company.name)
            return "unknown", []


def _parse_response(raw: str) -> tuple[str, list[str]]:
    try:
        data = json.loads(raw)
        segment = data.get("segment", "unknown")
        if segment not in _VALID_SEGMENTS:
            segment = "unknown"
        products = [p for p in data.get("products", []) if p in _VALID_PRODUCTS]
        return segment, products
    except json.JSONDecodeError:
        return "unknown", []


def _get_company_text(company: Company) -> str:
    parts = [company.name or ""]
    if company.region:
        parts.append(company.region)
    return " ".join(parts)


async def check_ollama_health() -> bool:
    """Ping Ollama /api/tags; raise RuntimeError if unreachable."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            return resp.status_code == 200
    except Exception as exc:
        raise RuntimeError(f"Ollama недоступен: {exc}") from exc
