import json

import httpx
import ollama
import structlog
from openai import AsyncOpenAI

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

_MsgList = list[dict[str, str]]


async def classify_company(company: Company) -> tuple[str, list[str]]:
    """Return (segment, products) for a company. Falls back to ('unknown', [])."""
    settings = get_settings()
    text = _get_company_text(company)
    if not text:
        return "unknown", []

    prompt = USER_TEMPLATE.format(name=company.name, text=text[:_MAX_TEXT])
    messages: _MsgList = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]

    if settings.llm_backend == "openai":
        return await _classify_openai(messages, company.name)
    return await _classify_ollama(messages, company.name)


async def _classify_openai(messages: _MsgList, company_name: str) -> tuple[str, list[str]]:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    try:
        resp = await client.chat.completions.create(  # type: ignore[call-overload]
            model=settings.llm_model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        return _parse_response(raw)
    except Exception as exc:
        log.warning("classify.openai_error", error=str(exc), company=company_name)
        try:
            suffix = "\n\nВажно: ответь ТОЛЬКО валидным JSON."
            stricter = messages[:-1] + [
                {"role": "user", "content": messages[-1]["content"] + suffix}
            ]
            resp = await client.chat.completions.create(  # type: ignore[call-overload]
                model=settings.llm_model,
                messages=stricter,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or ""
            return _parse_response(raw)
        except Exception:
            log.error("classify.openai_failed", company=company_name)
            return "unknown", []


async def _classify_ollama(messages: _MsgList, company_name: str) -> tuple[str, list[str]]:
    settings = get_settings()
    client = ollama.AsyncClient(host=settings.ollama_url)
    try:
        response = await client.chat(
            model=settings.llm_model,
            messages=messages,
            format="json",
        )
        raw: str = response.message.content or ""
        return _parse_response(raw)
    except Exception as exc:
        log.warning("classify.ollama_error", error=str(exc), company=company_name)
        try:
            suffix = "\n\nВажно: ответь ТОЛЬКО валидным JSON, без пояснений."
            stricter = messages[:-1] + [
                {"role": "user", "content": messages[-1]["content"] + suffix}
            ]
            response = await client.chat(
                model=settings.llm_model,
                messages=stricter,
                format="json",
            )
            raw = response.message.content or ""
            return _parse_response(raw)
        except Exception:
            log.error("classify.ollama_failed", company=company_name)
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
    """Ping LLM backend. For openai backend always returns True."""
    settings = get_settings()
    if settings.llm_backend == "openai":
        return True
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            return resp.status_code == 200
    except Exception as exc:
        raise RuntimeError(f"Ollama недоступен: {exc}") from exc
