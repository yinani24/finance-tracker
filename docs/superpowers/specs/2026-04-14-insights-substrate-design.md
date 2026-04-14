# Insights Substrate — Design Spec

## Overview

A unified recommendation substrate that multiple domain engines (save-money, earn-more, goal-forecast, card) plug into. Engines generate `Insight` rows; a dispatcher runs them in response to data-change events; the frontend reads a single ranked list.

This spec covers **only the substrate**. The individual engines (save, earn, goal-forecast) are out of scope and will each get their own spec → plan → build cycle. The existing card-recommendation engine (see `2026-04-12-card-recommendations-design.md`) is migrated onto the substrate as part of this work.

## Goals

- One storage model and one API for all recommendation types.
- Event-driven: insights are recomputed on data changes, not on request.
- Engines are isolated: one engine failing or being slow never blocks the others.
- Honest ranking: sort by dollar impact, show effort as a badge, no hand-tuned weights.
- Lifecycle: dismiss / snooze / acted-on are first-class; history is retained.

## Non-goals

- Notifications beyond an unread counter (no email, no toasts, no push).
- Confidence scoring (dropped as YAGNI — can be added later if useful).
- Background job runner infrastructure (Celery/RQ). Dispatch runs inline on events via `asyncio`.
- Rewriting the card engine's scoring logic. Only its storage path changes.

## Data Model

### `insights`

Source of truth for every recommendation surfaced to the user.

| Column | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `user_id` | int, FK → users | indexed |
| `engine` | string(20) | `save`, `earn`, `goal_forecast`, `card` |
| `kind` | string(50) | engine-specific subtype, e.g. `subscription_unused`, `idle_cash`, `goal_off_track`, `next_card` |
| `title` | string(200) | short headline |
| `body` | text | 1–3 sentence explanation |
| `impact_one_time_cents` | int | one-shot gain (e.g. sign-up bonus). 0 if recurring. |
| `impact_annual_cents` | int | recurring annualized gain. 0 if one-shot. |
| `effort` | string(10) | `low`, `medium`, `high` |
| `evidence_json` | jsonb | `{summary: str, data_points: list}` contract |
| `action_json` | jsonb, nullable | `{label: str, kind: "internal"|"external", target: str}` or null |
| `related_goal_id` | int, FK → goals, nullable | set when the insight is scoped to a specific goal |
| `status` | string(15) | `active`, `dismissed`, `snoozed`, `acted_on`, `expired` |
| `snoozed_until` | date, nullable | |
| `dismissed_at` | datetime, nullable | |
| `dismissed_inputs_hash` | string(64), nullable | snapshot of inputs at dismiss time; used to detect "materially different" resurfacing |
| `inputs_hash` | string(64) | hash of the inputs that produced this row; used for dedup |
| `seen_at` | datetime, nullable | bumped when user opens the insights page; drives unread counter |
| `created_at` | datetime | |
| `updated_at` | datetime | |

**Unique constraint:** `(user_id, engine, kind, inputs_hash)`. Prevents duplicate inserts when an engine reruns and produces the same draft.

**Indexes:** `(user_id, status)`, `(user_id, engine)`, `(user_id, related_goal_id)`.

### Impact convention

An insight sets exactly one of `impact_one_time_cents` or `impact_annual_cents` as its "primary" impact; the other may also be nonzero if both apply. Ranking uses `impact_annual_cents` when present, otherwise `impact_one_time_cents`. The UI shows whichever is primary with the right unit ("/yr" or "one-time").

### `evidence_json` contract

```jsonc
{
  "summary": "Checking balance has averaged $8,400 over the last 90 days.",
  "data_points": [
    {"label": "Avg daily balance (90d)", "value": "$8,412"},
    {"label": "HYSA APY assumed",        "value": "4.25%"},
    {"label": "Annualized yield gap",    "value": "$357"}
  ]
}
```

Freeform beyond these two keys. The UI renders `summary` as body text and `data_points` as a key/value list. Engines may add more keys for their own detail views, but the generic list page only needs `summary` + `data_points`.

## Service Layer

### `InsightEngine` protocol

```python
class InsightEngine(Protocol):
    name: str  # "save", "earn", "goal_forecast", "card"

    def relevant_events(self) -> set[EngineEvent]: ...

    async def generate(
        self, user_id: int, ctx: EngineContext
    ) -> list[InsightDraft]: ...

    async def detect_resolution(
        self, old_insight: Insight, ctx: EngineContext
    ) -> Literal["acted_on", "expired", "still_active"]:
        # Default implementation returns "expired" for missing drafts.
        ...
```

Engines are pure-ish: they read from `ctx`, return drafts. They do not write to the DB. The dispatcher owns persistence, dedup, and lifecycle transitions.

### `InsightDraft`

```python
@dataclass
class InsightDraft:
    kind: str
    title: str
    body: str
    impact_one_time_cents: int
    impact_annual_cents: int
    effort: Literal["low", "medium", "high"]
    evidence: dict                        # becomes evidence_json
    action: dict | None                   # becomes action_json
    related_goal_id: int | None
    inputs_hash: str                      # engine computes this from the inputs it used
```

### `EngineContext`

Read-only bag of data the dispatcher pre-loads once per fire, so each engine does not re-query:

- `spending_profile: SpendingProfile | None`
- `accounts: list[Account]`
- `transactions_recent: list[Transaction]` (bounded window)
- `goals: list[Goal]`
- `cards: list[Card]`
- `plaid_items: list[PlaidItem]`

The dispatcher decides which subsets to load based on the union of what the event's engines declare they need (a small `requires` set on each engine). Unneeded fields are left unset to keep the query cheap.

### `InsightDispatcher`

Owns the full generate → diff → persist loop.

```python
class InsightDispatcher:
    async def fire(self, event: EngineEvent, user_id: int) -> None: ...
    async def fire_all(self, user_id: int) -> None: ...  # refresh endpoint
    async def wake_snoozed(self, user_id: int) -> None: ...  # lazy, called by read endpoints
```

`fire` behavior:

1. Look up engines where `event in engine.relevant_events()`.
2. Load `EngineContext` once, covering the union of required data.
3. For each engine, `asyncio.gather` with return_exceptions:
   - On exception: log error, **skip this engine**, leave its existing insights untouched. One engine's failure never affects another.
   - On success: diff the returned drafts against the user's current `active` insights for `(engine)`:
     - **New draft** (no matching `inputs_hash`): insert as `active`, unless a `dismissed` row with a matching hash exists and is <90 days old AND the impact has changed by <25% — in that case, skip.
     - **Matching draft** (hash matches an `active` row): leave alone, bump `updated_at`.
     - **Missing** (active row, no matching draft): call `engine.detect_resolution(old, ctx)`; transition to `acted_on`, `expired`, or leave as `still_active` (rare — engine asserts "problem still there, just not in current draft set").
4. Commit all changes in one transaction.

`wake_snoozed` is a lightweight query that flips any `snoozed` rows whose `snoozed_until <= today` back to `active`. It is called at the top of every `/insights` read endpoint. No cron required.

`fire_all` triggers every registered engine regardless of event — used by the `POST /insights/refresh` escape hatch and for first-time users.

### Failure isolation

Engines run under `asyncio.gather(..., return_exceptions=True)`. Exceptions are logged with engine name, user_id, and event. The dispatcher never re-raises. A failing engine leaves its prior insights in place (neither expired nor acted_on) so the user sees stable data until the bug is fixed.

### Resurface-after-dismiss logic

When an insight is dismissed, we snapshot:
- `dismissed_at = now`
- `dismissed_inputs_hash = inputs_hash`

On a subsequent `fire`, when an engine produces a draft whose `(kind)` matches a dismissed row:

- If the new `inputs_hash` equals the stored `dismissed_inputs_hash` **and** it has been <90 days: skip insert.
- If the new draft's primary impact differs from the dismissed row's primary impact by ≥25%: insert a fresh `active` row (the situation has materially changed).
- If ≥90 days have passed since dismissal: insert a fresh `active` row regardless.

This keeps dismissals "sticky enough" to not nag, but still lets the user know when something meaningful shifts.

## Events

```python
class EngineEvent(StrEnum):
    TRANSACTIONS_SYNCED   = "transactions_synced"
    TRANSACTION_MUTATED   = "transaction_mutated"
    ACCOUNT_BALANCE_CHANGED = "account_balance_changed"
    GOAL_MUTATED          = "goal_mutated"
    CARD_MUTATED          = "card_mutated"
    USER_ONBOARDED        = "user_onboarded"
```

The spec defines the enum and the dispatcher API. Implementation plan is responsible for wiring each fire-site (Plaid sync handler, transaction CRUD routes, goal routes, card routes, onboarding flow) to call `dispatcher.fire(...)`. Fire-sites are listed as a checklist in the implementation plan, not enumerated here.

Events fire inline in the request handler as `asyncio.create_task(dispatcher.fire(...))`. This keeps the API response fast and avoids introducing a job runner for now. If latency or reliability requires it later, swapping to a real queue is a dispatcher-internal change.

## API Surface

New router: `/insights`. All endpoints are authenticated and scoped to the current user.

| Method | Path | Purpose |
|---|---|---|
| GET | `/insights` | List active insights. Query: `engine`, `kind`, `effort`, `limit`, `offset`. Sorted by primary impact desc. Calls `wake_snoozed` first. |
| GET | `/insights/summary` | Counts per engine + total potential annual impact + unread count. For dashboard widget. |
| GET | `/insights/{id}` | Full insight incl. `evidence_json` and `action_json`. |
| POST | `/insights/{id}/dismiss` | Body: `{reason?: str}`. Sets status, `dismissed_at`, `dismissed_inputs_hash`. |
| POST | `/insights/{id}/snooze` | Body: `{until: date}`. |
| POST | `/insights/{id}/acted-on` | Manual resolution. |
| POST | `/insights/mark-seen` | Bumps `seen_at = now` for all currently-unseen active insights. Called when user opens the page. |
| POST | `/insights/refresh` | Force `fire_all` for current user. Debug/dev. |
| GET | `/insights/history` | List non-active insights (`dismissed`, `expired`, `acted_on`). For the "you saved $X" view. |

No public POST to create insights — creation is engine-only via the dispatcher.

### Card engine migration

The existing `/recommendations/*` endpoints and services stay functional during migration. In the implementation plan:

1. Rewrite `CardRecommendationService` to emit `InsightDraft`s and register as an `InsightEngine` (`name = "card"`).
2. Route the existing card scoring logic through the new path unchanged — only storage and surfacing change.
3. The old `/recommendations/*` routes become thin wrappers that read from `insights` filtered by `engine=card`, or redirect to `/insights?engine=card`. Deprecation is a cleanup pass, not in scope for the substrate spec.

## Ranking

Sort `active` insights by:

1. Primary impact desc (`impact_annual_cents` if nonzero, else `impact_one_time_cents`).
2. `created_at` desc as tiebreaker.

Effort is surfaced as a badge in the UI but does not enter the sort. No weighting, no hand-tuned scores — dollars are honest, users decide.

## Frontend

### Dashboard widget

- Header: "Potential: +$X/yr across N ideas" (from `/insights/summary`).
- Top 3 active insights by primary impact.
- Each row: title, impact badge ($ amount + unit), effort badge, dismiss/snooze icons.
- Click row → navigate to `/insights` with the row expanded.

### `/insights` page

- Tabs per engine: **All** (default), **Save**, **Earn**, **Goals**, **Cards**.
- Secondary filters: effort (`low|medium|high`), minimum impact.
- List is the unified `insights` model; detail is an expandable inline panel (no separate route).
- Panel shows `body`, `evidence_json` rendered as a key/value list, and the action CTA if present.
- Row-level actions: Dismiss, Snooze (date picker), Mark as done.
- Calls `POST /insights/mark-seen` on page open to clear the unread badge.
- **History tab** reads from `/insights/history`, grouped by status.

### Per-goal page

On `/goals/{id}`, show insights where `related_goal_id` matches. Same rendering component as the list. Empty state is fine and common.

### Sidebar unread counter

Small numeric badge on the "Insights" sidebar link equal to `summary.unread_count`. No toasts, no email, no push. The counter decrements only via `POST /insights/mark-seen`.

### `/recommendations` deprecation

`/recommendations` redirects to `/insights?engine=card`. The old page component is removed in the migration step.

## Testing

- **Unit:** dispatcher diff logic (new / matching / missing / dismissed-sticky / resurface-after-25%-change / resurface-after-90-days), engine failure isolation (one throws, others persist), `wake_snoozed` transitions.
- **Unit:** `InsightDraft` → `insights` row persistence with unique-constraint dedup.
- **Integration:** fake engine registered, event fired, row appears in DB and in `/insights` response; dismiss → hidden from `/insights`, visible in `/insights/history`; snooze → hidden, reappears after `snoozed_until`.
- **Integration:** card engine migrated onto substrate still produces equivalent results (snapshot test against the current `/recommendations/next-card` output).
- Target 100% coverage on substrate files per project convention.

## Open questions deferred to later specs

- Save / earn / goal-forecast engine designs (each gets its own spec).
- Notification transport upgrades (email, push).
- Per-engine resolution detection heuristics (each engine defines its own).
- History analytics ("you've saved $X by acting on these").
