# Agent Backlog

Prioritized to-do for the overnight agent. Check off done items; add newly
discovered ones. Note: `feat/backend-foundation` has been merged into **`main`**
(commit 21d68dd) — base agent PRs on `main`.

## In progress / recently done
- [x] Restore missing `app/services/card_bonuses.py` — was breaking the entire app
      import and test suite (2026-07-07).
- [x] **Point card data at the sibling repo consistently** (#3) — `card_insight_engine`
      and `recommendation_snapshot` now delegate to `card_bonuses.fetch_cards_sync`; the
      third-party `andenacitelli` URL and the two duplicate caches are gone. One
      upstream, one shared cache. (PR opened 2026-07-07)

## High priority
- [ ] **Plaid end-to-end.** Code in `apps/api/app/api/plaid.py` +
      `app/services/plaid_service.py` now imports and all `test_plaid.py` tests pass
      against a mocked Plaid client. Still unverified against real/sandbox Plaid.
      Needs the owner's sandbox keys + a Link handshake to confirm link-token →
      exchange → sync works live. See VERIFY LOCALLY notes in the card-bonuses PR.
      Open questions: no webhook endpoint exists for Plaid `SYNC_UPDATES_AVAILABLE`;
      `sync_transactions` is only triggered manually via `POST /items/{id}/sync`.

## Medium priority
- [ ] Add a Plaid webhook endpoint + signature verification so syncs are event-driven
      instead of manual.

## Research (only if higher items blocked)
- [ ] Plaid alternatives (Teller, MX, Finicity, Yodlee, SimpleFIN, GoCardless/Nordigen)
      — write up in `docs/agent/RESEARCH.md`.
