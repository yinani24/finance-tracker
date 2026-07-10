# CLAUDE.md

Guidance for Claude Code when working in this repository.

---

## Structure

```
apps/
  api/    — FastAPI backend (Python, PostgreSQL, Supabase Auth, Alembic)
  web/    — Next.js frontend (TypeScript, Tailwind, DaisyUI)
```

## API (`apps/api/`)

```bash
cd apps/api
pip install -e ".[dev]"
uvicorn app.main:app --reload       # run dev server
pytest                               # run tests
alembic upgrade head                 # run migrations
alembic revision --autogenerate -m "description"  # create migration
```

**Running the test suite in an ephemeral sandbox** (e.g. Claude Code on the web, where there's no service Postgres and the system `pip`/`setuptools` can't build the `plaid-python` sdist): use `uv`, and provision a throwaway Postgres with the helper script. This runs the *full* suite — not just `--noconftest` pure-function checks.

```bash
cd apps/api
uv venv .venv && source .venv/bin/activate       # uv builds plaid-python cleanly; system pip may fail
uv pip install -e ".[dev]"
./scripts/setup-test-db.sh                         # boots local Postgres + test DB (idempotent, disposable)
pytest                                             # 235 tests, no extra env vars needed
```

The conftest fixtures connect to `settings.test_database_url` (default `postgresql://localhost:5432/finance_tracker_test`); the script provisions exactly that. Requires a PostgreSQL package (`initdb`/`pg_ctl`) on the box.

- **Auth:** Supabase JWT — middleware in `app/auth.py`, dependency in `app/api/deps.py`
- **DB:** PostgreSQL via SQLAlchemy async, connection in `app/database.py`
- **Config:** `app/config.py` reads from environment / `.env.local`
- **Models:** `app/models/` — SQLAlchemy ORM (user, account, transaction, goal, card, plaid_item, import_record)
- **Schemas:** `app/schemas/` — Pydantic request/response models
- **Repositories:** `app/repositories/` — DB query layer
- **Routes:** `app/api/` — FastAPI routers (accounts, transactions, goals, cards, plaid, me)
- **Migrations:** `alembic/versions/`

## Web (`apps/web/`)

```bash
cd apps/web
npm install
npm run dev          # run dev server
npm run build        # production build
npm run lint         # eslint
```

- Next.js App Router with `(app)` and `(auth)` route groups
- Supabase client auth with callback route

## Environment

Both apps use `.env.local` for local config (gitignored). See `.env.example` in each app for required variables.

---

## Changelog

Update `CHANGELOG.md` under `[Unreleased]` when making changes. Use [Keep a Changelog](https://keepachangelog.com/) format.
