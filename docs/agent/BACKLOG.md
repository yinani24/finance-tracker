# Agent Backlog

Prioritized to-do for the overnight agent. Check off done items; add newly
discovered ones. Note: `feat/backend-foundation` has been **merged into `main`**
(commit 21d68dd) — `main` is now the trunk. Base all agent PRs on `main`.

## In progress / recently done
- [x] Restore missing `app/services/card_bonuses.py` — was breaking the entire app
      import and test suite (2026-07-07).

## High priority
- [~] **Plaid end-to-end — PRD written** (`docs/prd/plaid-integration.md`, 2026-07-07).
      Next: owner glance at its `## QUESTIONS FOR HUMAN` (all low-risk, proceeding on
      assumptions), then Stage 1 — decompose into the 4 proposed issue slices:
      (1) sandbox verification harness, (2) Plaid error handling, (3) `POST /plaid/webhook`
      endpoint, (4) webhook JWT verification. Code in `app/api/plaid.py` +
      `app/services/plaid_service.py` imports and all `test_plaid.py` tests pass against a
      mocked client, but nothing has run against sandbox Plaid; no webhook endpoint exists;
      Plaid `ApiException` is unhandled.
- [ ] **Point card data at the sibling repo consistently.**
      `app/services/card_insight_engine.py` (`DATA_URL`) and the sync cache in
      `app/services/recommendation_snapshot.py` fetch card data from
      `andenacitelli/credit-card-bonuses-api` (main) directly, while the new
      `card_bonuses` service points at the sibling `yinani24/credit-card-bonuses-api`
      (master). Consolidate all three onto the sibling source (ideally reuse the
      `card_bonuses` service's cache/URL) so there is one source of truth.

## Medium priority
- [ ] Add a Plaid webhook endpoint + signature verification so syncs are event-driven
      instead of manual.
- [ ] Consider a shared sync/async cache in `card_bonuses` so
      `recommendation_snapshot._fetch_cards` and `card_insight_engine.fetch_card_bonuses`
      don't each maintain a separate cache dict.

## Research (only if higher items blocked)
- [ ] Plaid alternatives (Teller, MX, Finicity, Yodlee, SimpleFIN, GoCardless/Nordigen)
      — write up in `docs/agent/RESEARCH.md`.
