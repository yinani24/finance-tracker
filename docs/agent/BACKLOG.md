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

- [~] **Plaid end-to-end — PRD written + decomposed into issues** (`docs/prd/plaid-integration.md`).
      Stage 1 done 2026-07-07: issues **#5** sandbox verification harness (FR1), **#6** Plaid
      error handling → mapped HTTP codes (FR2), **#7** `POST /plaid/webhook` endpoint (FR3),
      **#8** webhook JWT verification (FR3). Next: Stage 2/3 (research/plan) then implement —
      suggested order #5 → #6 → #7 → #8 (#8 depends on #7). Code in `app/api/plaid.py` +
      `app/services/plaid_service.py` imports and all `test_plaid.py` tests pass against a
      mocked client, but nothing has run against sandbox Plaid; no webhook endpoint exists;
      Plaid `ApiException` is unhandled. Live sandbox verification is an owner-local step
      (real Postgres + Plaid keys).
      Owner: 3 low-risk QUESTIONS FOR HUMAN in the PRD (sandbox-only OK? webhook URL ngrok
      vs deployed? JWT-verify default enabled OK?) — proceeding on assumptions unless told.

## Medium priority
- [ ] Add a Plaid webhook endpoint + signature verification so syncs are event-driven
      instead of manual.

## Research (only if higher items blocked)
- [ ] Plaid alternatives (Teller, MX, Finicity, Yodlee, SimpleFIN, GoCardless/Nordigen)
      — write up in `docs/agent/RESEARCH.md`.
