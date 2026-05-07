# Pipes Outreach Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a B2B email outreach tool for selling steel pipes in Russia — discovers companies via 2GIS, harvests emails, classifies segments via Ollama LLM, sends templated plain-text emails, detects replies via IMAP, and provides a local FastAPI+HTMX dashboard.

**Architecture:** Modular pipeline — each stage (discover → harvest → classify → send → reply-check) is an independent CLI command and arq task. PostgreSQL stores all state; Redis backs the arq queue. A FastAPI+HTMX dashboard provides read-only observability. All user-facing strings in Russian; all code/comments in English.

**Tech Stack:** Python 3.12, PostgreSQL 16, Redis 7, SQLAlchemy 2.x async, Alembic, arq, FastAPI, Jinja2, HTMX, Pico.css, httpx, selectolax, ollama-python, aiosmtplib, imap-tools, dnspython, typer, structlog, pydantic-settings v2, ruff, mypy --strict, pytest + pytest-asyncio + VCR.py

---

## File Map

```
pipes-outreach/
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── alembic.ini
├── alembic/env.py
├── alembic/versions/   (generated)
├── src/outreach/
│   ├── __init__.py
│   ├── config.py
│   ├── logging_setup.py
│   ├── db/models.py
│   ├── db/session.py
│   ├── adapters/base.py
│   ├── adapters/twogis.py
│   ├── adapters/listorg.py  (stub)
│   ├── adapters/yandex.py   (stub)
│   ├── adapters/eis.py      (stub)
│   ├── dedup/merger.py
│   ├── harvest/extractor.py
│   ├── harvest/scraper.py
│   ├── harvest/verifier.py
│   ├── classify/prompts.py
│   ├── classify/llm.py
│   ├── send/templates.py
│   ├── send/smtp.py
│   ├── send/throttle.py
│   ├── replies/imap_poller.py
│   ├── tasks/worker.py
│   ├── tasks/discover.py
│   ├── tasks/harvest.py
│   ├── tasks/classify.py
│   ├── tasks/send.py
│   ├── tasks/check_replies.py
│   ├── cli.py
│   └── web/app.py
│   └── web/routes/companies.py
│   └── web/routes/campaigns.py
│   └── web/routes/sends.py
│   └── web/templates/base.html
│   └── web/templates/index.html
│   └── web/templates/companies.html
│   └── web/templates/company_detail.html
│   └── web/templates/campaigns.html
│   └── web/templates/sends.html
├── templates_email/trader.txt.example
├── templates_email/end_user.txt.example
├── deploy/systemd/  (5 service+timer pairs)
└── tests/
    ├── conftest.py
    ├── fixtures/
    ├── test_extractor.py
    ├── test_dedup.py
    ├── test_templates.py
    └── test_twogis_adapter.py
```

---

## Task 1: Project skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/outreach/__init__.py` (and all `__init__.py` files)

- [ ] **Step 1: Init git and create directory structure**

```bash
cd /home/harsh/project/pipemail
git init
mkdir -p src/outreach/{db,adapters,harvest,classify,send,replies,dedup,tasks,web/{routes,templates}}
mkdir -p alembic/versions templates_email deploy/systemd tests/fixtures
touch src/outreach/__init__.py
touch src/outreach/db/__init__.py src/outreach/adapters/__init__.py
touch src/outreach/harvest/__init__.py src/outreach/classify/__init__.py
touch src/outreach/send/__init__.py src/outreach/replies/__init__.py
touch src/outreach/dedup/__init__.py src/outreach/tasks/__init__.py
touch src/outreach/web/__init__.py src/outreach/web/routes/__init__.py
```

- [ ] **Step 2: Write pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pipes-outreach"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "httpx[http2]>=0.27",
    "selectolax>=0.3",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "arq>=0.25",
    "fastapi>=0.111",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
    "uvicorn[standard]>=0.30",
    "ollama>=0.2",
    "imap-tools>=1.6",
    "aiosmtplib>=3.0",
    "dnspython>=2.6",
    "typer>=0.12",
    "python-dotenv>=1.0",
    "structlog>=24.0",
    "itsdangerous>=2.2",
]

[project.scripts]
outreach = "outreach.cli:app"

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "vcrpy>=6.0",
    "ruff>=0.4",
    "mypy>=1.10",
    "types-python-dateutil",
    "httpx",
]

[tool.hatch.build.targets.wheel]
packages = ["src/outreach"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "C4"]

[tool.mypy]
strict = true
python_version = "3.12"
mypy_path = "src"
```

- [ ] **Step 3: Write docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: outreach
      POSTGRES_PASSWORD: outreach
      POSTGRES_DB: outreach
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

- [ ] **Step 4: Write .env.example**

```bash
# Database (runs via docker-compose)
DB_URL=postgresql+asyncpg://outreach:outreach@localhost:5432/outreach

# Redis
REDIS_URL=redis://localhost:6379

# 2GIS Catalog API key (get free at dev.2gis.ru)
TWOGIS_API_KEY=your_key_here

# SMTP — use an app password, not your main password
SMTP_HOST=smtp.mail.ru
SMTP_PORT=465
SMTP_USER=info@your-domain.ru
SMTP_PASSWORD=app_password_here
SENDER_NAME=Имя Фамилия
SENDER_EMAIL=info@your-domain.ru
REPLY_TO=info@your-domain.ru

# IMAP — same mailbox
IMAP_HOST=imap.mail.ru
IMAP_PORT=993
IMAP_USER=info@your-domain.ru
IMAP_PASSWORD=app_password_here

# Ollama LLM (install ollama separately, pull model separately)
OLLAMA_URL=http://localhost:11434
LLM_MODEL=qwen2.5:7b-instruct-q4_K_M

# Sending behaviour
DAILY_SEND_LIMIT=100
WORK_HOURS_START=9
WORK_HOURS_END=18
TIMEZONE=Asia/Yekaterinburg

# Logging
LOG_LEVEL=INFO
```

- [ ] **Step 5: Write .gitignore**

```
.env
__pycache__/
*.py[cod]
.mypy_cache/
.ruff_cache/
.pytest_cache/
dist/
*.egg-info/
.venv/
htmlcov/
.coverage
```

- [ ] **Step 6: Commit skeleton**

```bash
git add .
git commit -m "chore: project skeleton — pyproject, docker-compose, .env.example"
```

---

## Task 2: Config and logging

**Files:**
- Create: `src/outreach/config.py`
- Create: `src/outreach/logging_setup.py`

- [ ] **Step 1: Write config.py**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    db_url: str
    redis_url: str = "redis://localhost:6379"

    twogis_api_key: str = ""

    smtp_host: str = "smtp.mail.ru"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    sender_name: str = ""
    sender_email: str = ""
    reply_to: str = ""

    imap_host: str = "imap.mail.ru"
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""

    ollama_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b-instruct-q4_K_M"

    daily_send_limit: int = 100
    work_hours_start: int = 9
    work_hours_end: int = 18
    timezone: str = "Asia/Yekaterinburg"

    log_level: str = "INFO"

    twogis_default_categories: list[str] = [
        "трубы стальные",
        "металлопрокат",
        "нефтегазовое оборудование",
        "трубопроводная арматура",
    ]
    twogis_default_regions: list[int] = [1, 2, 4, 38, 70]


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 2: Write logging_setup.py**

```python
import logging
import structlog


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
```

- [ ] **Step 3: Commit**

```bash
git add src/outreach/config.py src/outreach/logging_setup.py
git commit -m "feat: config (pydantic-settings) and structlog setup"
```

---

## Task 3: Database models and Alembic

**Files:**
- Create: `src/outreach/db/models.py`
- Create: `src/outreach/db/session.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`

- [ ] **Step 1: Write db/models.py**

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawCompany(Base):
    __tablename__ = "raw_companies"
    __table_args__ = (UniqueConstraint("source", "source_id"),)

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


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    inn: Mapped[str | None] = mapped_column(String(12), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(512))
    domain: Mapped[str | None] = mapped_column(String(256), unique=True, index=True)
    region: Mapped[str | None] = mapped_column(String(128))
    segment: Mapped[str | None] = mapped_column(String(32), index=True)
    products: Mapped[list] = mapped_column(JSONB, default=list)
    classified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    sources: Mapped[list] = mapped_column(JSONB, default=list)


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(256), unique=True)
    is_role: Mapped[bool] = mapped_column(default=False)
    is_free_provider: Mapped[bool] = mapped_column(default=False)
    mx_valid: Mapped[bool | None] = mapped_column(nullable=True)
    bounced: Mapped[bool] = mapped_column(default=False)
    unsubscribed: Mapped[bool] = mapped_column(default=False)
    priority: Mapped[int] = mapped_column(default=50)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    template_key: Mapped[str] = mapped_column(String(64))
    target_segment: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(default=True)
    daily_limit: Mapped[int] = mapped_column(default=100)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Send(Base):
    __tablename__ = "sends"
    __table_args__ = (UniqueConstraint("company_id", "campaign_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"))
    status: Mapped[str] = mapped_column(String(32), index=True)
    message_id: Mapped[str | None] = mapped_column(String(256), unique=True, index=True)
    subject_used: Mapped[str] = mapped_column(String(512))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ImapState(Base):
    """Tracks last seen IMAP UID to avoid reprocessing messages."""

    __tablename__ = "imap_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    folder: Mapped[str] = mapped_column(String(128), default="INBOX")
    last_uid: Mapped[int] = mapped_column(default=0)
```

- [ ] **Step 2: Write db/session.py**

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from outreach.config import get_settings

_engine = None
_session_factory = None


def get_engine():  # type: ignore[no-untyped-def]
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.db_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
```

- [ ] **Step 3: Write alembic.ini**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 4: Write alembic/env.py**

```python
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from outreach.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return os.environ.get(
        "DB_URL", "postgresql+asyncpg://outreach:outreach@localhost:5432/outreach"
    )


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(get_url())
    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda conn: context.configure(
                connection=conn, target_metadata=target_metadata
            )
        )
        async with connection.begin():
            await connection.run_sync(lambda _: context.run_migrations())
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 5: Install deps and generate first migration**

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
docker compose up -d
# wait 3 seconds for postgres to start
sleep 3
DB_URL=postgresql+asyncpg://outreach:outreach@localhost:5432/outreach \
  alembic revision --autogenerate -m "initial schema"
DB_URL=postgresql+asyncpg://outreach:outreach@localhost:5432/outreach \
  alembic upgrade head
```

Expected: migration file created in `alembic/versions/`, tables created.

- [ ] **Step 6: Commit**

```bash
git add alembic/ src/outreach/db/ alembic.ini
git commit -m "feat: db models (SQLAlchemy 2 async) and alembic migration"
```

---

## Task 4: Adapter base + TwoGIS adapter

**Files:**
- Create: `src/outreach/adapters/base.py`
- Create: `src/outreach/adapters/twogis.py`
- Create: `src/outreach/adapters/listorg.py` (stub)
- Create: `src/outreach/adapters/yandex.py` (stub)
- Create: `src/outreach/adapters/eis.py` (stub)
- Test: `tests/test_twogis_adapter.py`
- Create: `tests/fixtures/twogis_response.json`

- [ ] **Step 1: Write adapters/base.py**

```python
from collections.abc import AsyncIterator
from typing import Protocol

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

- [ ] **Step 2: Write stub adapters**

`src/outreach/adapters/listorg.py`:
```python
"""
List-org.com adapter — Phase 2.

Planned approach:
  - URL: https://www.list-org.com/search?type=all&val={query}&region={region}
  - Parse HTML table rows; extract INN, name, address from columns
  - Pitfalls: rate limiting; CAPTCHAs on bulk queries; no official API
"""
from collections.abc import AsyncIterator

from outreach.adapters.base import Adapter, RawCompanyDTO


class ListOrgAdapter:
    name = "listorg"

    async def fetch(
        self, query: str, region: str | None = None, limit: int = 100
    ) -> AsyncIterator[RawCompanyDTO]:
        raise NotImplementedError("Phase 2")
        yield  # make mypy happy — unreachable


_: Adapter = ListOrgAdapter()
```

`src/outreach/adapters/yandex.py`:
```python
"""
Yandex Business adapter — Phase 2.

Planned approach:
  - Yandex Places API (https://yandex.ru/dev/geocode/doc)
  - Endpoint: https://search-maps.yandex.ru/v1/?text={query}&lang=ru_RU
  - Requires API key from developer.tech.yandex.ru
  - Pitfalls: tight rate limits (1000/day free), session cookies sometimes required
"""
from collections.abc import AsyncIterator

from outreach.adapters.base import Adapter, RawCompanyDTO


class YandexAdapter:
    name = "yandex"

    async def fetch(
        self, query: str, region: str | None = None, limit: int = 100
    ) -> AsyncIterator[RawCompanyDTO]:
        raise NotImplementedError("Phase 2")
        yield


_: Adapter = YandexAdapter()
```

`src/outreach/adapters/eis.py`:
```python
"""
ЕИС (Единая информационная система закупок) adapter — Phase 3.

Planned approach:
  - REST API: https://zakupki.gov.ru/epz/order/extendedsearch/results.html
  - Search by OKPD2 code for pipes: 24.20 (Трубы стальные)
  - Extract customer INN from tender docs
  - Pitfalls: XML-heavy responses; paging with up to 10k results per query
"""
from collections.abc import AsyncIterator

from outreach.adapters.base import Adapter, RawCompanyDTO


class EisAdapter:
    name = "eis"

    async def fetch(
        self, query: str, region: str | None = None, limit: int = 100
    ) -> AsyncIterator[RawCompanyDTO]:
        raise NotImplementedError("Phase 3")
        yield


_: Adapter = EisAdapter()
```

- [ ] **Step 3: Write failing test for TwoGIS adapter**

`tests/test_twogis_adapter.py`:
```python
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from outreach.adapters.twogis import TwoGISAdapter


FIXTURE = Path(__file__).parent / "fixtures" / "twogis_response.json"


@pytest.fixture()
def twogis_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.mark.asyncio
async def test_fetch_returns_dtos(twogis_fixture: dict) -> None:
    adapter = TwoGISAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = twogis_fixture
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        results = []
        async for dto in adapter.fetch("трубы стальные", region="38", limit=5):
            results.append(dto)

    assert len(results) >= 1
    assert results[0].source == "2gis"
    assert results[0].name != ""


@pytest.mark.asyncio
async def test_fetch_extracts_domain(twogis_fixture: dict) -> None:
    adapter = TwoGISAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = twogis_fixture
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        results = []
        async for dto in adapter.fetch("трубы", limit=10):
            results.append(dto)

    domains = [r.domain for r in results if r.domain]
    for d in domains:
        assert "://" not in d
        assert "/" not in d
```

- [ ] **Step 4: Run test — confirm FAIL**

```bash
pytest tests/test_twogis_adapter.py -v
```
Expected: `ModuleNotFoundError` or `ImportError` (TwoGISAdapter not yet defined).

- [ ] **Step 5: Write fixtures/twogis_response.json**

```json
{
  "meta": {"api_version": "3.0", "code": 200},
  "result": {
    "total": 2,
    "items": [
      {
        "id": "70000001041681880",
        "type": "org",
        "name_ex": {"primary": "МеталлТрейд"},
        "org": {"name": "МеталлТрейд"},
        "contact_groups": [
          {
            "contacts": [
              {"type": "phone", "value": "+7 (351) 555-01-01"},
              {"type": "website", "value": "http://metal-trade.ru/"}
            ]
          }
        ],
        "adm_div": [{"type": "city", "name": "Челябинск"}],
        "address": {"name": "ул. Труда, 90, Челябинск"}
      },
      {
        "id": "70000001099999999",
        "type": "org",
        "name_ex": {"primary": "СтальПром"},
        "org": {"name": "СтальПром"},
        "contact_groups": [],
        "adm_div": [{"type": "city", "name": "Екатеринбург"}],
        "address": {"name": "пр. Ленина, 1, Екатеринбург"}
      }
    ]
  }
}
```

- [ ] **Step 6: Write adapters/twogis.py**

```python
import asyncio
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import httpx
import structlog

from outreach.adapters.base import RawCompanyDTO

log = structlog.get_logger(__name__)

_TWOGIS_URL = "https://catalog.api.2gis.com/3.0/items"
_FIELDS = "items.org,items.contact_groups,items.point,items.adm_div,items.region_id"
_PAGE_SIZE = 50


class TwoGISAdapter:
    name = "2gis"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def fetch(
        self, query: str, region: str | None = None, limit: int = 100
    ) -> AsyncIterator[RawCompanyDTO]:
        fetched = 0
        page = 1

        async with httpx.AsyncClient(timeout=15) as client:
            while fetched < limit:
                params: dict[str, str | int] = {
                    "q": query,
                    "fields": _FIELDS,
                    "key": self._api_key,
                    "page_size": min(_PAGE_SIZE, limit - fetched),
                    "page": page,
                    "type": "branch",
                }
                if region:
                    params["region_id"] = region

                resp = await client.get(_TWOGIS_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

                result = data.get("result", {})
                items = result.get("items", [])
                if not items:
                    break

                for item in items:
                    if fetched >= limit:
                        return
                    dto = self._parse_item(item)
                    if dto:
                        fetched += 1
                        yield dto

                total = result.get("total", 0)
                if fetched >= total:
                    break
                page += 1
                await asyncio.sleep(0.5)

    def _parse_item(self, item: dict) -> RawCompanyDTO | None:
        org = item.get("org") or item.get("name_ex")
        if not org:
            return None
        name = org.get("name", "").strip()
        if not name:
            return None

        domain: str | None = None
        phone: str | None = None
        for group in item.get("contact_groups", []):
            for contact in group.get("contacts", []):
                ctype = contact.get("type", "")
                value = contact.get("value", "")
                if ctype == "website" and not domain:
                    parsed = urlparse(value if "://" in value else f"https://{value}")
                    domain = parsed.netloc or parsed.path
                    domain = domain.lstrip("www.").rstrip("/").split("/")[0] or None
                elif ctype == "phone" and not phone:
                    phone = value

        adm_div = item.get("adm_div", [])
        city = next(
            (d.get("name") for d in adm_div if d.get("type") == "city"), None
        )

        address_obj = item.get("address", {})
        address = address_obj.get("name") if isinstance(address_obj, dict) else None

        return RawCompanyDTO(
            source="2gis",
            source_id=str(item.get("id", "")),
            name=name,
            domain=domain,
            phone=phone,
            address=address,
            region=city,
            raw=item,
        )
```

- [ ] **Step 7: Run tests — confirm PASS**

```bash
pytest tests/test_twogis_adapter.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/outreach/adapters/ tests/test_twogis_adapter.py tests/fixtures/
git commit -m "feat: adapter base protocol + TwoGIS adapter with tests"
```

---

## Task 5: Dedup merger

**Files:**
- Create: `src/outreach/dedup/merger.py`
- Test: `tests/test_dedup.py`

- [ ] **Step 1: Write failing tests**

`tests/test_dedup.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from outreach.dedup.merger import merge_raw_companies


@pytest.mark.asyncio
async def test_merge_by_inn_deduplicates() -> None:
    """Two raw records with same INN produce one Company."""
    session = AsyncMock()

    raw1 = MagicMock()
    raw1.inn = "7700000001"
    raw1.name = "Металл Трейд"
    raw1.domain = "metal.ru"
    raw1.region = "Москва"
    raw1.source = "2gis"

    raw2 = MagicMock()
    raw2.inn = "7700000001"
    raw2.name = "МеталлТрейд"
    raw2.domain = None
    raw2.region = "Москва"
    raw2.source = "listorg"

    # Simulate no existing company in DB
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=scalar_result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    await merge_raw_companies([raw1, raw2], session)

    # Only one company should be added
    assert session.add.call_count == 1
    added = session.add.call_args[0][0]
    assert added.inn == "7700000001"
    assert "2gis" in added.sources
    assert "listorg" in added.sources


@pytest.mark.asyncio
async def test_merge_by_domain_when_no_inn() -> None:
    """Records without INN are merged by domain."""
    session = AsyncMock()

    raw1 = MagicMock()
    raw1.inn = None
    raw1.name = "Трубная компания"
    raw1.domain = "truba.ru"
    raw1.region = "Екатеринбург"
    raw1.source = "2gis"

    raw2 = MagicMock()
    raw2.inn = None
    raw2.name = "Трубная компания"
    raw2.domain = "truba.ru"
    raw2.region = "Екатеринбург"
    raw2.source = "2gis"

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=scalar_result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    await merge_raw_companies([raw1, raw2], session)

    assert session.add.call_count == 1
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
pytest tests/test_dedup.py -v
```
Expected: `ImportError` (merger not yet defined).

- [ ] **Step 3: Write dedup/merger.py**

```python
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
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
pytest tests/test_dedup.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/outreach/dedup/ tests/test_dedup.py
git commit -m "feat: dedup merger raw_companies → companies by INN/domain"
```

---

## Task 6: Email extractor

**Files:**
- Create: `src/outreach/harvest/extractor.py`
- Test: `tests/test_extractor.py`

- [ ] **Step 1: Write failing tests**

`tests/test_extractor.py`:
```python
from outreach.harvest.extractor import extract_emails, EmailResult

SAMPLE_HTML = """
<html><body>
<a href="mailto:zakupki@steel-co.ru">Написать нам</a>
<p>Также пишите на sales@steel-co.ru или info[at]steel-co.ru</p>
<p>Спам: noreply@steel-co.ru</p>
<p>Бесплатный: manager@gmail.com</p>
</body></html>
"""

def test_extracts_mailto_first() -> None:
    results = extract_emails(SAMPLE_HTML, "steel-co.ru")
    emails = [r.email for r in results]
    assert "zakupki@steel-co.ru" in emails
    mailto_result = next(r for r in results if r.email == "zakupki@steel-co.ru")
    assert mailto_result.priority <= 10

def test_extracts_plain_text_email() -> None:
    results = extract_emails(SAMPLE_HTML, "steel-co.ru")
    emails = [r.email for r in results]
    assert "sales@steel-co.ru" in emails

def test_deobfuscates_at() -> None:
    results = extract_emails(SAMPLE_HTML, "steel-co.ru")
    emails = [r.email for r in results]
    assert "info@steel-co.ru" in emails

def test_drops_noreply() -> None:
    results = extract_emails(SAMPLE_HTML, "steel-co.ru")
    emails = [r.email for r in results]
    assert "noreply@steel-co.ru" not in emails

def test_flags_free_provider() -> None:
    results = extract_emails(SAMPLE_HTML, "steel-co.ru")
    gmail = next((r for r in results if "gmail" in r.email), None)
    assert gmail is not None
    assert gmail.is_free_provider is True

def test_max_three_emails() -> None:
    html = " ".join(
        f'<a href="mailto:e{i}@corp.ru">e</a>' for i in range(10)
    )
    results = extract_emails(html, "corp.ru")
    assert len(results) <= 3

def test_role_email_flagged() -> None:
    html = '<a href="mailto:snab@corp.ru">snab</a>'
    results = extract_emails(html, "corp.ru")
    assert results[0].is_role is True
    assert results[0].priority <= 20

def test_deobfuscates_sobaka() -> None:
    html = "<p>contact[собака]company.ru</p>"
    results = extract_emails(html, "company.ru")
    assert any("contact@company.ru" == r.email for r in results)
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
pytest tests/test_extractor.py -v
```
Expected: all FAIL with ImportError.

- [ ] **Step 3: Write harvest/extractor.py**

```python
import re
from dataclasses import dataclass, field

from selectolax.parser import HTMLParser

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

_DROP_LOCAL = re.compile(
    r"^(noreply|no-reply|webmaster|postmaster|admin|abuse|hostmaster|root|mailer-daemon)$",
    re.IGNORECASE,
)

_ROLE_LOCAL = {
    "info", "sales", "office", "hello", "contact", "support",
    "sekretar", "secretary", "zakupki", "snab", "omts",
    "prodaja", "prodazhi",
}

_FREE_PROVIDERS = {
    "mail.ru", "gmail.com", "yandex.ru", "yandex.com",
    "yahoo.com", "rambler.ru", "list.ru", "bk.ru", "inbox.ru",
}

_DEOBFUSCATE = [
    (re.compile(r"\[at\]|\(at\)|\s+AT\s+", re.IGNORECASE), "@"),
    (re.compile(r"\[собака\]|\(собака\)", re.IGNORECASE), "@"),
    (re.compile(r"\[dot\]|\(точка\)|\s+DOT\s+|\s+точка\s+", re.IGNORECASE), "."),
    (re.compile(r"&#64;|&commat;"), "@"),
]


@dataclass
class EmailResult:
    email: str
    priority: int = 50
    is_role: bool = False
    is_free_provider: bool = False


def extract_emails(html: str, company_domain: str) -> list[EmailResult]:
    tree = HTMLParser(html)
    for tag in tree.css("script, style"):
        tag.decompose()

    results: dict[str, EmailResult] = {}

    # mailto links — highest confidence
    for node in tree.css("a[href]"):
        href = node.attributes.get("href", "") or ""
        if href.lower().startswith("mailto:"):
            addr = href[7:].split("?")[0].strip().lower()
            if addr and _EMAIL_RE.match(addr):
                _add(results, addr, mailto=True)

    # plain text (with deobfuscation)
    text = tree.body.text(separator=" ") if tree.body else tree.text()
    for pattern, replacement in _DEOBFUSCATE:
        text = pattern.sub(replacement, text)
    for match in _EMAIL_RE.finditer(text):
        addr = match.group(0).lower()
        _add(results, addr, mailto=False)

    sorted_results = sorted(results.values(), key=lambda r: r.priority)
    return sorted_results[:3]


def _add(results: dict[str, EmailResult], addr: str, *, mailto: bool) -> None:
    local, _, domain = addr.partition("@")
    if not domain:
        return
    if _DROP_LOCAL.match(local):
        return

    is_role = local in _ROLE_LOCAL or bool(
        re.match(r"^(zakup|snab)", local, re.IGNORECASE)
    )
    is_free = domain in _FREE_PROVIDERS

    if mailto:
        if re.match(r"^(zakup|snab)", local, re.IGNORECASE):
            priority = 10
        elif local in {"sales", "info"}:
            priority = 20
        else:
            priority = 30
    else:
        if re.match(r"^(zakup|snab)", local, re.IGNORECASE):
            priority = 30
        elif local in {"sales", "info"}:
            priority = 40
        else:
            priority = 50

    if is_free:
        priority += 20

    if addr not in results or results[addr].priority > priority:
        results[addr] = EmailResult(
            email=addr,
            priority=priority,
            is_role=is_role,
            is_free_provider=is_free,
        )
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
pytest tests/test_extractor.py -v
```
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/outreach/harvest/extractor.py tests/test_extractor.py
git commit -m "feat: email extractor with deobfuscation and priority ranking"
```

---

## Task 7: Web scraper and MX verifier

**Files:**
- Create: `src/outreach/harvest/scraper.py`
- Create: `src/outreach/harvest/verifier.py`

- [ ] **Step 1: Write harvest/scraper.py**

```python
import asyncio
import re
from urllib.parse import urljoin, urlparse

import httpx
import structlog

log = structlog.get_logger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_PATHS = [
    "",
    "/contacts",
    "/contact",
    "/kontakty",
    "/about",
    "/o-kompanii",
    "/o-nas",
    "/svyaz",
    "/contacts/",
]

_domain_last_request: dict[str, float] = {}
_ua_index = 0


async def scrape_domain(domain: str) -> list[str]:
    """Return list of HTML pages from the domain, checking common contact paths."""
    global _ua_index
    pages: list[str] = []

    async with httpx.AsyncClient(
        timeout=10,
        max_redirects=3,
        http2=True,
        follow_redirects=True,
    ) as client:
        for path in _PATHS:
            url = f"https://{domain}{path}"
            await _rate_limit(domain)
            ua = _USER_AGENTS[_ua_index % len(_USER_AGENTS)]
            _ua_index += 1
            try:
                resp = await client.get(url, headers={"User-Agent": ua})
                if resp.status_code in (403, 429):
                    log.info("scraper.skipped", url=url, status=resp.status_code)
                    break
                if resp.status_code == 200:
                    pages.append(resp.text)
            except (httpx.SSLError, httpx.ConnectError, httpx.TimeoutException) as exc:
                log.info("scraper.error", url=url, error=str(exc))

    return pages


async def _rate_limit(domain: str) -> None:
    import time
    now = time.monotonic()
    last = _domain_last_request.get(domain, 0.0)
    wait = 3.0 - (now - last)
    if wait > 0:
        await asyncio.sleep(wait)
    _domain_last_request[domain] = time.monotonic()
```

- [ ] **Step 2: Write harvest/verifier.py**

```python
import asyncio
import time

import dns.asyncresolver
import structlog

log = structlog.get_logger(__name__)

_cache: dict[str, tuple[bool, float]] = {}
_TTL = 86400.0  # 24 hours


async def has_valid_mx(domain: str) -> bool:
    """Return True if domain has at least one MX record. Cached 24h."""
    now = time.monotonic()
    if domain in _cache:
        result, expires = _cache[domain]
        if now < expires:
            return result

    try:
        answers = await dns.asyncresolver.resolve(domain, "MX")
        valid = len(answers) > 0
    except Exception as exc:
        log.debug("verifier.mx_fail", domain=domain, error=str(exc))
        valid = False

    _cache[domain] = (valid, now + _TTL)
    return valid
```

- [ ] **Step 3: Commit**

```bash
git add src/outreach/harvest/scraper.py src/outreach/harvest/verifier.py
git commit -m "feat: web scraper (httpx+selectolax) and async MX verifier"
```

---

## Task 8: CLI — discover and harvest commands

**Files:**
- Create: `src/outreach/cli.py`
- Modify: integrates adapters, dedup, scraper, extractor, verifier

- [ ] **Step 1: Write cli.py**

```python
import asyncio
from typing import Annotated

import structlog
import typer
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from outreach.config import get_settings
from outreach.db.models import Campaign, Company, Email, RawCompany, Send
from outreach.db.session import get_session_factory
from outreach.logging_setup import configure_logging

app = typer.Typer(help="Инструмент B2B рассылки стальных труб")
log = structlog.get_logger(__name__)


def _setup() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


# ─── discover ────────────────────────────────────────────────────────────────

discover_app = typer.Typer()
app.add_typer(discover_app, name="discover")


@app.command("discover")
def discover(
    source: Annotated[str, typer.Option(help="Источник: 2gis")] = "2gis",
    query: Annotated[str, typer.Option(help="Поисковый запрос")] = "",
    region: Annotated[str, typer.Option(help="ID региона")] = "",
    limit: Annotated[int, typer.Option(help="Максимум компаний")] = 100,
    all_defaults: Annotated[bool, typer.Option("--all-defaults")] = False,
) -> None:
    """Обнаружить компании через выбранный источник и сохранить в raw_companies."""
    _setup()
    asyncio.run(_discover(source, query, region, limit, all_defaults))


async def _discover(
    source: str, query: str, region: str, limit: int, all_defaults: bool
) -> None:
    from outreach.adapters.twogis import TwoGISAdapter
    from outreach.dedup.merger import merge_raw_companies

    settings = get_settings()
    factory = get_session_factory()

    if source == "2gis":
        adapter = TwoGISAdapter(api_key=settings.twogis_api_key)
    else:
        typer.echo(f"Источник '{source}' не поддерживается в v1", err=True)
        raise typer.Exit(1)

    queries = [query] if query else (settings.twogis_default_categories if all_defaults else [query])
    regions = [region] if region else (
        [str(r) for r in settings.twogis_default_regions] if all_defaults else [region]
    )

    total = 0
    async with factory() as session:
        for q in queries:
            for reg in regions:
                raw_batch: list[RawCompany] = []
                async for dto in adapter.fetch(q, region=reg or None, limit=limit):
                    stmt = pg_insert(RawCompany).values(
                        source=dto.source,
                        source_id=dto.source_id,
                        inn=dto.inn,
                        name=dto.name,
                        domain=dto.domain,
                        phone=dto.phone,
                        address=dto.address,
                        region=dto.region,
                        raw=dto.raw,
                    ).on_conflict_do_nothing(index_elements=["source", "source_id"])
                    await session.execute(stmt)
                    raw_batch.append(
                        RawCompany(
                            source=dto.source, source_id=dto.source_id,
                            inn=dto.inn, name=dto.name, domain=dto.domain,
                            phone=dto.phone, address=dto.address,
                            region=dto.region, raw=dto.raw,
                        )
                    )
                    total += 1

                await merge_raw_companies(raw_batch, session)
                await session.commit()

    typer.echo(f"Обнаружено и сохранено: {total} компаний")


# ─── harvest ─────────────────────────────────────────────────────────────────

@app.command("harvest")
def harvest(
    limit: Annotated[int, typer.Option(help="Максимум компаний")] = 50,
    company_id: Annotated[int | None, typer.Option(help="ID конкретной компании")] = None,
) -> None:
    """Собрать email-адреса с сайтов компаний."""
    _setup()
    asyncio.run(_harvest(limit, company_id))


async def _harvest(limit: int, company_id: int | None) -> None:
    from outreach.harvest.scraper import scrape_domain
    from outreach.harvest.extractor import extract_emails
    from outreach.harvest.verifier import has_valid_mx

    factory = get_session_factory()
    harvested = 0

    async with factory() as session:
        if company_id:
            result = await session.execute(
                select(Company).where(Company.id == company_id)
            )
            companies = [result.scalar_one()]
        else:
            result = await session.execute(
                select(Company)
                .where(Company.domain.isnot(None))
                .outerjoin(Email, Email.company_id == Company.id)
                .where(Email.id.is_(None))
                .limit(limit)
            )
            companies = list(result.scalars().all())

        for company in companies:
            if not company.domain:
                continue
            typer.echo(f"Обрабатываем: {company.name} ({company.domain})")
            pages = await scrape_domain(company.domain)
            combined_html = " ".join(pages)
            if not combined_html:
                continue

            email_results = extract_emails(combined_html, company.domain)
            for er in email_results:
                _, _, domain = er.email.partition("@")
                mx = await has_valid_mx(domain)
                stmt = pg_insert(Email).values(
                    company_id=company.id,
                    email=er.email,
                    is_role=er.is_role,
                    is_free_provider=er.is_free_provider,
                    mx_valid=mx,
                    priority=er.priority,
                ).on_conflict_do_nothing(index_elements=["email"])
                await session.execute(stmt)
            await session.commit()
            harvested += len(email_results)

    typer.echo(f"Собрано адресов: {harvested}")


# ─── classify ────────────────────────────────────────────────────────────────

@app.command("classify")
def classify(
    limit: Annotated[int, typer.Option()] = 20,
    company_id: Annotated[int | None, typer.Option()] = None,
) -> None:
    """Классифицировать компании по сегментам через Ollama."""
    _setup()
    asyncio.run(_classify(limit, company_id))


async def _classify(limit: int, company_id: int | None) -> None:
    from outreach.classify.llm import classify_company

    factory = get_session_factory()

    async with factory() as session:
        if company_id:
            result = await session.execute(
                select(Company).where(Company.id == company_id)
            )
            companies = [result.scalar_one()]
        else:
            result = await session.execute(
                select(Company)
                .where(Company.segment.is_(None))
                .limit(limit)
            )
            companies = list(result.scalars().all())

        for company in companies:
            typer.echo(f"Классифицируем: {company.name}")
            segment, products = await classify_company(company)
            company.segment = segment
            company.products = products
            from datetime import datetime, timezone
            company.classified_at = datetime.now(timezone.utc)

        await session.commit()

    typer.echo(f"Классифицировано: {len(companies)} компаний")


# ─── campaign ────────────────────────────────────────────────────────────────

campaign_app = typer.Typer()
app.add_typer(campaign_app, name="campaign")


@campaign_app.command("create")
def campaign_create(
    name: Annotated[str, typer.Option(help="Название кампании")],
    segment: Annotated[str, typer.Option(help="Сегмент: trader | end_user")],
    template: Annotated[str, typer.Option(help="Ключ шаблона: trader | end_user")],
    daily_limit: Annotated[int, typer.Option(help="Лимит в день")] = 100,
) -> None:
    """Создать новую кампанию рассылки."""
    _setup()
    if segment not in ("trader", "end_user"):
        typer.echo("Сегмент должен быть 'trader' или 'end_user'", err=True)
        raise typer.Exit(1)
    asyncio.run(_campaign_create(name, segment, template, daily_limit))


async def _campaign_create(
    name: str, segment: str, template: str, daily_limit: int
) -> None:
    factory = get_session_factory()
    async with factory() as session:
        campaign = Campaign(
            name=name,
            template_key=template,
            target_segment=segment,
            daily_limit=daily_limit,
        )
        session.add(campaign)
        await session.flush()
        campaign_id = campaign.id
        await session.commit()
    typer.echo(f"Кампания создана, ID: {campaign_id}")


# ─── send ─────────────────────────────────────────────────────────────────────

@app.command("send")
def send_cmd(
    campaign_id: Annotated[int, typer.Option(help="ID кампании")],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    all_active: Annotated[bool, typer.Option("--all-active")] = False,
) -> None:
    """Отправить письма по активной кампании."""
    _setup()
    asyncio.run(_send(campaign_id, dry_run))


async def _send(campaign_id: int, dry_run: bool) -> None:
    from outreach.send.smtp import send_email
    from outreach.send.templates import render_template
    from outreach.send.throttle import can_send_now, count_sent_today

    factory = get_session_factory()

    async with factory() as session:
        result = await session.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one()

        sent_today = await count_sent_today(campaign_id, session)
        remaining = campaign.daily_limit - sent_today

        if remaining <= 0:
            typer.echo("Дневной лимит исчерпан")
            return

        if not can_send_now(campaign):
            typer.echo("Не рабочее время — отправка отложена")
            return

        # Select companies
        subq = select(Send.company_id).where(Send.campaign_id == campaign_id)
        result = await session.execute(
            select(Company, Email)
            .join(Email, Email.company_id == Company.id)
            .where(Company.segment == campaign.target_segment)
            .where(Email.mx_valid.is_(True))
            .where(Email.bounced.is_(False))
            .where(Email.unsubscribed.is_(False))
            .where(Company.id.not_in(subq))
            .order_by(Company.created_at.asc(), Email.priority.asc())
            .limit(remaining)
        )
        rows = result.all()

        sent = 0
        for company, email in rows:
            subject, body = render_template(campaign.template_key, company)
            if dry_run:
                typer.echo(f"[dry-run] → {email.email} | {subject}")
                continue

            import asyncio as _asyncio
            await _asyncio.sleep(30)  # throttle handled in throttle.py
            send_result = await send_email(email.email, subject, body)
            status = "sent" if send_result.ok else "failed"

            send_row = Send(
                campaign_id=campaign_id,
                company_id=company.id,
                email_id=email.id,
                status=status,
                message_id=send_result.message_id,
                subject_used=subject,
                error=send_result.error,
            )
            if status == "sent":
                from datetime import datetime, timezone
                send_row.sent_at = datetime.now(timezone.utc)
            session.add(send_row)
            await session.commit()
            sent += 1
            typer.echo(f"Отправлено: {email.email}")

        if not dry_run:
            typer.echo(f"Итого отправлено: {sent}")


# ─── replies ──────────────────────────────────────────────────────────────────

@app.command("check-replies")
def check_replies() -> None:
    """Проверить входящие ответы через IMAP (однократно)."""
    _setup()
    asyncio.run(_check_replies())


@app.command("poll-replies")
def poll_replies() -> None:
    """Непрерывно проверять ответы (интервал 60 минут)."""
    _setup()

    async def _loop() -> None:
        import asyncio as _asyncio
        while True:
            await _check_replies()
            typer.echo("Следующая проверка через 60 минут...")
            await _asyncio.sleep(3600)

    asyncio.run(_loop())


async def _check_replies() -> None:
    from outreach.replies.imap_poller import poll_inbox
    found = await poll_inbox()
    typer.echo(f"Обработано ответов: {found}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 2: Commit**

```bash
git add src/outreach/cli.py
git commit -m "feat: typer CLI — discover, harvest, classify, send, check-replies"
```

---

## Task 9: Ollama classifier

**Files:**
- Create: `src/outreach/classify/prompts.py`
- Create: `src/outreach/classify/llm.py`

- [ ] **Step 1: Write classify/prompts.py**

```python
SYSTEM = (
    "Ты классификатор B2B-компаний в металлургии РФ. "
    "Тебе дан текст с сайта компании. Определи сегмент и продукты. "
    "Отвечай СТРОГО валидным JSON без комментариев и markdown-обёрток."
)

USER_TEMPLATE = """\
Текст сайта компании "{name}":

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

- [ ] **Step 2: Write classify/llm.py**

```python
import json
import re

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
        raw = response.message.content
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
            return _parse_response(response.message.content)
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
    """Ping Ollama; raise RuntimeError if unreachable."""
    settings = get_settings()
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            return resp.status_code == 200
    except Exception as exc:
        raise RuntimeError(f"Ollama недоступен: {exc}") from exc
```

- [ ] **Step 3: Commit**

```bash
git add src/outreach/classify/
git commit -m "feat: Ollama LLM classifier with retry and JSON validation"
```

---

## Task 10: Template engine

**Files:**
- Create: `src/outreach/send/templates.py`
- Create: `templates_email/trader.txt.example`
- Create: `templates_email/end_user.txt.example`
- Test: `tests/test_templates.py`

- [ ] **Step 1: Write failing tests**

`tests/test_templates.py`:
```python
import os
import tempfile
from pathlib import Path

import pytest

from outreach.send.templates import render_template, TemplateError


@pytest.fixture()
def template_dir(tmp_path: Path) -> Path:
    content = (
        "Subject: Поставки труб — {{ company_name }}\n"
        "\n"
        "{{ greeting }}!\n"
        "\n"
        "Предлагаем трубы для {{ company_name }}.\n"
    )
    (tmp_path / "trader.txt").write_text(content, encoding="utf-8")
    return tmp_path


def test_render_returns_subject_and_body(
    template_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEMPLATE_DIR", str(template_dir))
    from outreach.send import templates
    templates._cache.clear()

    from unittest.mock import MagicMock
    company = MagicMock()
    company.name = "СтальТорг"
    company.region = "Челябинск"

    subject, body = render_template("trader", company, _dir=template_dir)
    assert "СтальТорг" in subject
    assert "Здравствуйте, коллеги из г. Челябинск" in body


def test_render_greeting_without_city(template_dir: Path) -> None:
    from unittest.mock import MagicMock
    company = MagicMock()
    company.name = "СтальТорг"
    company.region = None

    subject, body = render_template("trader", company, _dir=template_dir)
    assert "Здравствуйте" in body
    assert "г." not in body


def test_missing_template_raises(tmp_path: Path) -> None:
    from unittest.mock import MagicMock
    company = MagicMock()
    company.name = "Test"
    company.region = None

    with pytest.raises(TemplateError):
        render_template("nonexistent", company, _dir=tmp_path)
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
pytest tests/test_templates.py -v
```

- [ ] **Step 3: Write send/templates.py**

```python
import os
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from outreach.db.models import Company

_cache: dict[str, tuple[object, float]] = {}  # key → (env, mtime)
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
            f"Шаблон не найден: {tfile}. Скопируй из {template_key}.txt.example и заполни."
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
```

- [ ] **Step 4: Write example templates**

`templates_email/trader.txt.example`:
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

`templates_email/end_user.txt.example`:
```
Subject: Стальные трубы для [REPLACE: сферы применения] — [REPLACE: ваше ИП/ООО]

{{ greeting }}!

Меня зовут [REPLACE: Имя], занимаюсь поставками стальных труб в [REPLACE: регион].

[REPLACE: 2-3 предложения о надёжности, сертификатах, опыте и конкретных типоразмерах]

Если есть текущая потребность — пришлите запрос, подготовлю спецификацию.

С уважением,
[REPLACE: Имя Фамилия]
[REPLACE: телефон]
ИНН: [REPLACE: ИНН]

---
Если рассылка вам неинтересна, ответьте «Отписаться» — больше писать не будем.
```

- [ ] **Step 5: Run tests — confirm PASS**

```bash
pytest tests/test_templates.py -v
```
Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/outreach/send/templates.py templates_email/ tests/test_templates.py
git commit -m "feat: Jinja2 template engine with file-mtime cache + example templates"
```

---

## Task 11: Throttle logic

**Files:**
- Create: `src/outreach/send/throttle.py`

- [ ] **Step 1: Write throttle.py**

```python
import random
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from outreach.config import get_settings
from outreach.db.models import Campaign, Send


def can_send_now(campaign: Campaign) -> bool:
    """Return True if current time is within configured working hours."""
    settings = get_settings()
    import zoneinfo

    tz = zoneinfo.ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    return settings.work_hours_start <= now.hour < settings.work_hours_end


async def count_sent_today(campaign_id: int, session: AsyncSession) -> int:
    """Return number of emails sent today for this campaign."""
    settings = get_settings()
    import zoneinfo

    tz = zoneinfo.ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_of_day.astimezone(timezone.utc)

    result = await session.execute(
        select(func.count(Send.id))
        .where(Send.campaign_id == campaign_id)
        .where(Send.status == "sent")
        .where(Send.sent_at >= start_utc)
    )
    return result.scalar_one()


def send_delay_seconds() -> float:
    """Return seconds to wait between sends: 30s ± 15s jitter."""
    return 30.0 + random.uniform(-15.0, 15.0)
```

- [ ] **Step 2: Commit**

```bash
git add src/outreach/send/throttle.py
git commit -m "feat: send throttle — working hours check and daily count"
```

---

## Task 12: SMTP sender

**Files:**
- Create: `src/outreach/send/smtp.py`

- [ ] **Step 1: Write send/smtp.py**

```python
import email.utils
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import aiosmtplib
import structlog

from outreach.config import get_settings

log = structlog.get_logger(__name__)


@dataclass
class SendResult:
    ok: bool
    message_id: str | None = None
    error: str | None = None


async def send_email(to_addr: str, subject: str, body: str) -> SendResult:
    """Send a plain-text email. Returns SendResult."""
    settings = get_settings()
    sender_domain = settings.sender_email.split("@")[-1]
    message_id = f"<{uuid4()}@{sender_domain}>"

    msg_lines = [
        f"From: {settings.sender_name} <{settings.sender_email}>",
        f"To: {to_addr}",
        f"Reply-To: {settings.reply_to}",
        f"Message-ID: {message_id}",
        f"Date: {email.utils.formatdate(localtime=False)}",
        "MIME-Version: 1.0",
        "Content-Type: text/plain; charset=utf-8",
        "Content-Transfer-Encoding: 8bit",
        f"List-Unsubscribe: <mailto:unsubscribe@{sender_domain}?subject=unsubscribe>",
        "List-Unsubscribe-Post: List-Unsubscribe=One-Click",
        f"Subject: {subject}",
        "",
        body,
    ]
    raw = "\r\n".join(msg_lines)

    try:
        if settings.smtp_port == 465:
            await aiosmtplib.send(
                raw,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password,
                use_tls=True,
            )
        else:
            await aiosmtplib.send(
                raw,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password,
                start_tls=True,
            )
        log.info("smtp.sent", to=to_addr, message_id=message_id)
        return SendResult(ok=True, message_id=message_id)
    except Exception as exc:
        log.error("smtp.failed", to=to_addr, error=str(exc))
        return SendResult(ok=False, error=str(exc))
```

- [ ] **Step 2: Commit**

```bash
git add src/outreach/send/smtp.py
git commit -m "feat: SMTP sender with List-Unsubscribe headers (aiosmtplib)"
```

---

## Task 13: IMAP reply poller

**Files:**
- Create: `src/outreach/replies/imap_poller.py`

- [ ] **Step 1: Write replies/imap_poller.py**

```python
import re
from datetime import datetime, timezone

import structlog
from imap_tools import AND, MailBox, MailMessage
from sqlalchemy import select

from outreach.config import get_settings
from outreach.db.models import Email, ImapState, Send
from outreach.db.session import get_session_factory

log = structlog.get_logger(__name__)

_UNSUB_RE = re.compile(r"отписаться|unsubscribe|не присылать", re.IGNORECASE)
_BOUNCE_RE = re.compile(r"mailer-daemon|postmaster", re.IGNORECASE)


async def poll_inbox() -> int:
    """Check INBOX for replies/bounces/unsubscribes. Returns count processed."""
    settings = get_settings()
    factory = get_session_factory()
    processed = 0

    async with factory() as session:
        state_result = await session.execute(select(ImapState).limit(1))
        state = state_result.scalar_one_or_none()
        if state is None:
            state = ImapState(folder="INBOX", last_uid=0)
            session.add(state)
            await session.flush()

        last_uid = state.last_uid

    with MailBox(settings.imap_host, port=settings.imap_port).login(
        settings.imap_user, settings.imap_password
    ) as mailbox:
        mailbox.folder.set("INBOX")
        messages = list(
            mailbox.fetch(
                criteria=AND(uid=f"{last_uid + 1}:*"),
                mark_seen=False,
                bulk=True,
            )
        )

    for msg in messages:
        try:
            await _process_message(msg)
            processed += 1
        except Exception as exc:
            log.error("imap.process_error", uid=msg.uid, error=str(exc))

    if messages:
        max_uid = max(int(m.uid) for m in messages if m.uid)
        async with factory() as session:
            state_result = await session.execute(select(ImapState).limit(1))
            state = state_result.scalar_one()
            state.last_uid = max(last_uid, max_uid)
            await session.commit()

    return processed


async def _process_message(msg: MailMessage) -> None:
    factory = get_session_factory()
    in_reply_to = msg.headers.get("in-reply-to", [""])[0]
    references = msg.headers.get("references", [""])[0]
    sender = msg.from_ or ""
    body = msg.text or ""

    async with factory() as session:
        matched_send: Send | None = None

        for mid in [in_reply_to, *references.split()]:
            mid = mid.strip()
            if not mid:
                continue
            result = await session.execute(
                select(Send).where(Send.message_id == mid)
            )
            matched_send = result.scalar_one_or_none()
            if matched_send:
                break

        is_bounce = _BOUNCE_RE.search(sender.lower())

        if matched_send:
            if is_bounce:
                matched_send.status = "bounced"
                email_result = await session.execute(
                    select(Email).where(Email.id == matched_send.email_id)
                )
                email_row = email_result.scalar_one_or_none()
                if email_row:
                    email_row.bounced = True
            elif _UNSUB_RE.search(body):
                matched_send.status = "unsubscribed"
                email_result = await session.execute(
                    select(Email).where(Email.id == matched_send.email_id)
                )
                email_row = email_result.scalar_one_or_none()
                if email_row:
                    email_row.unsubscribed = True
            else:
                matched_send.status = "replied"
                matched_send.replied_at = datetime.now(timezone.utc)

            await session.commit()
            log.info("imap.processed", sender=sender, status=matched_send.status)
```

- [ ] **Step 2: Commit**

```bash
git add src/outreach/replies/imap_poller.py
git commit -m "feat: IMAP reply poller with bounce/unsubscribe detection"
```

---

## Task 14: FastAPI + HTMX dashboard

**Files:**
- Create: `src/outreach/web/app.py`
- Create: `src/outreach/web/routes/companies.py`
- Create: `src/outreach/web/routes/campaigns.py`
- Create: `src/outreach/web/routes/sends.py`
- Create: `src/outreach/web/templates/base.html`
- Create: `src/outreach/web/templates/index.html`
- Create: `src/outreach/web/templates/companies.html`
- Create: `src/outreach/web/templates/company_detail.html`
- Create: `src/outreach/web/templates/campaigns.html`
- Create: `src/outreach/web/templates/sends.html`

- [ ] **Step 1: Write web/app.py**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from outreach.web.routes import companies, campaigns, sends

app = FastAPI(title="Outreach Dashboard")

templates = Jinja2Templates(directory="src/outreach/web/templates")

app.include_router(companies.router)
app.include_router(campaigns.router)
app.include_router(sends.router)


@app.get("/")
async def index(request):  # type: ignore[no-untyped-def]
    from datetime import date, timezone, datetime
    from sqlalchemy import func, select
    from outreach.db.models import Send, Company
    from outreach.db.session import get_session_factory

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
```

- [ ] **Step 2: Write web/routes/companies.py**

```python
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
            q = q.join(Email, Email.company_id == Company.id)

        total = (await session.execute(
            select(Company.id).where(q.whereclause or True)
        )).all()

        companies = (await session.execute(
            q.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

    return templates.TemplateResponse("companies.html", {
        "request": request,
        "companies": companies,
        "page": page,
        "total": len(total),
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

    return templates.TemplateResponse("company_detail.html", {
        "request": request,
        "company": company,
        "emails": emails,
        "sends": sends,
    })
```

- [ ] **Step 3: Write web/routes/campaigns.py**

```python
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
        "request": request, "campaigns": campaigns,
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
            name=name, template_key=template_key,
            target_segment=segment, daily_limit=daily_limit,
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
```

- [ ] **Step 4: Write web/routes/sends.py**

```python
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

    return templates.TemplateResponse("sends.html", {
        "request": request,
        "sends": sends,
        "status": status,
        "campaign_id": campaign_id,
        "page": page,
    })
```

- [ ] **Step 5: Write HTML templates**

`src/outreach/web/templates/base.html`:
```html
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Рассылка труб{% endblock %}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
</head>
<body>
  <nav class="container-fluid">
    <ul><li><strong>Рассылка труб</strong></li></ul>
    <ul>
      <li><a href="/">Дашборд</a></li>
      <li><a href="/companies">Компании</a></li>
      <li><a href="/campaigns">Кампании</a></li>
      <li><a href="/sends">Отправки</a></li>
    </ul>
  </nav>
  <main class="container">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

`src/outreach/web/templates/index.html`:
```html
{% extends "base.html" %}
{% block title %}Дашборд{% endblock %}
{% block content %}
<h1>Дашборд</h1>
<div class="grid">
  <article>
    <hgroup><h2>{{ sent_today }}</h2><p>Отправлено сегодня</p></hgroup>
  </article>
  <article>
    <hgroup><h2>{{ replied }}</h2><p>Ответов всего</p></hgroup>
  </article>
  <article>
    <hgroup><h2>{{ bounced }}</h2><p>Bounce</p></hgroup>
  </article>
  <article>
    <hgroup><h2>{{ total_companies }}</h2><p>Компаний в базе</p></hgroup>
  </article>
</div>
<h2>Последние 10 событий</h2>
<table>
  <thead><tr><th>ID</th><th>Статус</th><th>Email</th><th>Время</th></tr></thead>
  <tbody>
    {% for s in recent_sends %}
    <tr>
      <td>{{ s.id }}</td>
      <td>{{ s.status }}</td>
      <td>{{ s.email_id }}</td>
      <td>{{ s.queued_at.strftime('%d.%m %H:%M') if s.queued_at else '—' }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

`src/outreach/web/templates/companies.html`:
```html
{% extends "base.html" %}
{% block title %}Компании{% endblock %}
{% block content %}
<h1>Компании ({{ total }})</h1>
<form hx-get="/companies" hx-target="#companies-table" hx-push-url="true">
  <div class="grid">
    <input name="segment" placeholder="Сегмент" value="{{ segment }}">
    <input name="region" placeholder="Регион" value="{{ region }}">
    <select name="has_email">
      <option value="">Все</option>
      <option value="1" {% if has_email == '1' %}selected{% endif %}>С email</option>
    </select>
    <button type="submit">Найти</button>
  </div>
</form>
<div id="companies-table">
<table>
  <thead><tr><th>ID</th><th>Название</th><th>Сегмент</th><th>Регион</th><th>Домен</th></tr></thead>
  <tbody>
    {% for c in companies %}
    <tr>
      <td><a href="/companies/{{ c.id }}">{{ c.id }}</a></td>
      <td>{{ c.name }}</td>
      <td>{{ c.segment or '—' }}</td>
      <td>{{ c.region or '—' }}</td>
      <td>{{ c.domain or '—' }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
</div>
{% endblock %}
```

`src/outreach/web/templates/company_detail.html`:
```html
{% extends "base.html" %}
{% block title %}{{ company.name }}{% endblock %}
{% block content %}
<h1>{{ company.name }}</h1>
<dl>
  <dt>ИНН</dt><dd>{{ company.inn or '—' }}</dd>
  <dt>Сегмент</dt><dd>{{ company.segment or '—' }}</dd>
  <dt>Регион</dt><dd>{{ company.region or '—' }}</dd>
  <dt>Домен</dt><dd>{{ company.domain or '—' }}</dd>
  <dt>Источники</dt><dd>{{ company.sources | join(', ') }}</dd>
  <dt>Классифицирован</dt><dd>{{ company.classified_at or '—' }}</dd>
</dl>
<h2>Email-адреса</h2>
<table>
  <thead><tr><th>Email</th><th>MX</th><th>Роль</th><th>Приоритет</th></tr></thead>
  <tbody>
    {% for e in emails %}
    <tr>
      <td>{{ e.email }}</td>
      <td>{{ '✓' if e.mx_valid else '✗' }}</td>
      <td>{{ '✓' if e.is_role else '' }}</td>
      <td>{{ e.priority }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
<h2>История отправок</h2>
<table>
  <thead><tr><th>Кампания</th><th>Статус</th><th>Отправлено</th></tr></thead>
  <tbody>
    {% for s in sends %}
    <tr>
      <td>{{ s.campaign_id }}</td>
      <td>{{ s.status }}</td>
      <td>{{ s.sent_at.strftime('%d.%m.%Y %H:%M') if s.sent_at else '—' }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

`src/outreach/web/templates/campaigns.html`:
```html
{% extends "base.html" %}
{% block title %}Кампании{% endblock %}
{% block content %}
<h1>Кампании</h1>
<table>
  <thead><tr><th>ID</th><th>Название</th><th>Сегмент</th><th>Шаблон</th><th>Лимит/день</th><th>Активна</th><th></th></tr></thead>
  <tbody>
    {% for c in campaigns %}
    <tr>
      <td>{{ c.id }}</td>
      <td>{{ c.name }}</td>
      <td>{{ c.target_segment }}</td>
      <td>{{ c.template_key }}</td>
      <td>{{ c.daily_limit }}</td>
      <td>{{ 'Да' if c.is_active else 'Нет' }}</td>
      <td>
        <form method="post" action="/campaigns/{{ c.id }}/toggle">
          <button type="submit">{{ 'Пауза' if c.is_active else 'Запустить' }}</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>
<h2>Создать кампанию</h2>
<form method="post" action="/campaigns">
  <div class="grid">
    <input name="name" placeholder="Название" required>
    <select name="segment" required>
      <option value="trader">trader</option>
      <option value="end_user">end_user</option>
    </select>
    <select name="template_key" required>
      <option value="trader">trader</option>
      <option value="end_user">end_user</option>
    </select>
    <input name="daily_limit" type="number" value="100" required>
    <button type="submit">Создать</button>
  </div>
</form>
{% endblock %}
```

`src/outreach/web/templates/sends.html`:
```html
{% extends "base.html" %}
{% block title %}Отправки{% endblock %}
{% block content %}
<h1>Отправки</h1>
<form hx-get="/sends" hx-target="#sends-table" hx-push-url="true">
  <div class="grid">
    <select name="status">
      <option value="">Все статусы</option>
      <option value="sent" {% if status=='sent' %}selected{% endif %}>Отправлено</option>
      <option value="replied" {% if status=='replied' %}selected{% endif %}>Ответили</option>
      <option value="bounced" {% if status=='bounced' %}selected{% endif %}>Bounce</option>
      <option value="failed" {% if status=='failed' %}selected{% endif %}>Ошибка</option>
    </select>
    <button type="submit">Фильтр</button>
  </div>
</form>
<div id="sends-table">
<table>
  <thead><tr><th>ID</th><th>Email ID</th><th>Кампания</th><th>Статус</th><th>Тема</th><th>Отправлено</th></tr></thead>
  <tbody>
    {% for s in sends %}
    <tr>
      <td>{{ s.id }}</td>
      <td>{{ s.email_id }}</td>
      <td>{{ s.campaign_id }}</td>
      <td>{{ s.status }}</td>
      <td>{{ s.subject_used[:50] }}</td>
      <td>{{ s.sent_at.strftime('%d.%m %H:%M') if s.sent_at else '—' }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
</div>
{% endblock %}
```

- [ ] **Step 6: Commit**

```bash
git add src/outreach/web/
git commit -m "feat: FastAPI+HTMX+Pico.css dashboard (companies, campaigns, sends)"
```

---

## Task 15: arq worker + systemd units

**Files:**
- Create: `src/outreach/tasks/worker.py`
- Create: `src/outreach/tasks/discover.py`
- Create: `src/outreach/tasks/harvest.py`
- Create: `src/outreach/tasks/classify.py`
- Create: `src/outreach/tasks/send.py`
- Create: `src/outreach/tasks/check_replies.py`
- Create: `deploy/systemd/` (10 files)

- [ ] **Step 1: Write tasks/discover.py**

```python
from arq import ArqRedis


async def task_discover(ctx: dict) -> None:
    from outreach.cli import _discover
    from outreach.config import get_settings
    settings = get_settings()
    await _discover("2gis", "", "", 200, True)
```

- [ ] **Step 2: Write tasks/harvest.py**

```python
async def task_harvest(ctx: dict) -> None:
    from outreach.cli import _harvest
    await _harvest(50, None)
```

- [ ] **Step 3: Write tasks/classify.py**

```python
async def task_classify(ctx: dict) -> None:
    from outreach.cli import _classify
    await _classify(20, None)
```

- [ ] **Step 4: Write tasks/send.py**

```python
from sqlalchemy import select
from outreach.db.models import Campaign
from outreach.db.session import get_session_factory


async def task_send(ctx: dict) -> None:
    from outreach.cli import _send
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Campaign).where(Campaign.is_active.is_(True))
        )
        campaigns = result.scalars().all()
    for campaign in campaigns:
        await _send(campaign.id, dry_run=False)
```

- [ ] **Step 5: Write tasks/check_replies.py**

```python
async def task_check_replies(ctx: dict) -> None:
    from outreach.cli import _check_replies
    await _check_replies()
```

- [ ] **Step 6: Write tasks/worker.py**

```python
from arq.connections import RedisSettings
from arq import cron

from outreach.config import get_settings
from outreach.tasks.discover import task_discover
from outreach.tasks.harvest import task_harvest
from outreach.tasks.classify import task_classify
from outreach.tasks.send import task_send
from outreach.tasks.check_replies import task_check_replies


def get_redis_settings() -> RedisSettings:
    settings = get_settings()
    import re
    m = re.match(r"redis://([^:/]+)(?::(\d+))?", settings.redis_url)
    host = m.group(1) if m else "localhost"
    port = int(m.group(2)) if m and m.group(2) else 6379
    return RedisSettings(host=host, port=port)


class WorkerSettings:
    functions = [task_discover, task_harvest, task_classify, task_send, task_check_replies]
    redis_settings = get_redis_settings()
    cron_jobs = [
        cron(task_discover, hour=6),
        cron(task_harvest, hour=7),
        cron(task_classify, hour=8),
        cron(task_send, hour=10),
        cron(task_check_replies, minute={0}),
    ]
```

- [ ] **Step 7: Write systemd units**

`deploy/systemd/outreach-send.service`:
```ini
[Unit]
Description=Outreach — отправка писем
After=network.target

[Service]
Type=oneshot
WorkingDirectory=%h/project/pipemail
ExecStart=%h/project/pipemail/.venv/bin/outreach send --all-active
EnvironmentFile=%h/project/pipemail/.env
```

`deploy/systemd/outreach-send.timer`:
```ini
[Unit]
Description=Запуск outreach-send по расписанию
[Timer]
OnCalendar=Mon..Fri 10:00
Persistent=true
[Install]
WantedBy=timers.target
```

Create equivalent `.service` and `.timer` for: `outreach-discover` (06:00), `outreach-harvest` (07:00), `outreach-classify` (08:00), `outreach-check-replies` (every hour `*:00`).

`deploy/systemd/outreach-discover.service`:
```ini
[Unit]
Description=Outreach — обнаружение компаний
After=network.target

[Service]
Type=oneshot
WorkingDirectory=%h/project/pipemail
ExecStart=%h/project/pipemail/.venv/bin/outreach discover --source 2gis --all-defaults
EnvironmentFile=%h/project/pipemail/.env
```

`deploy/systemd/outreach-discover.timer`:
```ini
[Unit]
Description=Запуск outreach-discover по расписанию
[Timer]
OnCalendar=*-*-* 06:00
Persistent=true
[Install]
WantedBy=timers.target
```

`deploy/systemd/outreach-harvest.service`:
```ini
[Unit]
Description=Outreach — сбор email-адресов
[Service]
Type=oneshot
WorkingDirectory=%h/project/pipemail
ExecStart=%h/project/pipemail/.venv/bin/outreach harvest --limit 50
EnvironmentFile=%h/project/pipemail/.env
```

`deploy/systemd/outreach-harvest.timer`:
```ini
[Unit]
Description=Запуск outreach-harvest по расписанию
[Timer]
OnCalendar=*-*-* 07:00
Persistent=true
[Install]
WantedBy=timers.target
```

`deploy/systemd/outreach-classify.service`:
```ini
[Unit]
Description=Outreach — классификация компаний
[Service]
Type=oneshot
WorkingDirectory=%h/project/pipemail
ExecStart=%h/project/pipemail/.venv/bin/outreach classify --limit 20
EnvironmentFile=%h/project/pipemail/.env
```

`deploy/systemd/outreach-classify.timer`:
```ini
[Unit]
Description=Запуск outreach-classify по расписанию
[Timer]
OnCalendar=*-*-* 08:00
Persistent=true
[Install]
WantedBy=timers.target
```

`deploy/systemd/outreach-check-replies.service`:
```ini
[Unit]
Description=Outreach — проверка ответов IMAP
[Service]
Type=oneshot
WorkingDirectory=%h/project/pipemail
ExecStart=%h/project/pipemail/.venv/bin/outreach check-replies
EnvironmentFile=%h/project/pipemail/.env
```

`deploy/systemd/outreach-check-replies.timer`:
```ini
[Unit]
Description=Запуск outreach-check-replies каждый час
[Timer]
OnCalendar=*:00
Persistent=true
[Install]
WantedBy=timers.target
```

- [ ] **Step 8: Commit**

```bash
git add src/outreach/tasks/ deploy/
git commit -m "feat: arq worker with cron jobs + systemd service/timer units"
```

---

## Task 16: conftest and final tests

**Files:**
- Create: `tests/conftest.py`
- Update: add any missing test coverage

- [ ] **Step 1: Write tests/conftest.py**

```python
import pytest


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block accidental real HTTP calls in tests."""
    import httpx
    original = httpx.AsyncClient.send

    async def blocked(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError(
            "Real network call in test — use mock or VCR cassette"
        )

    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: all tests pass.

- [ ] **Step 3: Run ruff and mypy**

```bash
ruff check src/ tests/
mypy src/outreach/ --strict
```
Fix any reported issues.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test: conftest with network guard, full suite passing"
```

---

## Task 17: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

```markdown
# pipes-outreach

B2B email outreach tool for selling steel pipes to Russian companies.

**See [USER_CHECKLIST.md](USER_CHECKLIST.md) for all manual setup steps** (domain, DNS, email hosting, API keys, warm-up schedule).

## Quick start

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Install
uv venv .venv && source .venv/bin/activate
uv pip install -e .

# 3. Copy and fill env
cp .env.example .env
# edit .env with your credentials

# 4. Run migrations
alembic upgrade head

# 5. Discover companies
outreach discover --source 2gis --all-defaults

# 6. Harvest emails
outreach harvest --limit 50

# 7. Classify segments
outreach classify --limit 20

# 8. Create campaign (copy and fill templates_email/trader.txt first)
outreach campaign create --name "Трейдеры" --segment trader --template trader

# 9. Dry-run before real send
outreach send --campaign-id 1 --dry-run

# 10. Start dashboard
uvicorn outreach.web.app:app --host 127.0.0.1 --port 8000
```
```

- [ ] **Step 2: Final commit**

```bash
git add README.md
git commit -m "docs: README quickstart pointing to USER_CHECKLIST.md"
```

---

## Spec Coverage Check

| Spec section | Task |
|---|---|
| 3. Tech stack | Task 1 (pyproject.toml) |
| 4. Project structure | Tasks 1-16 |
| 5. DB schema | Task 3 |
| 6. Discovery / 2GIS adapter | Task 4 |
| 6.4 discover CLI | Task 8 |
| 7. Email harvesting | Tasks 6, 7, 8 |
| 8. Classification (Ollama) | Task 9 |
| 9. Template engine | Task 10 |
| 10. Sender + throttle | Tasks 11, 12 |
| 10.4 send / campaign CLI | Task 8 |
| 11. Reply detection | Task 13 |
| 12. Dashboard | Task 14 |
| 13. arq + systemd | Task 15 |
| 14. Coding conventions | Tasks 1-16 (ruff/mypy in Task 16) |
| 16. Tests | Tasks 4-6, 10, 16 |
| 17. Deliverables | All tasks |
| 18. Implementation order | Tasks follow spec order |
