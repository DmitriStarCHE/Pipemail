import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from outreach.db.models import Company

_cache: dict[Path, tuple[object, float]] = {}
_DEFAULT_DIR = Path("templates_email")
_SUBJECT_RE = re.compile(r"<!--\s*Subject:\s*(.+?)\s*-->", re.IGNORECASE)


class TemplateError(Exception):
    pass


def _find_template(key: str, tdir: Path) -> tuple[Path, bool]:
    """Return (path, is_html). HTML takes precedence over txt."""
    for ext, is_html in ((".html", True), (".txt", False)):
        path = tdir / f"{key}{ext}"
        if path.exists():
            return path, is_html
    raise TemplateError(
        f"Шаблон не найден: {key}.html или {key}.txt в {tdir}. "
        f"Скопируй из {key}.txt.example и заполни."
    )


def render_template(
    template_key: str,
    company: Company,
    *,
    _dir: Path | None = None,
) -> tuple[str, str, bool]:
    """Return (subject, body, is_html) rendered for the given company."""
    tdir = _dir or _DEFAULT_DIR
    tfile, is_html = _find_template(template_key, tdir)

    mtime = tfile.stat().st_mtime
    cached_env, cached_mtime = _cache.get(tfile, (None, -1.0))
    if cached_env is None or mtime != cached_mtime:
        env = Environment(
            loader=FileSystemLoader(str(tdir)),
            undefined=StrictUndefined,
            autoescape=is_html,
        )
        _cache[tfile] = (env, mtime)
    else:
        env = cached_env  # type: ignore[assignment]

    raw = tfile.read_text(encoding="utf-8")

    if is_html:
        m = _SUBJECT_RE.search(raw)
        subject_tpl = m.group(1).strip() if m else f"Предложение — {template_key}"
        body_raw = raw
    else:
        lines = raw.split("\n", 2)
        subject_tpl = lines[0].removeprefix("Subject:").strip() if lines else ""
        body_raw = lines[2] if len(lines) > 2 else ""

    city = company.region
    greeting = f"Здравствуйте, коллеги из г. {city}" if city else "Здравствуйте"

    ctx = {
        "company_name": company.name,
        "city": city or "",
        "greeting": greeting,
    }

    subject = env.from_string(subject_tpl).render(**ctx)
    body = env.from_string(body_raw).render(**ctx)
    return subject, body, is_html
