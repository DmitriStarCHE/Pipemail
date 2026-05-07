# pipes-outreach

B2B email outreach tool for selling steel pipes to Russian companies (НКТ, обсадные, общего назначения).

**See [USER_CHECKLIST.md](USER_CHECKLIST.md) for all manual setup steps** — domain purchase, DNS (SPF/DKIM/DMARC), email hosting, API keys, and domain warm-up schedule.

## Stack

Python 3.12 · PostgreSQL 16 · Redis 7 · FastAPI + HTMX · Ollama (local LLM) · arq

## Quick start

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Install
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 3. Configure
cp .env.example .env
# Edit .env — fill TWOGIS_API_KEY, SMTP_*, IMAP_*, SENDER_*

# 4. Apply migrations
alembic upgrade head

# 5. Discover companies
outreach discover --source 2gis --all-defaults

# 6. Harvest emails
outreach harvest --limit 50

# 7. Classify segments (requires Ollama running)
outreach classify --limit 20

# 8. Create campaign
# First: copy templates_email/trader.txt.example → templates_email/trader.txt
# Then fill in your details
outreach campaign create --name "Трейдеры Q1" --segment trader --template trader

# 9. Dry-run before real send
outreach send --campaign-id 1 --dry-run

# 10. Start dashboard
uvicorn outreach.web.app:app --host 127.0.0.1 --port 8000
# Open http://localhost:8000
```

## CLI reference

| Command | Description |
|---|---|
| `outreach discover --source 2gis --query "трубы" --region 38` | Find companies via 2GIS |
| `outreach discover --source 2gis --all-defaults` | Use config defaults (all categories + regions) |
| `outreach harvest --limit 50` | Scrape emails from company websites |
| `outreach harvest --company-id 123` | Harvest single company |
| `outreach classify --limit 20` | Classify segments via Ollama |
| `outreach campaign create --name X --segment trader --template trader` | Create campaign |
| `outreach send --campaign-id 1 --dry-run` | Preview what would send |
| `outreach send --campaign-id 1` | Send (respects daily limit + working hours) |
| `outreach send --all-active` | Send for all active campaigns |
| `outreach check-replies` | One-shot IMAP reply check |
| `outreach poll-replies` | Continuous IMAP polling (60 min interval) |

## Scheduling

**Option A: arq worker**
```bash
arq outreach.tasks.worker.WorkerSettings
```

**Option B: systemd timers**
```bash
cp deploy/systemd/*.service ~/.config/systemd/user/
cp deploy/systemd/*.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now outreach-discover.timer outreach-harvest.timer \
  outreach-classify.timer outreach-send.timer outreach-check-replies.timer
```

## Daily workflow

1. Open http://localhost:8000 — check today's stats
2. Read replies in your email client — the system flags them, you respond manually
3. Weekly: review bounce rate, adjust templates if needed

All automated tasks (discover → harvest → classify → send → check-replies) run on schedule without intervention.
