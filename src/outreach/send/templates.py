from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from outreach.db.models import Company

_cache: dict[str, tuple[object, float]] = {}
_DEFAULT_DIR = Path("templates_email")


class TemplateError(Exception):
    pass


def render_template(
    template_key: str,
    company: Company,
    *,
    _dir: Path | None = None,
) -> tuple[str, str]:
    """Return (subject, body) rendered for the given company."""
    tdir = _dir or _DEFAULT_DIR
    tfile = tdir / f"{template_key}.txt"

    if not tfile.exists():
        raise TemplateError(
            f"Шаблон не найден: {tfile}. "
            f"Скопируй из {template_key}.txt.example и заполни."
        )

    mtime = tfile.stat().st_mtime
    cached_env, cached_mtime = _cache.get(template_key, (None, -1.0))
    if cached_env is None or mtime != cached_mtime:
        env = Environment(
            loader=FileSystemLoader(str(tdir)),
            undefined=StrictUndefined,
            autoescape=False,
        )
        _cache[template_key] = (env, mtime)
    else:
        env = cached_env  # type: ignore[assignment]

    raw = tfile.read_text(encoding="utf-8")
    lines = raw.split("\n", 2)
    subject_line = lines[0] if lines else ""
    body_raw = lines[2] if len(lines) > 2 else ""

    subject_tpl = subject_line.removeprefix("Subject:").strip()

    city = company.region
    greeting = f"Здравствуйте, коллеги из г. {city}" if city else "Здравствуйте"

    ctx = {
        "company_name": company.name,
        "city": city or "",
        "greeting": greeting,
    }

    subject = env.from_string(subject_tpl).render(**ctx)
    body = env.from_string(body_raw).render(**ctx)
    return subject, body
