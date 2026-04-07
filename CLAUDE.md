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
