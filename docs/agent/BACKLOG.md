# Agent Backlog

Prioritized to-do for the overnight agent. Check off done items; add newly
discovered ones. Note: `feat/backend-foundation` has been **merged into `main`**
(commit 21d68dd) — `main` is now the trunk. Base all agent PRs on `main`.

## In progress / recently done
- [x] Restore missing `app/services/card_bonuses.py` — was breaking the entire app
      import and test suite (2026-07-07).
- [x] **Point card data at the sibling repo consistently** (#3) — `card_insight_engine`
      and `recommendation_snapshot` now delegate to `card_bonuses.fetch_cards_sync`; the
      third-party `andenacitelli` URL and the two duplicate caches are gone. One
      upstream, one shared cache. (PR opened 2026-07-07)

## High priority
- [~] **Plaid end-to-end — PRD written + decomposed into issues** (`docs/prd/plaid-integration.md`).
      Stage 1 done 2026-07-07: issues **#5** sandbox verification harness (FR1), **#6** Plaid
      error handling → mapped HTTP codes (FR2), **#7** `POST /plaid/webhook` endpoint (FR3),
      **#8** webhook JWT verification (FR3). Suggested order #5 → #6 → #7 → #8 (#8 depends on #7).
      Progress: #5 research+plan (merged, `docs/agent/research/5.md`); #6 & #7 research+plan
      posted. **#6 IMPLEMENTED → PR #10** (Stage 4 done 2026-07-07: `plaid_errors.py` classifier
      + `_call` wrapper + `@app.exception_handler`; Plaid `ApiException` now maps to
      409-relink / 503-retry / 502, secrets never surfaced; 26 plaid tests + 154 full suite
      green on real Postgres, ruff clean). Suggested next: implement #5 (sandbox harness),
      then #7 (webhook endpoint) → #8 (webhook JWT, depends on #7). Still nothing run against
      real sandbox Plaid; no webhook endpoint exists yet. Live sandbox verification is an
      owner-local step (real Postgres + Plaid keys).
      Owner: 3 low-risk QUESTIONS FOR HUMAN in the PRD (sandbox-only OK? webhook URL ngrok
      vs deployed? JWT-verify default enabled OK?) — proceeding on assumptions unless told.

## Medium priority
- [ ] Add a Plaid webhook endpoint + signature verification so syncs are event-driven
      instead of manual.

## Research (only if higher items blocked)
- [ ] Plaid alternatives (Teller, MX, Finicity, Yodlee, SimpleFIN, GoCardless/Nordigen)
      — write up in `docs/agent/RESEARCH.md`.
