# PRD — Plaid Integration (Phase 1: "Plaid works end-to-end")

- **Status:** DRAFT — open questions are low-risk; ready to decompose into issues once
  the owner glances at `## QUESTIONS FOR HUMAN`. Proceed on the stated assumptions.
- **North-star:** [`docs/prd/PRODUCT.md`](./PRODUCT.md) — Phase 1 of the delivery roadmap.
- **Owner:** Yash Inani. **Author:** overnight agent. **Last updated:** 2026-07-07.

---

## Problem

The credit-card usage optimizer cannot recommend anything without the user's real
spending data. Everything downstream — spending intelligence (Phase 2), card matching
(Phase 4), portfolio optimization (Phase 5) — depends on a **reliable stream of
categorized transactions** pulled from the user's real accounts. Plaid is the chosen
aggregator for the MVP.

Today the plumbing exists but is **unproven**:

- `app/api/plaid.py` exposes `link-token`, `exchange-token`, `items` (list),
  `items/{id}/sync`, and delete endpoints.
- `app/services/plaid_service.py` implements link-token creation, public-token
  exchange, and cursor-based `transactions_sync` (add/modify/remove with dedupe).
- `apps/api/tests/test_plaid.py` (358 lines) passes — but **only against a mocked
  Plaid client**. Nothing has run against sandbox Plaid.
- There is **no webhook endpoint**: syncs only happen when the client calls
  `POST /plaid/items/{id}/sync` by hand. Plaid's `SYNC_UPDATES_AVAILABLE` webhook is
  ignored, so transaction data goes stale until the user manually refreshes.
- Error handling for Plaid `ApiException` (expired/invalid access token, rate limits,
  `ITEM_LOGIN_REQUIRED`) is absent — a failed Plaid call surfaces as an unhandled 500.

## Goals

1. Confirm the link → exchange → sync loop works against **Plaid sandbox** end-to-end,
   producing `Account` + `Transaction` rows in the DB.
2. Make sync **resilient**: map Plaid API errors to sensible HTTP responses and a
   re-link path for `ITEM_LOGIN_REQUIRED`.
3. Make sync **event-driven**: a Plaid webhook endpoint that triggers `sync_transactions`
   on `SYNC_UPDATES_AVAILABLE`, with request verification, so data stays fresh without
   manual refresh.
4. Keep secrets safe: sandbox/placeholder credentials only; access tokens never logged
   or returned to the client.

## Non-goals (this phase)

- Live/production Plaid link (needs the owner's real keys + a manual Link handshake —
  see `## VERIFY LOCALLY` in implementation PRs). We target **sandbox** only here.
- Transaction categorization logic and per-category habit metrics — that is **Phase 2**.
  We only persist Plaid's `personal_finance_category.primary` as-is for now.
- Multiple aggregators (Teller/MX/etc.) — Plaid only for the MVP.
- A polished frontend Link flow — a minimal/manual link path is enough to prove the loop.

## User stories

- *As the owner*, I can link a bank account through Plaid sandbox and see my accounts
  and transactions appear in finance-tracker.
- *As the owner*, when my bank has new transactions, they show up **without** me hitting
  a manual "sync" button.
- *As the owner*, if my linked item breaks (login required / token expired), the app
  tells me and offers to re-link instead of silently failing.
- *As a developer*, I can run the whole sync path against Plaid sandbox locally with
  documented, non-secret steps.

## Functional requirements

### FR1 — Sandbox verification harness
- Provide a documented, repeatable way to exercise the real sandbox loop with
  `FT_PLAID_ENV=sandbox` and `FT_PLAID_CLIENT_ID` / `FT_PLAID_SECRET` from the owner's
  sandbox account (values supplied at run time, never committed).
- Use Plaid's `/sandbox/public_token/create` to obtain a `public_token` without a UI,
  then drive `exchange-token` and `items/{id}/sync`. Assert accounts + transactions land
  in the DB. Keep this out of the default `pytest` run (network-gated marker, e.g.
  `@pytest.mark.plaid_sandbox`), so CI stays hermetic.

### FR2 — Error handling
- Wrap Plaid calls in `plaid_service.py`; translate `plaid.ApiException` into:
  - `ITEM_LOGIN_REQUIRED` / `INVALID_ACCESS_TOKEN` → 409 with a re-link signal.
  - Rate-limit / transient (`RATE_LIMIT_EXCEEDED`, 5xx) → 503, safe to retry.
  - Everything else → 502 with the Plaid `error_code` (no secrets) in the body.
- Never include `access_token` or raw Plaid error internals containing credentials in
  responses or logs.

### FR3 — Webhook endpoint
- Add `POST /plaid/webhook` that accepts Plaid webhook payloads.
- Handle at minimum `TRANSACTIONS: SYNC_UPDATES_AVAILABLE` → look up the `PlaidItem` by
  `item_id`, run `sync_transactions`, fire `TRANSACTIONS_SYNCED` insights event (mirrors
  the manual sync path in `app/api/plaid.py`).
- **Verify** the request is really from Plaid (see Open Question 2 for the mechanism).
- Register the webhook URL on the item via `LinkTokenCreateRequest(webhook=...)` /
  item update, configurable through settings (`FT_PLAID_WEBHOOK_URL`).
- Endpoint must be idempotent — the existing `dedupe_hash` / cursor logic already makes
  repeated syncs safe; confirm with a test.

### FR4 — Data integrity (already partly implemented; lock in with tests)
- Cursor persisted per item (`PlaidItem.cursor`) so syncs are incremental.
- Dedupe via `dedupe_hash`; modified/removed transactions handled.
- Sign convention: Plaid positive = money out; stored as negative (expense). Keep and
  test this — Phase 2/4 value math depends on it.

## Success criteria

- With sandbox credentials set, a scripted run performs link-token → sandbox
  public-token → exchange → sync and produces ≥1 `Account` and ≥1 `Transaction` row.
  (Owner-run; documented under VERIFY LOCALLY.)
- `POST /plaid/webhook` with a `SYNC_UPDATES_AVAILABLE` payload triggers a sync for the
  right item and is covered by a test (mocked Plaid client + fake payload).
- Plaid API errors produce the mapped HTTP codes above, covered by tests; no 500s for
  known Plaid error codes.
- `pytest` stays green and hermetic (no network) by default; the sandbox harness is
  opt-in.
- No secret material in the repo, logs, or API responses.

## Risks

- **Blocked on owner keys** for true live verification — mitigated by scripting the
  sandbox path and putting the credential step under VERIFY LOCALLY.
- **Webhook verification** is the trickiest bit: Plaid signs webhooks with a JWT
  (`Plaid-Verification` header) validated against a key from `/webhook_verification_key/get`.
  Getting this wrong = either rejecting real webhooks or accepting spoofed ones. Needs
  care + tests. (Open Question 2.)
- Webhooks need a **public URL** to reach a local/dev server (ngrok or a deployed
  environment). Verification cannot be fully closed out without that.

## Open questions

1. **Webhook exposure** — where does Plaid reach us? For sandbox dev this needs a
   tunnel (ngrok) or a deployed URL. **Assumption:** build the endpoint + verification
   now; the owner supplies the reachable URL (`FT_PLAID_WEBHOOK_URL`) at verify time.
2. **Verification mechanism** — implement full Plaid JWT (`Plaid-Verification`) webhook
   verification, or start with a shared-secret path check for sandbox and add JWT before
   any production use? **Assumption for MVP:** implement JWT verification but allow it to
   be disabled via a settings flag in sandbox so local testing without a public URL is
   possible. Flag defaults to *enabled*.
3. **Products scope** — link currently requests only `transactions`. Do we also want
   `auth`/`liabilities` later (e.g. card APRs/balances for value math)? **Assumption:**
   `transactions` only for Phase 1; revisit in Phase 4.

## QUESTIONS FOR HUMAN

- **Q1 (low-risk, proceeding):** OK to target **sandbox only** for Phase 1 and defer
  live-link verification to a manual step you run with your real keys? (Assumed yes.)
- **Q2 (needs you eventually):** For webhooks to work end-to-end I need a **publicly
  reachable URL** (ngrok tunnel or a deployed dev instance) and it registered as
  `FT_PLAID_WEBHOOK_URL`. Which do you prefer — ngrok for now, or stand up a deployed
  dev environment? Until then the webhook code ships behind tests but can't be verified
  against real Plaid.
- **Q3 (low-risk, proceeding):** OK that webhook verification defaults to **enabled**
  (Plaid JWT) but can be toggled off in sandbox for local testing? (Assumed yes.)

## Proposed issue slices (Stage 1 preview)

1. **Sandbox verification harness** — opt-in `plaid_sandbox` test/script that drives the
   real loop; docs under VERIFY LOCALLY. (FR1)
2. **Plaid error handling** — map `ApiException` to HTTP codes + re-link signal; tests. (FR2)
3. **Plaid webhook endpoint** — `POST /plaid/webhook`, `SYNC_UPDATES_AVAILABLE` handling,
   idempotency test. (FR3)
4. **Webhook verification** — Plaid JWT verification with a sandbox-disable flag; tests. (FR3, Q2/Q3)
