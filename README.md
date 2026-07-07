# Finance Tracker

A personal finance app with a FastAPI backend and Next.js frontend.

## Structure

```
apps/
  api/    — FastAPI + PostgreSQL + Supabase Auth
  web/    — Next.js + TypeScript + Tailwind
```

## Getting Started

### API

```bash
cd apps/api
pip install -e ".[dev]"
cp .env.example .env.local
# Edit .env.local with your Supabase/DB credentials
uvicorn app.main:app --reload
```

### Web

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

## API Docs

With the API running: http://localhost:8000/docs
