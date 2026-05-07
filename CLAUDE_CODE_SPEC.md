# Pipe Sales Outreach Tool — Specification for Claude Code

> **Note for Claude Code:** Read this entire document before starting. Then read `USER_CHECKLIST.md` to understand the manual setup the operator will do in parallel. Implement in phases, in order. Don't skip ahead. After each phase, run tests and ensure CLI commands for that phase work end-to-end.
>
> **Operator language:** Russian (RU). All user-facing strings (CLI output, logs, error messages, dashboard text) must be in Russian. All code, comments, docstrings, commit messages — English.

---

## 1. Project overview

Build a B2B email outreach tool for a sole developer in Russia who sells **steel pipes** (НКТ, обсадные, общего назначения). The tool finds Russian companies that buy pipes (traders + end users), harvests their email addresses, classifies them, and sends templated commercial proposals at low volume (~100/day) to maintain SMTP deliverability.

**Operator profile:**
- Solo developer, Linux user (CachyOS, Arch), Python 3.12
- Hardware: Ryzen 7 + 32GB RAM + GTX 1660 Super (6GB VRAM)
- No VPS — everything runs on home PC
- Owns one sender domain; uses free email hosting (Mail.ru для Бизнеса or Yandex 360)

**Hard constraints:**
- Volume cap: **100 emails/day**
- Budget: minimal — only ~200₽/year for domain
- Plain-text emails only (no HTML, no tracking pixels in v1)
- No inbox pool / domain rotation in v1 — single sender domain
- No paid SMTP relays — direct SMTP via the operator's mail provider

---

## 2. Goals

1. Discover Russian companies via multiple sources (2GIS first; list-org, Yandex, ЕИС as future adapters)
2. Harvest emails from company websites
3. Classify each company into a segment (`producer` | `trader` | `end_user` | `unknown`)
4. Send templated emails for two segments only: `trader` and `end_user`. **Never send to producers** — they're competitors.
5. Detect replies via IMAP and stop further sends to that company
6. Provide a local FastAPI+HTMX dashboard for observability
7. Architecture must be modular: adding new sources / templates / segments later must not require core rewrites

---

## 3. Tech stack (lock these)

- Python 3.12
- PostgreSQL 16 (via Docker)
- Redis 7 (via Docker)
- httpx (sync + async, HTTP client)
- selectolax (fast HTML parsing)
- playwright (only when JS rendering is unavoidable; not in v1 unless explicitly needed)
- pydantic v2 + pydantic-settings
- SQLAlchemy 2.x (async) + asyncpg
- alembic (migrations)
- arq (async task queue)
- FastAPI + Jinja2 + HTMX (dashboard)
- ollama-python (LLM client; operator runs Ollama separately)
- imap-tools (reply detection)
- aiosmtplib (sending)
- dnspython (MX checks)
- typer (CLI)
- python-dotenv (loaded by pydantic-settings)
- structlog (JSON logs)
- ruff + mypy --strict
- pytest + pytest-asyncio + VCR.py

---

## 4. Project structure

```
pipes-outreach/
├── pyproject.toml
├── docker-compose.yml          # postgres + redis
├── .env.example
├── .gitignore
├── README.md                   # short, points to USER_CHECKLIST.md
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── src/
│   └── outreach/
│       ├── __init__.py
│       ├── config.py           # pydantic-settings
│       ├── logging_setup.py    # structlog config
│       ├── db/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   └── session.py
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py         # Protocol + DTO
│       │   ├── twogis.py       # FULLY IMPLEMENTED in v1
│       │   ├── listorg.py      # stub for v2
│       │   ├── yandex.py       # stub for v2
│       │   └── eis.py          # stub for v3
│       ├── harvest/
│       │   ├── __init__.py
│       │   ├── scraper.py
│       │   ├── extractor.py
│       │   └── verifier.py
│       ├── classify/
│       │   ├── __init__.py
│       │   ├── llm.py
│       │   └── prompts.py
│       ├── send/
│       │   ├── __init__.py
│       │   ├── templates.py
│       │   ├── smtp.py
│       │   └── throttle.py
│       ├── replies/
│       │   ├── __init__.py
│       │   └── imap_poller.py
│       ├── dedup/
│       │   ├── __init__.py
│       │   └── merger.py       # raw_companies → companies
│       ├── tasks/              # arq tasks
│       │   ├── __init__.py
│       │   ├── worker.py       # arq WorkerSettings
│       │   ├── discover.py
│       │   ├── harvest.py
│       │   ├── classify.py
│       │   ├── send.py
│       │   └── check_replies.py
│       ├── cli.py              # typer entry point
│       └── web/
│           ├── __init__.py
│           ├── app.py
│           ├── routes/
│           └── templates/
├── templates_email/            # email body templates (RU)
│   ├── trader.txt.example
│   └── end_user.txt.example
├── deploy/
│   └── systemd/                # user units for cron-less scheduling
│       ├── outreach-discover.service
│       ├── outreach-discover.timer
│       └── ... (one per task)
└── tests/
    ├── conftest.py
    ├── fixtures/               # VCR cassettes, sample HTML
    ├── test_extractor.py
    ├── test_dedup.py
    ├── test_templates.py
    └── test_twogis_adapter.py
```

---

## 5. Database schema

SQLAlchemy 2.x async style. Generate via alembic, don't auto-create.

```python
class RawCompany(Base):
    __tablename__ = "raw_companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(128))
    inn: Mapped[str | None] = mapped_column(String(12), index=True)
    name: Mapped[str] = mapped_column(String(512))
    domain: Mapped[str | None] = mapped_column(String(256), index=True)
    phone: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(128))
    raw: Mapped[dict] = mapped_column(JSONB, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())
    __table_args__ = (UniqueConstraint("source", "source_id"),)

class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    inn: Mapped[str | None] = mapped_column(String(12), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(512))
    domain: Mapped[str | None] = mapped_column(String(256), unique=True, index=True)
    region: Mapped[str | None] = mapped_column(String(128))
    segment: Mapped[str | None] = mapped_column(String(32), index=True)
    products: Mapped[list] = mapped_column(JSONB, default=list)
    classified_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    sources: Mapped[list[str]] = mapped_column(JSONB, default=list)  # ['2gis', 'listorg']

class Email(Base):
    __tablename__ = "emails"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True)
    is_role: Mapped[bool] = mapped_column(default=False)
    is_free_provider: Mapped[bool] = mapped_column(default=False)
    mx_valid: Mapped[bool | None]
    bounced: Mapped[bool] = mapped_column(default=False)
    unsubscribed: Mapped[bool] = mapped_column(default=False)
    priority: Mapped[int] = mapped_column(default=50)  # lower = higher priority

class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    template_key: Mapped[str] = mapped_column(String(64))  # 'trader' | 'end_user'
    target_segment: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(default=True)
    daily_limit: Mapped[int] = mapped_column(default=100)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

class Send(Base):
    __tablename__ = "sends"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"))
    status: Mapped[str] = mapped_column(String(32), index=True)  # queued|sent|bounced|replied|failed|unsubscribed
    message_id: Mapped[str | None] = mapped_column(String(256), unique=True, index=True)
    subject_used: Mapped[str] = mapped_column(String(512))
    error: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(server_default=func.now())
    sent_at: Mapped[datetime | None]
    replied_at: Mapped[datetime | None]
    __table_args__ = (UniqueConstraint("company_id", "campaign_id"),)
```

Indexes: add btree on `sends.status`, `sends.sent_at`, `companies.segment`, composite (`company_id`, `campaign_id`).

---

## 6. Phase 1 — Discovery (adapter pattern)

### 6.1 Base
```python
# src/outreach/adapters/base.py
from typing import Protocol, AsyncIterator
from pydantic import BaseModel

class RawCompanyDTO(BaseModel):
    source: str
    source_id: str
    inn: str | None = None
    name: str
    domain: str | None = None
    phone: str | None = None
    address: str | None = None
    region: str | None = None
    raw: dict = {}

class Adapter(Protocol):
    name: str
    async def fetch(
        self, query: str, region: str | None = None, limit: int = 100
    ) -> AsyncIterator[RawCompanyDTO]: ...
```

### 6.2 TwoGISAdapter (full implementation)
- API key from `TWOGIS_API_KEY` env
- Endpoint: `https://catalog.api.2gis.com/3.0/items`
- Request fields: `items.org,items.contact_groups,items.point,items.adm_div,items.region_id`
- Default categories (configurable): `["трубы стальные", "металлопрокат", "нефтегазовое оборудование", "трубопроводная арматура"]`
- Default regions (configurable): `[1, 2, 4, 38, 70]` (Москва, СПб, Екатеринбург, Челябинск, etc.)
- Rate limit: 1 request per 0.5 sec (use `asyncio.sleep`)
- Pagination: respect `total` field, stop when reached or `limit` hit
- Map `contact_groups[].contacts[]` where `type='website'` → `domain` (strip protocol/path)
- Save to `raw_companies` with `ON CONFLICT (source, source_id) DO NOTHING`

### 6.3 Other adapters
`listorg.py`, `yandex.py`, `eis.py` — implement Protocol with `NotImplementedError("Phase 2/3")`. Add detailed docstring with implementation notes (what URL, what fields, expected pitfalls). Don't try to implement them in v1.

### 6.4 CLI
```
outreach discover --source 2gis --query "трубы" --region 1 --limit 100
outreach discover --source 2gis --all-defaults    # uses config defaults
```

---

## 7. Phase 2 — Email harvesting

### 7.1 Scraper (`harvest/scraper.py`)
- httpx async client, timeout=10s, max_redirects=3, http2=True
- User-Agent: realistic Chrome string (rotate from a small pool of 3-4)
- Try paths in order: `["", "/contacts", "/contact", "/kontakty", "/about", "/o-kompanii", "/o-nas", "/svyaz", "/contacts/"]`
- Per-domain rate limit: 1 request per 3 sec
- On 403/Cloudflare/SSL error → log and skip; don't retry, don't fall back to Playwright in v1
- Strip scripts/styles before passing to extractor

### 7.2 Extractor (`harvest/extractor.py`)
- Email regex: `re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")`
- Extract from:
  1. `<a href="mailto:...">` (highest confidence, `priority=10`)
  2. Plain text after deobfuscation (`priority=50`)
- Deobfuscation: handle `[at]`, `(at)`, `[собака]`, `(собака)`, ` AT `, `[dot]`, `(точка)`, ` DOT `, ` точка `, `&#64;`, `&commat;`. Case-insensitive.
- Drop list (regex match on local part): `^(noreply|no-reply|webmaster|postmaster|admin|abuse|hostmaster|root|mailer-daemon)$`
- Mark `is_role=True` if local part in: `{info, sales, office, hello, contact, support, sekretar, secretary, zakupki, snab, omts, prodaja, prodazhi}`
- Detect free providers: domain in `{mail.ru, gmail.com, yandex.ru, yandex.com, yahoo.com, rambler.ru, list.ru, bk.ru, inbox.ru}` → flag `is_free_provider=True`
- Reorder emails by priority (asc), keep top 3 per company
- Priority computation:
  - mailto + role match {zakup*, snab*}: 10
  - mailto + sales/info: 20
  - text + zakup*/snab*: 30
  - text + sales/info: 40
  - other: 50
  - free provider: +20

### 7.3 Verifier (`harvest/verifier.py`)
- MX check via `dnspython` (async wrapper using `dns.asyncresolver`)
- In-memory TTL cache 24h, keyed by domain
- **Do not implement SMTP probing.** That's a footgun on residential IP.

### 7.4 CLI
```
outreach harvest --limit 50      # picks N companies without emails, scrapes
outreach harvest --company-id 123
```

---

## 8. Phase 3 — Classification (Ollama)

### 8.1 Setup
- Ollama URL from `OLLAMA_URL` env (default `http://localhost:11434`)
- Model from `LLM_MODEL` env (default `qwen2.5:7b-instruct-q4_K_M`)
- Operator runs Ollama and pulls model separately (instructions in `USER_CHECKLIST.md`)
- Health check at startup: ping `/api/tags`, fail loudly if Ollama unreachable

### 8.2 Prompt (in `classify/prompts.py`)
```python
SYSTEM = """Ты классификатор B2B-компаний в металлургии РФ. \
Тебе дан текст с сайта компании. Определи сегмент и продукты. \
Отвечай СТРОГО валидным JSON без комментариев и markdown-обёрток."""

USER_TEMPLATE = """Текст сайта компании "{name}":

{text}

Верни JSON в формате:
{{
  "segment": "producer" | "trader" | "end_user" | "unknown",
  "products": [список из: "НКТ", "обсадная", "профильная", "бесшовная", "электросварная", "г/к лист", "х/к лист", "арматура"]
}}

Где:
- producer = производит трубы или прокат самостоятельно
- trader = перепродаёт металлопрокат, дилер, склад, торговый дом
- end_user = покупает трубы для своих нужд (нефтегаз, стройка, ЖКХ, машиностроение)
- unknown = недостаточно информации"""
```

### 8.3 Logic (`classify/llm.py`)
- Truncate input text to ~4000 chars (concatenate homepage + about page text, strip HTML, collapse whitespace)
- Call Ollama with `format="json"` parameter (forces valid JSON output)
- Parse response; on JSON parse failure retry once with stricter prompt
- On total failure: set `segment='unknown'`, `products=[]`
- Update `companies.segment`, `companies.products`, `companies.classified_at`

### 8.4 CLI
```
outreach classify --limit 20
outreach classify --company-id 123
```

---

## 9. Phase 4 — Template engine

### 9.1 Format
- Files: `templates_email/{template_key}.txt`
- First line: `Subject: <тема>`
- Empty line
- Body (Jinja2)
- Available variables: `company_name`, `city`, `greeting` (auto: «Здравствуйте» if no city else `f"Здравствуйте, коллеги из г. {city}"`)
- Use Jinja2 `StrictUndefined` — fail loud on missing variables

### 9.2 Example files
Provide `templates_email/trader.txt.example` and `templates_email/end_user.txt.example` with REPLACE-ME placeholders. **Do not** provide working content — operator writes their own.

```
Subject: Поставки стальных труб — [REPLACE: краткое предложение]

{{ greeting }}!

Меня зовут [REPLACE: Имя], [REPLACE: должность] в [REPLACE: название компании/ИП].

[REPLACE: 2-3 предложения о вашем предложении — ассортимент, география, условия поставки]

Если интересно — отвечу на это письмо с актуальным прайсом и условиями.

С уважением,
[REPLACE: Имя Фамилия]
[REPLACE: телефон]
[REPLACE: сайт]
ИНН: [REPLACE: ИНН]

---
Если рассылка вам неинтересна, ответьте «Отписаться» — больше писать не будем.
```

### 9.3 Template loader (`send/templates.py`)
- Load file, split on first blank line
- Parse `Subject:` from first line
- Compile body with Jinja2
- Cache compiled templates in memory; reload on file mtime change

---

## 10. Phase 5 — Sender

### 10.1 SMTP (`send/smtp.py`)
- aiosmtplib, TLS (port 465 implicit or 587 STARTTLS — config-driven)
- Credentials from .env: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SENDER_NAME`, `SENDER_EMAIL`, `REPLY_TO`
- Generate `Message-ID` per send: `f"<{uuid4()}@{sender_domain}>"`, store in `sends.message_id`
- Required headers: `From`, `Reply-To`, `Message-ID`, `Date`, `MIME-Version: 1.0`, `Content-Type: text/plain; charset=utf-8`, `Content-Transfer-Encoding: 8bit`, `List-Unsubscribe: <mailto:unsubscribe@{domain}?subject=unsubscribe>`, `List-Unsubscribe-Post: List-Unsubscribe=One-Click`
- **Plain text body only** (no multipart, no HTML)

### 10.2 Throttle (`send/throttle.py`)
- Read `Campaign.daily_limit` (default 100)
- Min delay between sends: 30 sec, jitter ±15 sec
- Working hours: from `WORK_HOURS_START` to `WORK_HOURS_END` in `TIMEZONE` (config defaults: 9-18, Asia/Yekaterinburg)
- Outside working hours: skip and log
- Skip if: company already has a `Send` row for this campaign (UniqueConstraint guarantees)
- Skip if: email is `bounced=True` or `unsubscribed=True`

### 10.3 Selection logic
For a given active campaign:
1. Find companies where `segment == campaign.target_segment`
2. With at least one valid email (`mx_valid=True`, `bounced=False`, `unsubscribed=False`)
3. Without an existing `Send` for this campaign
4. Order by: `companies.created_at` ASC (oldest first; gives breadth)
5. For each, pick highest-priority email
6. Render template with company context
7. Insert `Send` row with `status='queued'` (in transaction)
8. Send via SMTP; on success → `status='sent'`, `sent_at=now()`
9. On exception → `status='failed'`, `error=str(e)`

### 10.4 CLI
```
outreach campaign create --name "Трейдеры Q1" --segment trader --template trader
outreach send --campaign-id 1 --dry-run    # prints what would send, no SMTP
outreach send --campaign-id 1              # actual send up to daily_limit
```

---

## 11. Phase 6 — Reply detection

### 11.1 IMAP poller (`replies/imap_poller.py`)
- imap-tools, connect to `IMAP_HOST:IMAP_PORT` (default Mail.ru: imap.mail.ru:993)
- Folder: `INBOX`
- Strategy: **don't use IDLE in v1** (some providers flaky). Just poll on schedule.
- For each new message (track last seen UID in a small state file or DB row):
  1. Check `In-Reply-To` and `References` headers — match against `sends.message_id`
  2. If match: set `sends.status='replied'`, `sends.replied_at=now()`
  3. If sender domain is in known bouncers (`mailer-daemon@`, `postmaster@`) and body contains the recipient address → mark that `Email.bounced=True`, set corresponding `sends.status='bounced'`
  4. If body contains "отписаться", "unsubscribe", "не присылать" — find sender's email, mark `Email.unsubscribed=True`
- Don't mark messages as read (`mark_seen=False`)
- Idempotent: re-running shouldn't double-count (track processed UIDs)

### 11.2 CLI
```
outreach check-replies            # one shot
outreach poll-replies             # loop forever, 60-min interval
```

---

## 12. Phase 7 — Dashboard (FastAPI + HTMX)

### 12.1 Setup
- FastAPI, bind to `127.0.0.1:8000` only (no auth, local-only)
- Jinja2 templates in `web/templates/`
- HTMX 1.9+ via CDN
- Pico.css for styling (no other CSS framework)
- All UI strings in Russian

### 12.2 Pages
- `GET /` — dashboard: today's stats (sends/replies/bounces), queue depth, last 10 events
- `GET /companies` — paginated table with filters (segment, region, has_email, status). HTMX-powered filters (no full reload).
- `GET /companies/{id}` — detail: sources, emails list, send history
- `GET /campaigns` — list + create form (HTMX)
- `POST /campaigns` — create
- `POST /campaigns/{id}/toggle` — activate/deactivate
- `GET /sends` — log, filterable by status/date/campaign

### 12.3 No auth, no JS frameworks
This is a single-user local tool. Don't add login, sessions, React, Vue, or Alpine.

---

## 13. Phase 8 — Scheduling

### 13.1 arq worker (`tasks/worker.py`)
- WorkerSettings with cron jobs:
  - `cron(hour=6)` — discover (only if `companies` count below threshold)
  - `cron(hour=7)` — harvest
  - `cron(hour=8)` — classify
  - `cron(hour=10)` — send (per active campaign)
  - `cron(minute=0)` — check_replies (every hour)
- Operator runs `arq outreach.tasks.worker.WorkerSettings` manually or via systemd

### 13.2 systemd user units (`deploy/systemd/`)
Provide alternative to arq: discrete one-shot units + timers. Operator can choose either approach.

```ini
# outreach-send.service
[Unit]
Description=Outreach send
[Service]
Type=oneshot
WorkingDirectory=%h/projects/pipes-outreach
ExecStart=%h/projects/pipes-outreach/.venv/bin/outreach send --all-active
```

```ini
# outreach-send.timer
[Unit]
Description=Run outreach send daily
[Timer]
OnCalendar=Mon..Fri 10:00
Persistent=true
[Install]
WantedBy=timers.target
```

Provide units for: discover, harvest, classify, send, check-replies.

---

## 14. Coding conventions

- Type hints everywhere; mypy `--strict`
- ruff with: `select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "C4"]`, line-length 100
- Async wherever IO is involved
- All external data (API responses, .env, config files) through Pydantic v2 models
- No global state; pass session/client via dependency injection
- structlog with JSON renderer; log levels via env (`LOG_LEVEL=INFO` default)
- Secrets only in `.env`, loaded by pydantic-settings, never in code or logs
- Migrations via alembic; never `Base.metadata.create_all()` in production paths
- All user-facing strings (CLI, logs, dashboard) in Russian
- All internals (code, comments, docstrings, commits, errors raised) in English

---

## 15. What NOT to do

- ❌ Don't implement scraping for sources outside the listed adapters (no Yandex Maps without API, no Rusprofile)
- ❌ Don't add tracking pixels or click tracking
- ❌ Don't implement SMTP probing for verification
- ❌ Don't add Cloudflare-bypass logic (cloudscraper, FlareSolverr, etc.)
- ❌ Don't make IMAP poller mark messages as read
- ❌ Don't send without `List-Unsubscribe` header and unsubscribe footer in template
- ❌ Don't store SMTP password in code, only `.env`
- ❌ Don't introduce React, Vue, Alpine, or any JS framework — HTMX only
- ❌ Don't introduce Celery — arq is sufficient
- ❌ Don't include `producer` segment in any campaign's target — it's competitors
- ❌ Don't implement an inbox pool / domain rotation in v1
- ❌ Don't auto-fill template content; let operator write their own

---

## 16. Testing

- **Unit tests:** extractor (regex + deobfuscation edge cases), dedup merger, template rendering, throttle logic
- **Integration:** 2GIS adapter with VCR.py cassettes recorded once and committed
- **Smoke test:** seed 5 fake companies, run full pipeline (discover→harvest→classify→send→reply), assert end states
- **Don't test live:** SMTP, IMAP, Ollama. Mock all three.
- Coverage target: 70%+ on core modules (`extractor`, `dedup`, `templates`, `throttle`)
- pytest config in `pyproject.toml`, no separate `setup.cfg`

---

## 17. Deliverables for v1

1. Working `outreach` CLI: `discover`, `harvest`, `classify`, `send`, `check-replies`, `campaign create`
2. Alembic migrations applied, schema in place
3. Dashboard at `http://127.0.0.1:8000` with all listed pages working
4. Two example template files with REPLACE-ME placeholders
5. `README.md` with quickstart pointing to `USER_CHECKLIST.md` for manual setup
6. `docker-compose.yml` for postgres + redis
7. `.env.example` with every required var documented inline
8. systemd unit files in `deploy/systemd/`
9. Test suite passing locally (`pytest`)
10. ruff + mypy passing without errors

---

## 18. Implementation order (strict)

1. Skeleton (pyproject, docker-compose, .env.example, config.py, db models, alembic init)
2. Phase 1: 2GIS adapter + raw_companies storage + `discover` CLI
3. Dedup merger: raw_companies → companies (by INN, then domain, then name+region)
4. Phase 2: scraper + extractor + verifier + `harvest` CLI
5. Phase 3: Ollama classifier + `classify` CLI
6. Phase 4: template engine + example files
7. Phase 5: SMTP sender + throttle + `send` CLI + `campaign create`
8. Phase 6: IMAP poller + `check-replies` CLI
9. Phase 7: FastAPI dashboard
10. Phase 8: arq worker + systemd units
11. Tests (write incrementally, but ensure final coverage)
12. README + final pass

After each phase: commit with conventional commit message, ensure CLI for that phase works end-to-end against real Postgres.
