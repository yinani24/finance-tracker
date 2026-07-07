# Insights Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified insights substrate that multiple recommendation engines (save, earn, goal-forecast, card) plug into, replacing the standalone card-recommendation storage layer.

**Architecture:** Event-driven dispatcher runs registered engines when data changes (Plaid sync, transaction/goal/card CRUD). Engines produce `InsightDraft`s; the dispatcher diffs them against existing rows, deduplicates via `inputs_hash`, and manages lifecycle (dismiss/snooze/expire/acted_on). A single `/insights` API and React page surfaces all insights ranked by dollar impact.

**Tech Stack:** Python, FastAPI, SQLAlchemy (sync), Alembic, PostgreSQL, pytest, Next.js, React Query, Tailwind/shadcn

**Spec:** `docs/superpowers/specs/2026-04-14-insights-substrate-design.md`

---

## File Structure

### Backend — New files

| File | Responsibility |
|------|----------------|
| `apps/api/app/models/insight.py` | `Insight` SQLAlchemy model |
| `apps/api/app/repositories/insight.py` | `InsightRepository` — CRUD, status transitions, queries |
| `apps/api/app/schemas/insight.py` | Pydantic request/response models |
| `apps/api/app/services/insight_types.py` | Core types: `InsightDraft`, `EngineContext`, `EngineEvent`, `InsightEngine` protocol |
| `apps/api/app/services/insight_dispatcher.py` | `InsightDispatcher` — register engines, fire events, diff/persist |
| `apps/api/app/services/card_insight_engine.py` | `CardInsightEngine` — adapts existing `CardRecommendationService` to the `InsightEngine` protocol |
| `apps/api/app/api/insights.py` | FastAPI router for `/insights` endpoints |
| `apps/api/alembic/versions/<auto>_add_insights_table.py` | Migration for `insights` table |
| `apps/api/tests/test_insight_model.py` | Model tests |
| `apps/api/tests/test_insight_repository.py` | Repository tests |
| `apps/api/tests/test_insight_dispatcher.py` | Dispatcher logic tests |
| `apps/api/tests/test_card_insight_engine.py` | Card engine adapter tests |
| `apps/api/tests/test_insights_api.py` | API integration tests |

### Backend — Modified files

| File | Change |
|------|--------|
| `apps/api/app/models/__init__.py` | Add `Insight` import |
| `apps/api/app/api/router.py` | Register insights router |
| `apps/api/app/api/plaid.py` | Fire `TRANSACTIONS_SYNCED` after sync |
| `apps/api/app/api/transactions.py` | Fire `TRANSACTION_MUTATED` after create/update |
| `apps/api/app/api/goals.py` | Fire `GOAL_MUTATED` after create/update |
| `apps/api/app/api/cards.py` | Fire `CARD_MUTATED` after create/update/delete |

### Frontend — New files

| File | Responsibility |
|------|----------------|
| `apps/web/src/app/(app)/insights/page.tsx` | Insights page with engine tabs, filters, detail panels |
| `apps/web/src/components/insights-widget.tsx` | Dashboard widget showing top 3 insights |

### Frontend — Modified files

| File | Change |
|------|--------|
| `apps/web/src/lib/types.ts` | Add `Insight`, `InsightSummary` types |
| `apps/web/src/lib/api.ts` | Add insights API functions |
| `apps/web/src/components/sidebar.tsx` | Rename Recommendations → Insights, add unread badge |
| `apps/web/src/app/(app)/recommendations/page.tsx` | Redirect to `/insights?engine=card` |

---

## Task 1: Insight Model + Migration

**Files:**
- Create: `apps/api/app/models/insight.py`
- Modify: `apps/api/app/models/__init__.py`
- Test: `apps/api/tests/test_insight_model.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_insight_model.py`:

```python
import json
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.insight import Insight


def test_create_insight(db_session: Session, seed_user):
    insight = Insight(
        user_id=seed_user.id,
        engine="save",
        kind="idle_cash",
        title="Move $8,400 to HYSA",
        body="Your checking account has averaged $8,400 over 90 days.",
        impact_one_time_cents=0,
        impact_annual_cents=35700,
        effort="low",
        evidence_json=json.dumps({"summary": "test", "data_points": []}),
        action_json=json.dumps({"label": "Open HYSA", "kind": "external", "target": "https://example.com"}),
        status="active",
        inputs_hash="abc123",
    )
    db_session.add(insight)
    db_session.commit()
    db_session.refresh(insight)

    assert insight.id is not None
    assert insight.engine == "save"
    assert insight.kind == "idle_cash"
    assert insight.impact_annual_cents == 35700
    assert insight.status == "active"
    assert insight.created_at is not None


def test_unique_constraint_prevents_duplicates(db_session: Session, seed_user):
    kwargs = dict(
        user_id=seed_user.id,
        engine="save",
        kind="idle_cash",
        title="Move $8,400 to HYSA",
        body="test",
        impact_one_time_cents=0,
        impact_annual_cents=35700,
        effort="low",
        evidence_json="{}",
        status="active",
        inputs_hash="same_hash",
    )
    db_session.add(Insight(**kwargs))
    db_session.commit()

    db_session.add(Insight(**kwargs))
    from sqlalchemy.exc import IntegrityError
    import pytest
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_nullable_fields_default(db_session: Session, seed_user):
    insight = Insight(
        user_id=seed_user.id,
        engine="card",
        kind="next_card",
        title="Get Chase Sapphire",
        body="test",
        impact_one_time_cents=60000,
        impact_annual_cents=0,
        effort="medium",
        evidence_json="{}",
        status="active",
        inputs_hash="xyz789",
    )
    db_session.add(insight)
    db_session.commit()
    db_session.refresh(insight)

    assert insight.action_json is None
    assert insight.related_goal_id is None
    assert insight.snoozed_until is None
    assert insight.dismissed_at is None
    assert insight.dismissed_inputs_hash is None
    assert insight.seen_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_insight_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.insight'`

- [ ] **Step 3: Write the Insight model**

Create `apps/api/app/models/insight.py`:

```python
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Insight(Base):
    __tablename__ = "insights"
    __table_args__ = (
        UniqueConstraint("user_id", "engine", "kind", "inputs_hash", name="uq_insights_user_engine_kind_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    engine: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    impact_one_time_cents: Mapped[int] = mapped_column(Integer, default=0)
    impact_annual_cents: Mapped[int] = mapped_column(Integer, default=0)
    effort: Mapped[str] = mapped_column(String(10))
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    action_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_goal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("goals.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="active")
    snoozed_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dismissed_inputs_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    inputs_hash: Mapped[str] = mapped_column(String(64))
    seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: Register model in `__init__.py`**

Add to `apps/api/app/models/__init__.py`:

```python
from app.models.insight import Insight
```

And add `"Insight"` to the `__all__` list.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/api && python -m pytest tests/test_insight_model.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Generate Alembic migration**

Run: `cd apps/api && alembic revision --autogenerate -m "add insights table"`

Verify the generated migration creates the `insights` table with all columns and the unique constraint.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/models/insight.py apps/api/app/models/__init__.py apps/api/tests/test_insight_model.py apps/api/alembic/versions/*_add_insights_table.py
git commit -m "feat: add Insight model and migration"
```

---

## Task 2: Insight Repository

**Files:**
- Create: `apps/api/app/repositories/insight.py`
- Test: `apps/api/tests/test_insight_repository.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_insight_repository.py`:

```python
import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.insight import Insight
from app.repositories.insight import InsightRepository


def _make_insight(db: Session, user_id: int, **overrides) -> Insight:
    defaults = dict(
        user_id=user_id,
        engine="save",
        kind="idle_cash",
        title="Test insight",
        body="Test body",
        impact_one_time_cents=0,
        impact_annual_cents=10000,
        effort="low",
        evidence_json=json.dumps({"summary": "test", "data_points": []}),
        status="active",
        inputs_hash="hash_default",
    )
    defaults.update(overrides)
    row = Insight(**defaults)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_list_active_returns_only_active(db_session: Session, seed_user):
    _make_insight(db_session, seed_user.id, inputs_hash="h1")
    _make_insight(db_session, seed_user.id, inputs_hash="h2", status="dismissed")

    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id)
    assert len(results) == 1
    assert results[0].status == "active"


def test_list_active_sorted_by_annual_then_one_time(db_session: Session, seed_user):
    _make_insight(db_session, seed_user.id, inputs_hash="h1", impact_annual_cents=5000, impact_one_time_cents=0)
    _make_insight(db_session, seed_user.id, inputs_hash="h2", impact_annual_cents=20000, impact_one_time_cents=0)
    _make_insight(db_session, seed_user.id, inputs_hash="h3", impact_annual_cents=0, impact_one_time_cents=90000)

    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id)
    assert [r.inputs_hash for r in results] == ["h3", "h2", "h1"]


def test_list_active_filters_by_engine(db_session: Session, seed_user):
    _make_insight(db_session, seed_user.id, inputs_hash="h1", engine="save")
    _make_insight(db_session, seed_user.id, inputs_hash="h2", engine="card")

    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id, engine="save")
    assert len(results) == 1
    assert results[0].engine == "save"


def test_get_by_id(db_session: Session, seed_user):
    row = _make_insight(db_session, seed_user.id)
    repo = InsightRepository(db_session)
    found = repo.get(row.id, seed_user.id)
    assert found is not None
    assert found.id == row.id


def test_get_by_id_wrong_user_returns_none(db_session: Session, seed_user):
    row = _make_insight(db_session, seed_user.id)
    repo = InsightRepository(db_session)
    assert repo.get(row.id, 9999) is None


def test_dismiss(db_session: Session, seed_user):
    row = _make_insight(db_session, seed_user.id)
    repo = InsightRepository(db_session)
    repo.dismiss(row, reason="not useful")
    db_session.refresh(row)
    assert row.status == "dismissed"
    assert row.dismissed_at is not None
    assert row.dismissed_inputs_hash == row.inputs_hash


def test_snooze(db_session: Session, seed_user):
    row = _make_insight(db_session, seed_user.id)
    repo = InsightRepository(db_session)
    until = date.today() + timedelta(days=30)
    repo.snooze(row, until)
    db_session.refresh(row)
    assert row.status == "snoozed"
    assert row.snoozed_until == until


def test_mark_acted_on(db_session: Session, seed_user):
    row = _make_insight(db_session, seed_user.id)
    repo = InsightRepository(db_session)
    repo.mark_acted_on(row)
    db_session.refresh(row)
    assert row.status == "acted_on"


def test_mark_seen(db_session: Session, seed_user):
    _make_insight(db_session, seed_user.id, inputs_hash="h1")
    _make_insight(db_session, seed_user.id, inputs_hash="h2")

    repo = InsightRepository(db_session)
    count = repo.mark_seen(seed_user.id)
    assert count == 2


def test_wake_snoozed(db_session: Session, seed_user):
    yesterday = date.today() - timedelta(days=1)
    tomorrow = date.today() + timedelta(days=1)
    _make_insight(db_session, seed_user.id, inputs_hash="h1", status="snoozed", snoozed_until=yesterday)
    _make_insight(db_session, seed_user.id, inputs_hash="h2", status="snoozed", snoozed_until=tomorrow)

    repo = InsightRepository(db_session)
    woke = repo.wake_snoozed(seed_user.id)
    assert woke == 1

    results = repo.list_active(seed_user.id)
    assert len(results) == 1
    assert results[0].inputs_hash == "h1"


def test_summary(db_session: Session, seed_user):
    _make_insight(db_session, seed_user.id, inputs_hash="h1", engine="save", impact_annual_cents=10000)
    _make_insight(db_session, seed_user.id, inputs_hash="h2", engine="card", impact_annual_cents=5000)
    _make_insight(db_session, seed_user.id, inputs_hash="h3", engine="save", impact_annual_cents=3000, seen_at=datetime.now(timezone.utc))

    repo = InsightRepository(db_session)
    summary = repo.summary(seed_user.id)
    assert summary["total_active"] == 3
    assert summary["total_annual_impact_cents"] == 18000
    assert summary["unread_count"] == 2
    assert summary["by_engine"]["save"] == 2
    assert summary["by_engine"]["card"] == 1


def test_list_history(db_session: Session, seed_user):
    _make_insight(db_session, seed_user.id, inputs_hash="h1", status="active")
    _make_insight(db_session, seed_user.id, inputs_hash="h2", status="dismissed")
    _make_insight(db_session, seed_user.id, inputs_hash="h3", status="acted_on")

    repo = InsightRepository(db_session)
    history = repo.list_history(seed_user.id)
    assert len(history) == 2
    statuses = {r.status for r in history}
    assert statuses == {"dismissed", "acted_on"}


def test_find_dismissed_by_kind(db_session: Session, seed_user):
    _make_insight(
        db_session, seed_user.id, inputs_hash="h1", status="dismissed",
        dismissed_inputs_hash="old_hash",
        dismissed_at=datetime.now(timezone.utc),
    )
    repo = InsightRepository(db_session)
    found = repo.find_dismissed_by_kind(seed_user.id, "save", "idle_cash")
    assert found is not None
    assert found.dismissed_inputs_hash == "old_hash"


def test_upsert_draft_creates_new(db_session: Session, seed_user):
    repo = InsightRepository(db_session)
    row = repo.upsert_draft(
        user_id=seed_user.id,
        engine="save",
        kind="idle_cash",
        title="Move money",
        body="body",
        impact_one_time_cents=0,
        impact_annual_cents=35000,
        effort="low",
        evidence_json="{}",
        action_json=None,
        related_goal_id=None,
        inputs_hash="new_hash",
    )
    assert row.id is not None
    assert row.status == "active"


def test_upsert_draft_updates_existing(db_session: Session, seed_user):
    repo = InsightRepository(db_session)
    row1 = repo.upsert_draft(
        user_id=seed_user.id, engine="save", kind="idle_cash", title="Old title",
        body="body", impact_one_time_cents=0, impact_annual_cents=35000, effort="low",
        evidence_json="{}", action_json=None, related_goal_id=None, inputs_hash="same_hash",
    )
    row2 = repo.upsert_draft(
        user_id=seed_user.id, engine="save", kind="idle_cash", title="New title",
        body="body", impact_one_time_cents=0, impact_annual_cents=40000, effort="low",
        evidence_json="{}", action_json=None, related_goal_id=None, inputs_hash="same_hash",
    )
    assert row2.id == row1.id
    assert row2.title == "New title"
    assert row2.impact_annual_cents == 40000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_insight_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.repositories.insight'`

- [ ] **Step 3: Write the InsightRepository**

Create `apps/api/app/repositories/insight.py`:

```python
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from app.models.insight import Insight


class InsightRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, insight_id: int, user_id: int) -> Optional[Insight]:
        stmt = select(Insight).where(Insight.id == insight_id, Insight.user_id == user_id)
        return self.db.scalars(stmt).first()

    def list_active(
        self,
        user_id: int,
        engine: Optional[str] = None,
        effort: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Insight]:
        sort_key = case(
            (Insight.impact_annual_cents > 0, Insight.impact_annual_cents),
            else_=Insight.impact_one_time_cents,
        )
        stmt = (
            select(Insight)
            .where(Insight.user_id == user_id, Insight.status == "active")
            .order_by(sort_key.desc(), Insight.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if engine:
            stmt = stmt.where(Insight.engine == engine)
        if effort:
            stmt = stmt.where(Insight.effort == effort)
        return list(self.db.scalars(stmt).all())

    def list_history(self, user_id: int, limit: int = 50, offset: int = 0) -> list[Insight]:
        stmt = (
            select(Insight)
            .where(
                Insight.user_id == user_id,
                Insight.status.in_(["dismissed", "expired", "acted_on"]),
            )
            .order_by(Insight.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all())

    def summary(self, user_id: int) -> dict:
        stmt = select(Insight).where(Insight.user_id == user_id, Insight.status == "active")
        rows = list(self.db.scalars(stmt).all())

        by_engine: dict[str, int] = {}
        total_annual = 0
        unread = 0
        for r in rows:
            by_engine[r.engine] = by_engine.get(r.engine, 0) + 1
            total_annual += r.impact_annual_cents if r.impact_annual_cents else r.impact_one_time_cents
            if r.seen_at is None:
                unread += 1

        return {
            "total_active": len(rows),
            "total_annual_impact_cents": total_annual,
            "unread_count": unread,
            "by_engine": by_engine,
        }

    def dismiss(self, insight: Insight, reason: Optional[str] = None) -> None:
        insight.status = "dismissed"
        insight.dismissed_at = datetime.now(timezone.utc)
        insight.dismissed_inputs_hash = insight.inputs_hash
        self.db.commit()

    def snooze(self, insight: Insight, until: date) -> None:
        insight.status = "snoozed"
        insight.snoozed_until = until
        self.db.commit()

    def mark_acted_on(self, insight: Insight) -> None:
        insight.status = "acted_on"
        self.db.commit()

    def mark_seen(self, user_id: int) -> int:
        now = datetime.now(timezone.utc)
        stmt = (
            update(Insight)
            .where(Insight.user_id == user_id, Insight.status == "active", Insight.seen_at.is_(None))
            .values(seen_at=now)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount

    def wake_snoozed(self, user_id: int) -> int:
        today = date.today()
        stmt = (
            update(Insight)
            .where(
                Insight.user_id == user_id,
                Insight.status == "snoozed",
                Insight.snoozed_until <= today,
            )
            .values(status="active", snoozed_until=None)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount

    def find_dismissed_by_kind(
        self, user_id: int, engine: str, kind: str
    ) -> Optional[Insight]:
        stmt = (
            select(Insight)
            .where(
                Insight.user_id == user_id,
                Insight.engine == engine,
                Insight.kind == kind,
                Insight.status == "dismissed",
            )
            .order_by(Insight.dismissed_at.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def get_active_by_engine(self, user_id: int, engine: str) -> list[Insight]:
        stmt = (
            select(Insight)
            .where(Insight.user_id == user_id, Insight.engine == engine, Insight.status == "active")
        )
        return list(self.db.scalars(stmt).all())

    def expire(self, insight: Insight) -> None:
        insight.status = "expired"
        self.db.commit()

    def upsert_draft(
        self,
        user_id: int,
        engine: str,
        kind: str,
        title: str,
        body: str,
        impact_one_time_cents: int,
        impact_annual_cents: int,
        effort: str,
        evidence_json: str,
        action_json: Optional[str],
        related_goal_id: Optional[int],
        inputs_hash: str,
    ) -> Insight:
        stmt = select(Insight).where(
            Insight.user_id == user_id,
            Insight.engine == engine,
            Insight.kind == kind,
            Insight.inputs_hash == inputs_hash,
        )
        existing = self.db.scalars(stmt).first()
        if existing:
            existing.title = title
            existing.body = body
            existing.impact_one_time_cents = impact_one_time_cents
            existing.impact_annual_cents = impact_annual_cents
            existing.effort = effort
            existing.evidence_json = evidence_json
            existing.action_json = action_json
            existing.related_goal_id = related_goal_id
            self.db.commit()
            self.db.refresh(existing)
            return existing

        row = Insight(
            user_id=user_id,
            engine=engine,
            kind=kind,
            title=title,
            body=body,
            impact_one_time_cents=impact_one_time_cents,
            impact_annual_cents=impact_annual_cents,
            effort=effort,
            evidence_json=evidence_json,
            action_json=action_json,
            related_goal_id=related_goal_id,
            status="active",
            inputs_hash=inputs_hash,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_insight_repository.py -v`
Expected: All 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/repositories/insight.py apps/api/tests/test_insight_repository.py
git commit -m "feat: add InsightRepository with full lifecycle operations"
```

---

## Task 3: Core Types (InsightDraft, EngineContext, EngineEvent, InsightEngine Protocol)

**Files:**
- Create: `apps/api/app/services/insight_types.py`

- [ ] **Step 1: Write the types module**

Create `apps/api/app/services/insight_types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Optional, Protocol

from app.models.account import Account
from app.models.card import Card
from app.models.goal import Goal
from app.models.insight import Insight
from app.models.plaid_item import PlaidItem
from app.models.spending_profile import SpendingProfile
from app.models.transaction import Transaction


class EngineEvent(StrEnum):
    TRANSACTIONS_SYNCED = "transactions_synced"
    TRANSACTION_MUTATED = "transaction_mutated"
    ACCOUNT_BALANCE_CHANGED = "account_balance_changed"
    GOAL_MUTATED = "goal_mutated"
    CARD_MUTATED = "card_mutated"
    USER_ONBOARDED = "user_onboarded"


@dataclass
class EngineContext:
    spending_profile: Optional[SpendingProfile] = None
    accounts: list[Account] = field(default_factory=list)
    transactions_recent: list[Transaction] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    cards: list[Card] = field(default_factory=list)
    plaid_items: list[PlaidItem] = field(default_factory=list)


@dataclass
class InsightDraft:
    kind: str
    title: str
    body: str
    impact_one_time_cents: int
    impact_annual_cents: int
    effort: Literal["low", "medium", "high"]
    evidence: dict
    action: Optional[dict]
    related_goal_id: Optional[int]
    inputs_hash: str


class InsightEngine(Protocol):
    name: str

    def relevant_events(self) -> set[EngineEvent]: ...

    def generate(self, user_id: int, ctx: EngineContext) -> list[InsightDraft]: ...

    def detect_resolution(
        self, old_insight: Insight, ctx: EngineContext
    ) -> Literal["acted_on", "expired", "still_active"]:
        return "expired"
```

- [ ] **Step 2: Verify import works**

Run: `cd apps/api && python -c "from app.services.insight_types import EngineEvent, InsightDraft, EngineContext, InsightEngine; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/services/insight_types.py
git commit -m "feat: add core insight types (InsightDraft, EngineContext, EngineEvent, InsightEngine protocol)"
```

---

## Task 4: InsightDispatcher — Core Fire Logic

**Files:**
- Create: `apps/api/app/services/insight_dispatcher.py`
- Test: `apps/api/tests/test_insight_dispatcher.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_insight_dispatcher.py`:

```python
import json
from typing import Literal, Optional

from sqlalchemy.orm import Session

from app.models.insight import Insight
from app.repositories.insight import InsightRepository
from app.services.insight_dispatcher import InsightDispatcher
from app.services.insight_types import (
    EngineContext,
    EngineEvent,
    InsightDraft,
    InsightEngine,
)


class FakeEngine:
    name = "test_engine"

    def __init__(self, drafts: Optional[list[InsightDraft]] = None, should_raise: bool = False):
        self._drafts = drafts or []
        self._should_raise = should_raise

    def relevant_events(self) -> set[EngineEvent]:
        return {EngineEvent.TRANSACTIONS_SYNCED}

    def generate(self, user_id: int, ctx: EngineContext) -> list[InsightDraft]:
        if self._should_raise:
            raise RuntimeError("engine crashed")
        return self._drafts

    def detect_resolution(
        self, old_insight: Insight, ctx: EngineContext
    ) -> Literal["acted_on", "expired", "still_active"]:
        return "expired"


def _draft(kind="test_kind", hash_val="h1", annual=10000) -> InsightDraft:
    return InsightDraft(
        kind=kind,
        title=f"Test {kind}",
        body="test body",
        impact_one_time_cents=0,
        impact_annual_cents=annual,
        effort="low",
        evidence={"summary": "test", "data_points": []},
        action=None,
        related_goal_id=None,
        inputs_hash=hash_val,
    )


def test_fire_creates_insights(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft()])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)

    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)

    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id)
    assert len(results) == 1
    assert results[0].engine == "test_engine"
    assert results[0].kind == "test_kind"


def test_fire_skips_irrelevant_engines(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft()])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)

    dispatcher.fire(EngineEvent.GOAL_MUTATED, seed_user.id)

    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id)
    assert len(results) == 0


def test_fire_isolates_engine_failure(db_session: Session, seed_user):
    good_engine = FakeEngine(drafts=[_draft(hash_val="good")])
    good_engine.name = "good_engine"
    bad_engine = FakeEngine(should_raise=True)
    bad_engine.name = "bad_engine"

    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(good_engine)
    dispatcher.register(bad_engine)

    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)

    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id)
    assert len(results) == 1
    assert results[0].engine == "good_engine"


def test_fire_expires_missing_drafts(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft()])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)

    engine._drafts = []
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)

    repo = InsightRepository(db_session)
    active = repo.list_active(seed_user.id)
    assert len(active) == 0
    history = repo.list_history(seed_user.id)
    assert len(history) == 1
    assert history[0].status == "expired"


def test_fire_keeps_matching_drafts(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft()])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)

    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)
    repo = InsightRepository(db_session)
    first_id = repo.list_active(seed_user.id)[0].id

    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)
    results = repo.list_active(seed_user.id)
    assert len(results) == 1
    assert results[0].id == first_id


def test_fire_all_runs_every_engine(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft()])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)

    dispatcher.fire_all(seed_user.id)

    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id)
    assert len(results) == 1


def test_fire_respects_dismissed_sticky(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft()])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)

    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)

    repo = InsightRepository(db_session)
    insight = repo.list_active(seed_user.id)[0]
    repo.dismiss(insight)

    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)

    active = repo.list_active(seed_user.id)
    assert len(active) == 0


def test_fire_resurfaces_after_material_change(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft(hash_val="v1", annual=10000)])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)

    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)

    repo = InsightRepository(db_session)
    insight = repo.list_active(seed_user.id)[0]
    repo.dismiss(insight)

    engine._drafts = [_draft(hash_val="v2", annual=15000)]
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)

    active = repo.list_active(seed_user.id)
    assert len(active) == 1
    assert active[0].impact_annual_cents == 15000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_insight_dispatcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.insight_dispatcher'`

- [ ] **Step 3: Write the InsightDispatcher**

Create `apps/api/app/services/insight_dispatcher.py`:

```python
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.card import Card
from app.models.goal import Goal
from app.models.insight import Insight
from app.models.plaid_item import PlaidItem
from app.models.transaction import Transaction
from app.repositories.insight import InsightRepository
from app.services.insight_types import (
    EngineContext,
    EngineEvent,
    InsightDraft,
    InsightEngine,
)
from app.services.spending_profile import get_or_refresh

logger = logging.getLogger(__name__)

DISMISS_STICKY_DAYS = 90
DISMISS_RESURFACE_THRESHOLD = 0.25


class InsightDispatcher:
    def __init__(self, db: Session):
        self.db = db
        self._engines: list[InsightEngine] = []

    def register(self, engine: InsightEngine) -> None:
        self._engines.append(engine)

    def fire(self, event: EngineEvent, user_id: int) -> None:
        engines = [e for e in self._engines if event in e.relevant_events()]
        if not engines:
            return
        ctx = self._build_context(user_id)
        for engine in engines:
            self._run_engine(engine, user_id, ctx)

    def fire_all(self, user_id: int) -> None:
        if not self._engines:
            return
        ctx = self._build_context(user_id)
        for engine in self._engines:
            self._run_engine(engine, user_id, ctx)

    def _build_context(self, user_id: int) -> EngineContext:
        try:
            profile = get_or_refresh(self.db, user_id)
        except Exception:
            profile = None

        accounts = list(self.db.scalars(
            select(Account).where(Account.user_id == user_id)
        ).all())
        cards = list(self.db.scalars(
            select(Card).where(Card.user_id == user_id)
        ).all())
        goals = list(self.db.scalars(
            select(Goal).where(Goal.user_id == user_id)
        ).all())
        plaid_items = list(self.db.scalars(
            select(PlaidItem).where(PlaidItem.user_id == user_id)
        ).all())
        transactions = list(self.db.scalars(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.occurred_on.desc())
            .limit(500)
        ).all())

        return EngineContext(
            spending_profile=profile,
            accounts=accounts,
            cards=cards,
            goals=goals,
            plaid_items=plaid_items,
            transactions_recent=transactions,
        )

    def _run_engine(self, engine: InsightEngine, user_id: int, ctx: EngineContext) -> None:
        try:
            drafts = engine.generate(user_id, ctx)
        except Exception:
            logger.exception("Insight engine '%s' failed for user %d", engine.name, user_id)
            return

        repo = InsightRepository(self.db)
        existing = repo.get_active_by_engine(user_id, engine.name)
        existing_by_hash = {row.inputs_hash: row for row in existing}

        new_hashes: set[str] = set()
        for draft in drafts:
            new_hashes.add(draft.inputs_hash)
            if draft.inputs_hash in existing_by_hash:
                row = existing_by_hash[draft.inputs_hash]
                row.title = draft.title
                row.body = draft.body
                row.impact_one_time_cents = draft.impact_one_time_cents
                row.impact_annual_cents = draft.impact_annual_cents
                row.effort = draft.effort
                row.evidence_json = json.dumps(draft.evidence)
                row.action_json = json.dumps(draft.action) if draft.action else None
                row.related_goal_id = draft.related_goal_id
                continue

            if self._is_dismissed_sticky(repo, user_id, engine.name, draft):
                continue

            repo.upsert_draft(
                user_id=user_id,
                engine=engine.name,
                kind=draft.kind,
                title=draft.title,
                body=draft.body,
                impact_one_time_cents=draft.impact_one_time_cents,
                impact_annual_cents=draft.impact_annual_cents,
                effort=draft.effort,
                evidence_json=json.dumps(draft.evidence),
                action_json=json.dumps(draft.action) if draft.action else None,
                related_goal_id=draft.related_goal_id,
                inputs_hash=draft.inputs_hash,
            )

        for old_hash, old_row in existing_by_hash.items():
            if old_hash not in new_hashes:
                try:
                    resolution = engine.detect_resolution(old_row, ctx)
                except Exception:
                    resolution = "expired"
                if resolution == "acted_on":
                    repo.mark_acted_on(old_row)
                elif resolution == "expired":
                    repo.expire(old_row)

        self.db.commit()

    def _is_dismissed_sticky(
        self,
        repo: InsightRepository,
        user_id: int,
        engine_name: str,
        draft: InsightDraft,
    ) -> bool:
        dismissed = repo.find_dismissed_by_kind(user_id, engine_name, draft.kind)
        if dismissed is None:
            return False

        now = datetime.now(timezone.utc)
        dismissed_at = dismissed.dismissed_at
        if dismissed_at and dismissed_at.tzinfo is None:
            dismissed_at = dismissed_at.replace(tzinfo=timezone.utc)

        if dismissed_at and (now - dismissed_at) > timedelta(days=DISMISS_STICKY_DAYS):
            return False

        old_impact = dismissed.impact_annual_cents or dismissed.impact_one_time_cents
        new_impact = draft.impact_annual_cents or draft.impact_one_time_cents
        if old_impact > 0:
            change_ratio = abs(new_impact - old_impact) / old_impact
            if change_ratio >= DISMISS_RESURFACE_THRESHOLD:
                return False

        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_insight_dispatcher.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/insight_dispatcher.py apps/api/tests/test_insight_dispatcher.py
git commit -m "feat: add InsightDispatcher with diff, failure isolation, and dismiss-sticky logic"
```

---

## Task 5: Insight Schemas (Pydantic)

**Files:**
- Create: `apps/api/app/schemas/insight.py`

- [ ] **Step 1: Create the schemas**

Create `apps/api/app/schemas/insight.py`:

```python
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class InsightRead(BaseModel):
    id: int
    engine: str
    kind: str
    title: str
    body: str
    impact_one_time_cents: int
    impact_annual_cents: int
    effort: str
    evidence_json: str
    action_json: Optional[str]
    related_goal_id: Optional[int]
    status: str
    snoozed_until: Optional[date]
    seen_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InsightSummary(BaseModel):
    total_active: int
    total_annual_impact_cents: int
    unread_count: int
    by_engine: dict[str, int]


class DismissRequest(BaseModel):
    reason: Optional[str] = None


class SnoozeRequest(BaseModel):
    until: date


class MarkSeenResponse(BaseModel):
    marked: int
```

- [ ] **Step 2: Verify import works**

Run: `cd apps/api && python -c "from app.schemas.insight import InsightRead, InsightSummary; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/schemas/insight.py
git commit -m "feat: add Pydantic schemas for insights API"
```

---

## Task 6: Insights API Router

**Files:**
- Create: `apps/api/app/api/insights.py`
- Modify: `apps/api/app/api/router.py`
- Test: `apps/api/tests/test_insights_api.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_insights_api.py`:

```python
import json
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.insight import Insight


def _create_insight(db: Session, user_id: int, **overrides) -> Insight:
    defaults = dict(
        user_id=user_id,
        engine="save",
        kind="idle_cash",
        title="Move money to HYSA",
        body="Your checking has excess cash",
        impact_one_time_cents=0,
        impact_annual_cents=35000,
        effort="low",
        evidence_json=json.dumps({"summary": "test", "data_points": []}),
        status="active",
        inputs_hash="default_hash",
    )
    defaults.update(overrides)
    row = Insight(**defaults)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_list_insights(client: TestClient, db_session: Session, seed_user):
    _create_insight(db_session, seed_user.id, inputs_hash="h1")
    _create_insight(db_session, seed_user.id, inputs_hash="h2", status="dismissed")
    resp = client.get("/insights")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1


def test_list_insights_filter_engine(client: TestClient, db_session: Session, seed_user):
    _create_insight(db_session, seed_user.id, inputs_hash="h1", engine="save")
    _create_insight(db_session, seed_user.id, inputs_hash="h2", engine="card")
    resp = client.get("/insights?engine=save")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_insight(client: TestClient, db_session: Session, seed_user):
    row = _create_insight(db_session, seed_user.id)
    resp = client.get(f"/insights/{row.id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Move money to HYSA"


def test_get_insight_not_found(client: TestClient, seed_user):
    resp = client.get("/insights/99999")
    assert resp.status_code == 404


def test_summary(client: TestClient, db_session: Session, seed_user):
    _create_insight(db_session, seed_user.id, inputs_hash="h1", engine="save", impact_annual_cents=10000)
    _create_insight(db_session, seed_user.id, inputs_hash="h2", engine="card", impact_annual_cents=5000)
    resp = client.get("/insights/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_active"] == 2
    assert data["total_annual_impact_cents"] == 15000
    assert data["unread_count"] == 2


def test_dismiss(client: TestClient, db_session: Session, seed_user):
    row = _create_insight(db_session, seed_user.id)
    resp = client.post(f"/insights/{row.id}/dismiss", json={"reason": "not useful"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"


def test_snooze(client: TestClient, db_session: Session, seed_user):
    row = _create_insight(db_session, seed_user.id)
    until = (date.today() + timedelta(days=30)).isoformat()
    resp = client.post(f"/insights/{row.id}/snooze", json={"until": until})
    assert resp.status_code == 200
    assert resp.json()["status"] == "snoozed"


def test_acted_on(client: TestClient, db_session: Session, seed_user):
    row = _create_insight(db_session, seed_user.id)
    resp = client.post(f"/insights/{row.id}/acted-on")
    assert resp.status_code == 200
    assert resp.json()["status"] == "acted_on"


def test_mark_seen(client: TestClient, db_session: Session, seed_user):
    _create_insight(db_session, seed_user.id, inputs_hash="h1")
    _create_insight(db_session, seed_user.id, inputs_hash="h2")
    resp = client.post("/insights/mark-seen")
    assert resp.status_code == 200
    assert resp.json()["marked"] == 2


def test_history(client: TestClient, db_session: Session, seed_user):
    _create_insight(db_session, seed_user.id, inputs_hash="h1", status="active")
    _create_insight(db_session, seed_user.id, inputs_hash="h2", status="dismissed")
    _create_insight(db_session, seed_user.id, inputs_hash="h3", status="acted_on")
    resp = client.get("/insights/history")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_refresh(client: TestClient, seed_user):
    resp = client.post("/insights/refresh")
    assert resp.status_code == 200
    assert resp.json()["status"] == "refreshed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_insights_api.py -v`
Expected: FAIL — routing not registered

- [ ] **Step 3: Write the insights router**

Create `apps/api/app/api/insights.py`:

```python
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.repositories.insight import InsightRepository
from app.schemas.insight import (
    DismissRequest,
    InsightRead,
    InsightSummary,
    MarkSeenResponse,
    SnoozeRequest,
)
from app.services.insight_dispatcher import InsightDispatcher

router = APIRouter(prefix="/insights", tags=["insights"])


def _get_dispatcher(db: Session) -> InsightDispatcher:
    return InsightDispatcher(db)


@router.get("", response_model=list[InsightRead])
def list_insights(
    engine: Optional[str] = None,
    effort: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[InsightRead]:
    repo = InsightRepository(db)
    repo.wake_snoozed(user_id)
    return repo.list_active(user_id, engine=engine, effort=effort, limit=limit, offset=offset)


@router.get("/summary", response_model=InsightSummary)
def get_summary(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> InsightSummary:
    repo = InsightRepository(db)
    repo.wake_snoozed(user_id)
    return repo.summary(user_id)


@router.get("/history", response_model=list[InsightRead])
def list_history(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[InsightRead]:
    repo = InsightRepository(db)
    return repo.list_history(user_id, limit=limit, offset=offset)


@router.get("/{insight_id}", response_model=InsightRead)
def get_insight(
    insight_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> InsightRead:
    repo = InsightRepository(db)
    row = repo.get(insight_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")
    return row


@router.post("/{insight_id}/dismiss", response_model=InsightRead)
def dismiss_insight(
    insight_id: int,
    body: DismissRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> InsightRead:
    repo = InsightRepository(db)
    row = repo.get(insight_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")
    repo.dismiss(row, reason=body.reason)
    return row


@router.post("/{insight_id}/snooze", response_model=InsightRead)
def snooze_insight(
    insight_id: int,
    body: SnoozeRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> InsightRead:
    repo = InsightRepository(db)
    row = repo.get(insight_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")
    repo.snooze(row, body.until)
    return row


@router.post("/{insight_id}/acted-on", response_model=InsightRead)
def mark_acted_on(
    insight_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> InsightRead:
    repo = InsightRepository(db)
    row = repo.get(insight_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")
    repo.mark_acted_on(row)
    return row


@router.post("/mark-seen", response_model=MarkSeenResponse)
def mark_seen(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> MarkSeenResponse:
    repo = InsightRepository(db)
    count = repo.mark_seen(user_id)
    return MarkSeenResponse(marked=count)


@router.post("/refresh")
def refresh_insights(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    dispatcher = _get_dispatcher(db)
    dispatcher.fire_all(user_id)
    return {"status": "refreshed"}
```

- [ ] **Step 4: Register the router**

In `apps/api/app/api/router.py`, add:

```python
from app.api.insights import router as insights_router
```

And:

```python
api_router.include_router(insights_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_insights_api.py -v`
Expected: All 11 tests PASS

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/api/insights.py apps/api/app/api/router.py apps/api/tests/test_insights_api.py
git commit -m "feat: add /insights API router with all CRUD and lifecycle endpoints"
```

---

## Task 7: CardInsightEngine — Adapt Existing Card Engine

**Files:**
- Create: `apps/api/app/services/card_insight_engine.py`
- Test: `apps/api/tests/test_card_insight_engine.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_card_insight_engine.py`:

```python
import json
from unittest.mock import patch

from app.services.card_insight_engine import CardInsightEngine
from app.services.insight_types import EngineContext, EngineEvent


def _profile_ctx(**overrides):
    from app.models.spending_profile import SpendingProfile
    from datetime import date, datetime

    profile = SpendingProfile(
        id=1,
        user_id=1,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        avg_monthly_spend=3000.0,
        category_breakdown_json=json.dumps({"dining": 500, "travel": 800}),
        top_merchants_json=json.dumps([]),
        computed_at=datetime(2026, 4, 1),
    )
    from app.models.card import Card

    cards = overrides.get("cards", [
        Card(id=1, user_id=1, name="My Card", network="Visa", issuer="Chase", annual_fee=0.0, rewards_config_json="{}"),
    ])
    ctx = EngineContext(spending_profile=profile, cards=cards)
    return ctx


def test_relevant_events():
    engine = CardInsightEngine()
    events = engine.relevant_events()
    assert EngineEvent.TRANSACTIONS_SYNCED in events
    assert EngineEvent.CARD_MUTATED in events


def test_generate_returns_drafts_with_correct_fields():
    engine = CardInsightEngine()
    ctx = _profile_ctx()

    fake_api_cards = [
        {
            "name": "Sapphire Preferred",
            "issuer": "CHASE",
            "network": "Visa",
            "annualFee": 95,
            "universalCashbackPercent": 1,
            "isAnnualFeeWaived": False,
            "discontinued": False,
            "credits": [],
            "offers": [
                {
                    "amount": [{"amount": 60000}],
                    "spend": 4000,
                    "days": 90,
                }
            ],
        }
    ]

    with patch("app.services.card_insight_engine.fetch_card_bonuses", return_value=fake_api_cards):
        drafts = engine.generate(user_id=1, ctx=ctx)

    assert len(drafts) >= 1
    draft = drafts[0]
    assert draft.kind == "next_card"
    assert draft.impact_one_time_cents > 0
    assert draft.effort == "medium"
    assert "summary" in draft.evidence
    assert draft.inputs_hash != ""


def test_generate_with_no_profile_returns_empty():
    engine = CardInsightEngine()
    ctx = EngineContext()
    with patch("app.services.card_insight_engine.fetch_card_bonuses", return_value=[]):
        drafts = engine.generate(user_id=1, ctx=ctx)
    assert drafts == []


def test_generate_portfolio_insights():
    engine = CardInsightEngine()
    from app.models.card import Card

    cards = [
        Card(id=1, user_id=1, name="Expensive Card", network="Visa", issuer="AMEX", annual_fee=550.0, rewards_config_json="{}"),
    ]
    ctx = _profile_ctx(cards=cards)

    fake_api_cards = [
        {
            "name": "Expensive Card",
            "issuer": "AMEX",
            "network": "Visa",
            "annualFee": 550,
            "universalCashbackPercent": 1,
            "isAnnualFeeWaived": False,
            "discontinued": False,
            "credits": [],
            "offers": [],
        },
        {
            "name": "Free Card",
            "issuer": "DISCOVER",
            "network": "Visa",
            "annualFee": 0,
            "universalCashbackPercent": 2,
            "isAnnualFeeWaived": False,
            "discontinued": False,
            "credits": [],
            "offers": [],
        },
    ]

    with patch("app.services.card_insight_engine.fetch_card_bonuses", return_value=fake_api_cards):
        drafts = engine.generate(user_id=1, ctx=ctx)

    portfolio_drafts = [d for d in drafts if d.kind == "portfolio_underperforming"]
    assert len(portfolio_drafts) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_card_insight_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.card_insight_engine'`

- [ ] **Step 3: Write the CardInsightEngine**

Create `apps/api/app/services/card_insight_engine.py`:

```python
from __future__ import annotations

import hashlib
import json
import time
from typing import Dict, List, Literal

import httpx

from app.models.insight import Insight
from app.services.card_recommendation import CardRecommendationService
from app.services.insight_types import (
    EngineContext,
    EngineEvent,
    InsightDraft,
)

DATA_URL = "https://raw.githubusercontent.com/andenacitelli/credit-card-bonuses-api/main/exports/data.json"
CACHE_TTL_SECONDS = 3600

_cache: Dict[str, object] = {"data": None, "fetched_at": 0.0}


def fetch_card_bonuses() -> List[dict]:
    now = time.time()
    if _cache["data"] is not None and now - _cache["fetched_at"] < CACHE_TTL_SECONDS:
        return _cache["data"]
    resp = httpx.get(DATA_URL, timeout=15)
    resp.raise_for_status()
    cards = resp.json()
    _cache["data"] = cards
    _cache["fetched_at"] = now
    return cards


def _hash_inputs(profile_json: str, cards_json: str, kind: str) -> str:
    raw = f"{kind}|{profile_json}|{cards_json}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class CardInsightEngine:
    name = "card"

    def relevant_events(self) -> set[EngineEvent]:
        return {
            EngineEvent.TRANSACTIONS_SYNCED,
            EngineEvent.TRANSACTION_MUTATED,
            EngineEvent.CARD_MUTATED,
            EngineEvent.USER_ONBOARDED,
        }

    def generate(self, user_id: int, ctx: EngineContext) -> list[InsightDraft]:
        if not ctx.spending_profile:
            return []

        profile_dict = {
            "avg_monthly_spend": ctx.spending_profile.avg_monthly_spend,
            "category_breakdown": json.loads(ctx.spending_profile.category_breakdown_json),
            "top_merchants": json.loads(ctx.spending_profile.top_merchants_json),
        }
        user_cards = [
            {
                "name": c.name,
                "issuer": c.issuer or "",
                "network": c.network,
                "annual_fee": c.annual_fee,
            }
            for c in ctx.cards
        ]

        available_cards = fetch_card_bonuses()
        svc = CardRecommendationService()
        drafts: list[InsightDraft] = []

        profile_json = json.dumps(profile_dict, sort_keys=True)
        cards_json = json.dumps(user_cards, sort_keys=True)

        next_cards = svc.recommend_next_card(profile_dict, user_cards, available_cards, max_results=5)
        for rec in next_cards:
            card = rec["card"]
            bonus_val = rec["bonus_value"]
            drafts.append(InsightDraft(
                kind="next_card",
                title=f"Apply for {card.get('name', 'card')}",
                body=rec["explanation"],
                impact_one_time_cents=int(bonus_val * 100),
                impact_annual_cents=0,
                effort="medium",
                evidence={
                    "summary": rec["explanation"],
                    "data_points": [
                        {"label": "Sign-up bonus", "value": f"{bonus_val:,.0f} pts"},
                        {"label": "Score", "value": f"{rec['score']:,.0f}"},
                        {"label": "Months to hit", "value": f"{rec['months_to_hit']:.1f}"},
                    ],
                },
                action={
                    "label": "View card",
                    "kind": "external",
                    "target": card.get("url", ""),
                } if card.get("url") else None,
                related_goal_id=None,
                inputs_hash=_hash_inputs(profile_json, cards_json, f"next_card_{card.get('name', '')}"),
            ))

        portfolio = svc.analyze_portfolio(profile_dict, user_cards, available_cards)
        for analysis in portfolio:
            if analysis["status"] in ("underperforming", "costing_money"):
                card_name = analysis["user_card"].get("name", "Card")
                kind = f"portfolio_{analysis['status']}"
                drafts.append(InsightDraft(
                    kind=kind,
                    title=f"{card_name} is {analysis['status'].replace('_', ' ')}",
                    body=analysis["explanation"],
                    impact_one_time_cents=0,
                    impact_annual_cents=int(abs(analysis["net_value"]) * 100),
                    effort="high",
                    evidence={
                        "summary": analysis["explanation"],
                        "data_points": [
                            {"label": "Annual value", "value": f"${analysis['estimated_annual_value']:,.2f}"},
                            {"label": "Annual fee", "value": f"${analysis['user_card'].get('annual_fee', 0):,.2f}"},
                            {"label": "Net value", "value": f"${analysis['net_value']:,.2f}"},
                        ],
                    },
                    action=None,
                    related_goal_id=None,
                    inputs_hash=_hash_inputs(profile_json, cards_json, f"portfolio_{card_name}"),
                ))

        return drafts

    def detect_resolution(
        self, old_insight: Insight, ctx: EngineContext
    ) -> Literal["acted_on", "expired", "still_active"]:
        return "expired"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_card_insight_engine.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/card_insight_engine.py apps/api/tests/test_card_insight_engine.py
git commit -m "feat: add CardInsightEngine adapter for existing card recommendation service"
```

---

## Task 8: Wire Event Fires in Existing Routes

**Files:**
- Modify: `apps/api/app/api/plaid.py`
- Modify: `apps/api/app/api/transactions.py`
- Modify: `apps/api/app/api/goals.py`
- Modify: `apps/api/app/api/cards.py`

- [ ] **Step 1: Write the tests for event wiring**

Add to `apps/api/tests/test_insights_api.py`:

```python
from unittest.mock import patch


def test_transaction_create_fires_event(client: TestClient, db_session: Session, seed_user):
    from app.models.account import Account

    acct = Account(user_id=seed_user.id, name="Checking", type="checking", balance=1000, currency="USD", dedupe_hash="x")
    # Create the account first
    acct = Account(user_id=seed_user.id, name="Checking", type="checking", balance=1000, currency="USD")
    db_session.add(acct)
    db_session.commit()
    db_session.refresh(acct)

    with patch("app.api.transactions.fire_insights_event") as mock_fire:
        resp = client.post("/transactions", json={
            "account_id": acct.id,
            "occurred_on": "2026-04-01",
            "amount": -50.0,
            "merchant": "Test Store",
            "dedupe_hash": "txn_hash_1",
        })
        assert resp.status_code == 201
        mock_fire.assert_called_once()


def test_goal_create_fires_event(client: TestClient, seed_user):
    with patch("app.api.goals.fire_insights_event") as mock_fire:
        resp = client.post("/goals", json={
            "name": "Emergency Fund",
            "goal_type": "savings",
            "target_amount": 10000,
        })
        assert resp.status_code == 201
        mock_fire.assert_called_once()


def test_card_create_fires_event(client: TestClient, seed_user):
    with patch("app.api.cards.fire_insights_event") as mock_fire:
        resp = client.post("/cards", json={
            "name": "Sapphire",
            "network": "Visa",
        })
        assert resp.status_code == 201
        mock_fire.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_insights_api.py::test_transaction_create_fires_event tests/test_insights_api.py::test_goal_create_fires_event tests/test_insights_api.py::test_card_create_fires_event -v`
Expected: FAIL — `fire_insights_event` not found

- [ ] **Step 3: Add the shared event fire helper**

Add to `apps/api/app/api/insights.py` at the bottom:

```python
from app.services.insight_types import EngineEvent
from app.services.card_insight_engine import CardInsightEngine


def get_default_dispatcher(db: Session) -> InsightDispatcher:
    dispatcher = InsightDispatcher(db)
    dispatcher.register(CardInsightEngine())
    return dispatcher


def fire_insights_event(db: Session, event: EngineEvent, user_id: int) -> None:
    dispatcher = get_default_dispatcher(db)
    dispatcher.fire(event, user_id)
```

Update the `refresh_insights` endpoint to use `get_default_dispatcher`:

```python
@router.post("/refresh")
def refresh_insights(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    dispatcher = get_default_dispatcher(db)
    dispatcher.fire_all(user_id)
    return {"status": "refreshed"}
```

- [ ] **Step 4: Wire events into transactions.py**

In `apps/api/app/api/transactions.py`, add import and fire calls:

```python
from app.api.insights import fire_insights_event
from app.services.insight_types import EngineEvent
```

After `repo.create(user_id, data)` in `create_transaction`, add:

```python
    result = repo.create(user_id, data)
    fire_insights_event(db, EngineEvent.TRANSACTION_MUTATED, user_id)
    return result
```

After `repo.update(txn, data)` in `update_transaction`, add:

```python
    result = repo.update(txn, data)
    fire_insights_event(db, EngineEvent.TRANSACTION_MUTATED, user_id)
    return result
```

- [ ] **Step 5: Wire events into goals.py**

In `apps/api/app/api/goals.py`, add import and fire calls:

```python
from app.api.insights import fire_insights_event
from app.services.insight_types import EngineEvent
```

After `repo.create(user_id, data)` in `create_goal`:

```python
    result = repo.create(user_id, data)
    fire_insights_event(db, EngineEvent.GOAL_MUTATED, user_id)
    return result
```

After `repo.update(goal, data)` in `update_goal`:

```python
    result = repo.update(goal, data)
    fire_insights_event(db, EngineEvent.GOAL_MUTATED, user_id)
    return result
```

- [ ] **Step 6: Wire events into cards.py**

In `apps/api/app/api/cards.py`, add import and fire calls:

```python
from app.api.insights import fire_insights_event
from app.services.insight_types import EngineEvent
```

After `repo.create(user_id, data)` in `create_card`:

```python
    result = repo.create(user_id, data)
    fire_insights_event(db, EngineEvent.CARD_MUTATED, user_id)
    return result
```

After `repo.update(card, data)` in `update_card`:

```python
    result = repo.update(card, data)
    fire_insights_event(db, EngineEvent.CARD_MUTATED, user_id)
    return result
```

After `repo.delete(card)` in `delete_card`:

```python
    repo.delete(card)
    fire_insights_event(db, EngineEvent.CARD_MUTATED, user_id)
```

- [ ] **Step 7: Wire events into plaid.py**

In `apps/api/app/api/plaid.py`, add import and fire after sync:

```python
from app.api.insights import fire_insights_event
from app.services.insight_types import EngineEvent
```

After `sync_transactions(...)` in `sync_item`:

```python
    result = sync_transactions(client, db, plaid_item, user_id)
    fire_insights_event(db, EngineEvent.TRANSACTIONS_SYNCED, user_id)
    return SyncResult(**result)
```

- [ ] **Step 8: Run all tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_insights_api.py -v`
Expected: All tests PASS (including the 3 new event wiring tests)

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/api/insights.py apps/api/app/api/transactions.py apps/api/app/api/goals.py apps/api/app/api/cards.py apps/api/app/api/plaid.py apps/api/tests/test_insights_api.py
git commit -m "feat: wire insight event fires into transaction, goal, card, and plaid routes"
```

---

## Task 9: Frontend Types and API Client

**Files:**
- Modify: `apps/web/src/lib/types.ts`
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1: Add Insight types**

Add to `apps/web/src/lib/types.ts`:

```typescript
export interface Insight {
  id: number;
  engine: string;
  kind: string;
  title: string;
  body: string;
  impact_one_time_cents: number;
  impact_annual_cents: number;
  effort: string;
  evidence_json: string;
  action_json: string | null;
  related_goal_id: number | null;
  status: string;
  snoozed_until: string | null;
  seen_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InsightSummary {
  total_active: number;
  total_annual_impact_cents: number;
  unread_count: number;
  by_engine: Record<string, number>;
}
```

- [ ] **Step 2: Add API functions**

Add to `apps/web/src/lib/api.ts`:

```typescript
import type { Insight, InsightSummary } from "./types";
```

Then add:

```typescript
// Insights
export const getInsights = (params?: { engine?: string; effort?: string; limit?: number; offset?: number }) => {
  const search = new URLSearchParams();
  if (params?.engine) search.set("engine", params.engine);
  if (params?.effort) search.set("effort", params.effort);
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  const qs = search.toString();
  return request<Insight[]>(`/insights${qs ? `?${qs}` : ""}`);
};
export const getInsightsSummary = () => request<InsightSummary>("/insights/summary");
export const getInsight = (id: number) => request<Insight>(`/insights/${id}`);
export const dismissInsight = (id: number, reason?: string) =>
  request<Insight>(`/insights/${id}/dismiss`, { method: "POST", body: JSON.stringify({ reason }) });
export const snoozeInsight = (id: number, until: string) =>
  request<Insight>(`/insights/${id}/snooze`, { method: "POST", body: JSON.stringify({ until }) });
export const markInsightActedOn = (id: number) =>
  request<Insight>(`/insights/${id}/acted-on`, { method: "POST" });
export const markInsightsSeen = () =>
  request<{ marked: number }>("/insights/mark-seen", { method: "POST" });
export const getInsightsHistory = () => request<Insight[]>("/insights/history");
export const refreshInsights = () =>
  request<{ status: string }>("/insights/refresh", { method: "POST" });
```

- [ ] **Step 3: Verify build**

Run: `cd apps/web && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/types.ts apps/web/src/lib/api.ts
git commit -m "feat(web): add Insight types and API client functions"
```

---

## Task 10: Insights Page (Frontend)

**Files:**
- Create: `apps/web/src/app/(app)/insights/page.tsx`

**Important:** Read `node_modules/next/dist/docs/` guides before writing any Next.js code, per `AGENTS.md`.

- [ ] **Step 1: Read Next.js docs for current API patterns**

Run: `ls apps/web/node_modules/next/dist/docs/` and read relevant guides for App Router patterns, especially around `"use client"` and route params.

- [ ] **Step 2: Create the insights page**

Create `apps/web/src/app/(app)/insights/page.tsx`:

```tsx
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getInsights,
  getInsightsSummary,
  dismissInsight,
  snoozeInsight,
  markInsightActedOn,
  markInsightsSeen,
} from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import type { Insight } from "@/lib/types";
import {
  Lightbulb,
  CreditCard,
  PiggyBank,
  TrendingUp,
  Target,
  X,
  Clock,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Filter,
  Zap,
} from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";

const ENGINE_TABS = [
  { key: "", label: "All", icon: Lightbulb },
  { key: "save", label: "Save", icon: PiggyBank },
  { key: "earn", label: "Earn", icon: TrendingUp },
  { key: "goal_forecast", label: "Goals", icon: Target },
  { key: "card", label: "Cards", icon: CreditCard },
] as const;

const EFFORT_LABELS: Record<string, string> = {
  low: "Easy",
  medium: "Moderate",
  high: "Involved",
};

function formatImpact(insight: Insight): string {
  if (insight.impact_annual_cents > 0) {
    return `${formatCurrency(insight.impact_annual_cents / 100)}/yr`;
  }
  return formatCurrency(insight.impact_one_time_cents / 100);
}

function EffortBadge({ effort }: { effort: string }) {
  const colors: Record<string, string> = {
    low: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    medium: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    high: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${colors[effort] || ""}`}>
      <Zap className="w-3 h-3" />
      {EFFORT_LABELS[effort] || effort}
    </span>
  );
}

function InsightRow({ insight, onAction }: { insight: Insight; onAction: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const queryClient = useQueryClient();

  const dismissMutation = useMutation({
    mutationFn: () => dismissInsight(insight.id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["insights"] }); onAction(); },
  });
  const snoozeMutation = useMutation({
    mutationFn: () => {
      const until = new Date();
      until.setDate(until.getDate() + 30);
      return snoozeInsight(insight.id, until.toISOString().split("T")[0]);
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["insights"] }); onAction(); },
  });
  const actedOnMutation = useMutation({
    mutationFn: () => markInsightActedOn(insight.id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["insights"] }); onAction(); },
  });

  let evidence: { summary?: string; data_points?: { label: string; value: string }[] } = {};
  try {
    evidence = JSON.parse(insight.evidence_json);
  } catch {}

  let action: { label?: string; kind?: string; target?: string } | null = null;
  try {
    if (insight.action_json) action = JSON.parse(insight.action_json);
  } catch {}

  return (
    <div className="border border-border rounded-lg p-4 transition-colors hover:bg-accent/30">
      <div className="flex items-start justify-between gap-3">
        <button onClick={() => setExpanded(!expanded)} className="flex-1 text-left">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-card-foreground">{insight.title}</h3>
            {!insight.seen_at && (
              <span className="inline-block w-2 h-2 rounded-full bg-primary" />
            )}
          </div>
          <p className="text-sm text-muted-foreground line-clamp-1">{insight.body}</p>
        </button>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-sm font-semibold text-primary whitespace-nowrap">
            +{formatImpact(insight)}
          </span>
          <EffortBadge effort={insight.effort} />
          <button onClick={() => setExpanded(!expanded)} className="text-muted-foreground">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-border space-y-3">
          {evidence.summary && (
            <p className="text-sm text-muted-foreground">{evidence.summary}</p>
          )}
          {evidence.data_points && evidence.data_points.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {evidence.data_points.map((dp, i) => (
                <div key={i} className="bg-muted/50 rounded-md px-3 py-2">
                  <div className="text-xs text-muted-foreground">{dp.label}</div>
                  <div className="text-sm font-medium">{dp.value}</div>
                </div>
              ))}
            </div>
          )}
          <div className="flex items-center gap-2 pt-2">
            {action?.target && (
              <a
                href={action.target}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline"
              >
                {action.label || "Learn more"} →
              </a>
            )}
            <div className="ml-auto flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={() => actedOnMutation.mutate()} disabled={actedOnMutation.isPending}>
                <CheckCircle className="w-4 h-4 mr-1" /> Done
              </Button>
              <Button variant="ghost" size="sm" onClick={() => snoozeMutation.mutate()} disabled={snoozeMutation.isPending}>
                <Clock className="w-4 h-4 mr-1" /> Snooze
              </Button>
              <Button variant="ghost" size="sm" onClick={() => dismissMutation.mutate()} disabled={dismissMutation.isPending}>
                <X className="w-4 h-4 mr-1" /> Dismiss
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function InsightsPage() {
  const [engine, setEngine] = useState("");
  const queryClient = useQueryClient();

  const { data: insights, isLoading } = useQuery({
    queryKey: ["insights", "list", engine],
    queryFn: () => getInsights({ engine: engine || undefined }),
  });

  const { data: summary } = useQuery({
    queryKey: ["insights", "summary"],
    queryFn: getInsightsSummary,
  });

  const seenMutation = useMutation({
    mutationFn: markInsightsSeen,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["insights", "summary"] }),
  });

  useEffect(() => {
    seenMutation.mutate();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold font-heading">Insights</h1>
        {summary && summary.total_active > 0 && (
          <p className="text-muted-foreground mt-1">
            Potential: +{formatCurrency(summary.total_annual_impact_cents / 100)}/yr across {summary.total_active} ideas
          </p>
        )}
      </div>

      <div className="flex gap-1 border-b border-border">
        {ENGINE_TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setEngine(key)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              engine === key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-card-foreground"
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
            {key && summary?.by_engine[key] ? (
              <span className="ml-1 text-xs bg-muted rounded-full px-1.5">
                {summary.by_engine[key]}
              </span>
            ) : null}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 rounded-lg" />
          ))}
        </div>
      ) : insights && insights.length > 0 ? (
        <div className="space-y-3">
          {insights.map((insight) => (
            <InsightRow
              key={insight.id}
              insight={insight}
              onAction={() => queryClient.invalidateQueries({ queryKey: ["insights"] })}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          <Lightbulb className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="font-medium">No insights yet</p>
          <p className="text-sm mt-1">Insights will appear as we analyze your financial data</p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd apps/web && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/\(app\)/insights/page.tsx
git commit -m "feat(web): add insights page with engine tabs, detail panels, and lifecycle actions"
```

---

## Task 11: Update Sidebar + Redirect Recommendations

**Files:**
- Modify: `apps/web/src/components/sidebar.tsx`
- Modify: `apps/web/src/app/(app)/recommendations/page.tsx`

- [ ] **Step 1: Update sidebar nav item**

In `apps/web/src/components/sidebar.tsx`, change the Recommendations nav entry:

Replace:
```typescript
  { href: "/recommendations", label: "Recommendations", icon: Lightbulb },
```

With:
```typescript
  { href: "/insights", label: "Insights", icon: Lightbulb },
```

- [ ] **Step 2: Add unread badge to sidebar**

Add import at the top of the sidebar file:

```typescript
import { useQuery } from "@tanstack/react-query";
```

is already imported. Add the API import:

```typescript
import { getMe, getInsightsSummary } from "@/lib/api";
```

Inside the `Sidebar` component, add query for summary:

```typescript
const { data: insightSummary } = useQuery({
  queryKey: ["insights", "summary"],
  queryFn: getInsightsSummary,
  enabled: !!user,
});
```

In the nav rendering, after the label span, conditionally show the badge:

```tsx
{!collapsed && <span className="truncate">{label}</span>}
{!collapsed && label === "Insights" && insightSummary?.unread_count ? (
  <span className="ml-auto text-xs bg-primary text-primary-foreground rounded-full px-1.5 py-0.5 min-w-[1.25rem] text-center">
    {insightSummary.unread_count}
  </span>
) : null}
```

- [ ] **Step 3: Redirect recommendations page**

Replace `apps/web/src/app/(app)/recommendations/page.tsx` with:

```tsx
import { redirect } from "next/navigation";

export default function RecommendationsRedirect() {
  redirect("/insights?engine=card");
}
```

- [ ] **Step 4: Start dev server and verify**

Run: `cd apps/web && npm run dev`

Verify:
- Sidebar shows "Insights" instead of "Recommendations"
- Navigating to `/insights` shows the page with engine tabs
- Navigating to `/recommendations` redirects to `/insights?engine=card`
- Unread badge shows when there are unseen insights

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/sidebar.tsx apps/web/src/app/\(app\)/recommendations/page.tsx
git commit -m "feat(web): rename Recommendations to Insights in sidebar, add unread badge, redirect old route"
```

---

## Task 12: Dashboard Insights Widget

**Files:**
- Create: `apps/web/src/components/insights-widget.tsx`

- [ ] **Step 1: Identify where dashboard widgets live**

Run: `ls apps/web/src/app/\(app\)/dashboard/`

Read the dashboard page to understand the widget layout pattern.

- [ ] **Step 2: Create the insights widget component**

Create `apps/web/src/components/insights-widget.tsx`:

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { getInsights, getInsightsSummary } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { Lightbulb, ArrowRight, Zap } from "lucide-react";
import Link from "next/link";
import type { Insight } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

function formatImpact(insight: Insight): string {
  if (insight.impact_annual_cents > 0) {
    return `${formatCurrency(insight.impact_annual_cents / 100)}/yr`;
  }
  return formatCurrency(insight.impact_one_time_cents / 100);
}

export function InsightsWidget() {
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["insights", "summary"],
    queryFn: getInsightsSummary,
  });

  const { data: insights, isLoading: insightsLoading } = useQuery({
    queryKey: ["insights", "list", "widget"],
    queryFn: () => getInsights({ limit: 3 }),
  });

  const isLoading = summaryLoading || insightsLoading;

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 space-y-3">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-16" />
      </div>
    );
  }

  if (!insights || insights.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Lightbulb className="w-5 h-5 text-primary" />
          <h3 className="font-semibold text-card-foreground">Insights</h3>
        </div>
        <Link
          href="/insights"
          className="text-sm text-primary hover:underline flex items-center gap-1"
        >
          View all <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {summary && summary.total_active > 0 && (
        <p className="text-sm text-muted-foreground mb-3">
          +{formatCurrency(summary.total_annual_impact_cents / 100)}/yr potential across {summary.total_active} ideas
        </p>
      )}

      <div className="space-y-2">
        {insights.map((insight) => (
          <Link
            key={insight.id}
            href="/insights"
            className="flex items-center justify-between gap-3 rounded-lg p-2.5 hover:bg-accent/50 transition-colors"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-card-foreground truncate">{insight.title}</p>
              <p className="text-xs text-muted-foreground truncate">{insight.body}</p>
            </div>
            <span className="text-sm font-semibold text-primary whitespace-nowrap flex-shrink-0">
              +{formatImpact(insight)}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add widget to dashboard page**

Read the dashboard page, find the widget section, and add:

```tsx
import { InsightsWidget } from "@/components/insights-widget";
```

Place `<InsightsWidget />` in the widget grid, replacing or alongside the existing recommendations widget.

- [ ] **Step 4: Verify build and visual check**

Run: `cd apps/web && npx tsc --noEmit`
Then check in browser that the widget renders on the dashboard.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/insights-widget.tsx apps/web/src/app/\(app\)/dashboard/page.tsx
git commit -m "feat(web): add insights widget to dashboard"
```

---

## Task 13: Run Full Test Suite + Update Changelog

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Run full backend test suite**

Run: `cd apps/api && python -m pytest -v`
Expected: All tests PASS with 0 failures

- [ ] **Step 2: Run frontend type check and lint**

Run: `cd apps/web && npx tsc --noEmit && npm run lint`
Expected: No errors

- [ ] **Step 3: Update changelog**

Add under `[Unreleased]` in `CHANGELOG.md`:

```markdown
### Added
- Unified insights substrate with event-driven recommendation engine
- `Insight` model with lifecycle management (dismiss, snooze, acted-on, expire)
- `InsightDispatcher` with engine isolation, diff logic, and dismiss-sticky resurfacing
- `CardInsightEngine` adapting existing card recommendation service to new substrate
- `/insights` API endpoints (list, summary, detail, dismiss, snooze, acted-on, mark-seen, refresh, history)
- Event wiring: Plaid sync, transaction/goal/card CRUD fire insight recomputation
- Insights page with engine tabs, inline detail panels, and lifecycle actions
- Dashboard insights widget showing top recommendations
- Sidebar unread count badge for new insights

### Changed
- Renamed "Recommendations" to "Insights" in sidebar navigation
- `/recommendations` now redirects to `/insights?engine=card`
```

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: update changelog with insights substrate feature"
```
