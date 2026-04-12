# Card Recommendation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend recommendation engine that analyzes user spending to suggest optimal next credit cards and flag underperforming cards in the portfolio.

**Architecture:** Three-layer backend: SpendingProfileService (aggregation) -> CardRecommendationService (pure scoring logic) -> RecommendationSnapshotService (caching). New DB models for spending profiles and recommendation snapshots. New `/recommendations` API router. Frontend: new `/recommendations` page + dashboard widget.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Alembic, Pydantic, Next.js/React, TanStack Query

---

## File Structure

### Backend (new files)
- `apps/api/app/models/spending_profile.py` — SpendingProfile ORM model
- `apps/api/app/models/recommendation_snapshot.py` — RecommendationSnapshot ORM model
- `apps/api/app/schemas/recommendation.py` — Pydantic schemas for all recommendation types
- `apps/api/app/repositories/spending_profile.py` — SpendingProfile DB queries
- `apps/api/app/repositories/recommendation_snapshot.py` — RecommendationSnapshot DB queries
- `apps/api/app/services/spending_profile.py` — Transaction aggregation logic
- `apps/api/app/services/card_recommendation.py` — Pure scoring/ranking engine
- `apps/api/app/services/recommendation_snapshot.py` — Caching orchestrator
- `apps/api/app/api/recommendations.py` — API router

### Backend (modified files)
- `apps/api/app/models/__init__.py` — Import new models
- `apps/api/app/api/router.py` — Register recommendations router
- `apps/api/app/models/card.py` — Add optional `issuer` column

### Frontend (new files)
- `apps/web/src/app/(app)/recommendations/page.tsx` — Recommendations page

### Frontend (modified files)
- `apps/web/src/lib/types.ts` — Add recommendation types
- `apps/web/src/lib/api.ts` — Add recommendation API functions
- `apps/web/src/components/sidebar.tsx` — Add recommendations nav item
- `apps/web/src/app/(app)/dashboard/page.tsx` — Add recommendation widget

### Tests
- `apps/api/tests/test_spending_profile_service.py`
- `apps/api/tests/test_card_recommendation_service.py`
- `apps/api/tests/test_recommendation_snapshot_service.py`
- `apps/api/tests/test_recommendations_api.py`

### Migration
- `apps/api/alembic/versions/` — New migration for spending_profiles + recommendation_snapshots tables + card.issuer column

---

## Task 1: SpendingProfile and RecommendationSnapshot Models + Migration

**Files:**
- Create: `apps/api/app/models/spending_profile.py`
- Create: `apps/api/app/models/recommendation_snapshot.py`
- Modify: `apps/api/app/models/__init__.py`
- Modify: `apps/api/app/models/card.py`
- Test: `apps/api/tests/test_models.py`

- [ ] **Step 1: Write test for new models**

Add to `apps/api/tests/test_models.py`:

```python
class TestSpendingProfileModel:
    def test_create_spending_profile(self, db_session: Session, seed_user: User):
        from app.models.spending_profile import SpendingProfile
        profile = SpendingProfile(
            user_id=seed_user.id,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            avg_monthly_spend=2500.0,
            category_breakdown_json='{"dining": 450, "travel": 800}',
            top_merchants_json='[{"name": "Amazon", "monthly_avg": 200}]',
        )
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(profile)
        assert profile.id is not None
        assert profile.avg_monthly_spend == 2500.0
        assert profile.computed_at is not None


class TestRecommendationSnapshotModel:
    def test_create_snapshot(self, db_session: Session, seed_user: User):
        from app.models.recommendation_snapshot import RecommendationSnapshot
        snap = RecommendationSnapshot(
            user_id=seed_user.id,
            type="next_card",
            results_json='[{"card": "Chase Sapphire"}]',
            inputs_hash="abc123",
        )
        db_session.add(snap)
        db_session.commit()
        db_session.refresh(snap)
        assert snap.id is not None
        assert snap.type == "next_card"
        assert snap.computed_at is not None


class TestCardIssuerField:
    def test_card_with_issuer(self, db_session: Session, seed_user: User):
        from app.models.card import Card
        card = Card(
            user_id=seed_user.id,
            name="Sapphire Preferred",
            network="visa",
            issuer="CHASE",
            annual_fee=95.0,
        )
        db_session.add(card)
        db_session.commit()
        db_session.refresh(card)
        assert card.issuer == "CHASE"

    def test_card_issuer_nullable(self, db_session: Session, seed_user: User):
        from app.models.card import Card
        card = Card(user_id=seed_user.id, name="Some Card", network="visa")
        db_session.add(card)
        db_session.commit()
        db_session.refresh(card)
        assert card.issuer is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_models.py::TestSpendingProfileModel -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.spending_profile'`

- [ ] **Step 3: Create SpendingProfile model**

Create `apps/api/app/models/spending_profile.py`:

```python
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SpendingProfile(Base):
    __tablename__ = "spending_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_spending_profiles_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    avg_monthly_spend: Mapped[float] = mapped_column(Float, default=0.0)
    category_breakdown_json: Mapped[str] = mapped_column(Text, default="{}")
    top_merchants_json: Mapped[str] = mapped_column(Text, default="[]")
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 4: Create RecommendationSnapshot model**

Create `apps/api/app/models/recommendation_snapshot.py`:

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RecommendationSnapshot(Base):
    __tablename__ = "recommendation_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "type", name="uq_recommendation_snapshots_user_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    results_json: Mapped[str] = mapped_column(Text, default="[]")
    inputs_hash: Mapped[str] = mapped_column(String(64))
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 5: Add issuer to Card model**

Edit `apps/api/app/models/card.py`, add after the `network` field:

```python
    issuer: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
```

Add `from typing import Optional` to imports.

- [ ] **Step 6: Update `__init__.py` to import new models**

Edit `apps/api/app/models/__init__.py` to add:

```python
from app.models.spending_profile import SpendingProfile  # noqa: F401
from app.models.recommendation_snapshot import RecommendationSnapshot  # noqa: F401
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_models.py::TestSpendingProfileModel tests/test_models.py::TestRecommendationSnapshotModel tests/test_models.py::TestCardIssuerField -v`
Expected: PASS

- [ ] **Step 8: Generate Alembic migration**

Run: `cd apps/api && alembic revision --autogenerate -m "add spending_profiles, recommendation_snapshots, card issuer"`
Verify the generated migration contains: create_table for `spending_profiles`, create_table for `recommendation_snapshots`, add_column `issuer` to `cards`.

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/models/spending_profile.py apps/api/app/models/recommendation_snapshot.py apps/api/app/models/__init__.py apps/api/app/models/card.py apps/api/alembic/versions/ apps/api/tests/test_models.py
git commit -m "feat: add spending_profiles, recommendation_snapshots models and card issuer"
```

---

## Task 2: Pydantic Schemas for Recommendations

**Files:**
- Create: `apps/api/app/schemas/recommendation.py`
- Modify: `apps/api/app/schemas/card.py`

- [ ] **Step 1: Create recommendation schemas**

Create `apps/api/app/schemas/recommendation.py`:

```python
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class CategorySpend(BaseModel):
    category: str
    monthly_avg: float


class TopMerchant(BaseModel):
    name: str
    monthly_avg: float


class SpendingProfileRead(BaseModel):
    user_id: int
    period_start: date
    period_end: date
    avg_monthly_spend: float
    categories: list[CategorySpend]
    top_merchants: list[TopMerchant]
    computed_at: datetime


class BonusInfo(BaseModel):
    amount: int
    min_spend: float
    days: int
    months_to_hit: float
    achievable: bool


class NextCardRecommendation(BaseModel):
    card_id: str
    name: str
    issuer: str
    network: str
    annual_fee: float
    is_annual_fee_waived: bool
    universal_cashback_percent: float
    currency: str
    url: str
    image_url: str
    bonus: Optional[BonusInfo]
    score: float
    explanation: str


class NextCardResponse(BaseModel):
    recommendations: list[NextCardRecommendation]
    spending_profile: SpendingProfileRead


class CardAnalysis(BaseModel):
    card_name: str
    card_network: str
    annual_fee: float
    estimated_annual_value: float
    net_value: float
    status: str  # "good", "underperforming", "costing_money"
    explanation: str
    alternatives: list[AlternativeCard]


class AlternativeCard(BaseModel):
    card_id: str
    name: str
    issuer: str
    annual_fee: float
    estimated_annual_value: float
    net_value: float
    url: str


class PortfolioResponse(BaseModel):
    cards: list[CardAnalysis]
    total_annual_fees: float
    total_estimated_value: float
    spending_profile: SpendingProfileRead
```

Note: `CardAnalysis` references `AlternativeCard` which is defined after it. Use `from __future__ import annotations` (already at top) to handle forward reference.

- [ ] **Step 2: Update card schema with optional issuer**

Edit `apps/api/app/schemas/card.py` — add `issuer: Optional[str] = None` to `CardCreate`, `CardUpdate`, and `CardRead`.

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/schemas/recommendation.py apps/api/app/schemas/card.py
git commit -m "feat: add Pydantic schemas for recommendations and card issuer"
```

---

## Task 3: SpendingProfile Repository

**Files:**
- Create: `apps/api/app/repositories/spending_profile.py`

- [ ] **Step 1: Create the repository**

Create `apps/api/app/repositories/spending_profile.py`:

```python
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.spending_profile import SpendingProfile


class SpendingProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user(self, user_id: int) -> SpendingProfile | None:
        stmt = select(SpendingProfile).where(SpendingProfile.user_id == user_id)
        return self.db.scalars(stmt).first()

    def upsert(
        self,
        user_id: int,
        period_start: date,
        period_end: date,
        avg_monthly_spend: float,
        category_breakdown_json: str,
        top_merchants_json: str,
    ) -> SpendingProfile:
        existing = self.get_by_user(user_id)
        if existing:
            existing.period_start = period_start
            existing.period_end = period_end
            existing.avg_monthly_spend = avg_monthly_spend
            existing.category_breakdown_json = category_breakdown_json
            existing.top_merchants_json = top_merchants_json
            from datetime import datetime, timezone
            existing.computed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        profile = SpendingProfile(
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
            avg_monthly_spend=avg_monthly_spend,
            category_breakdown_json=category_breakdown_json,
            top_merchants_json=top_merchants_json,
        )
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/repositories/spending_profile.py
git commit -m "feat: add SpendingProfile repository with upsert"
```

---

## Task 4: RecommendationSnapshot Repository

**Files:**
- Create: `apps/api/app/repositories/recommendation_snapshot.py`

- [ ] **Step 1: Create the repository**

Create `apps/api/app/repositories/recommendation_snapshot.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recommendation_snapshot import RecommendationSnapshot


class RecommendationSnapshotRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int, rec_type: str) -> RecommendationSnapshot | None:
        stmt = select(RecommendationSnapshot).where(
            RecommendationSnapshot.user_id == user_id,
            RecommendationSnapshot.type == rec_type,
        )
        return self.db.scalars(stmt).first()

    def upsert(
        self,
        user_id: int,
        rec_type: str,
        results_json: str,
        inputs_hash: str,
    ) -> RecommendationSnapshot:
        existing = self.get(user_id, rec_type)
        if existing:
            existing.results_json = results_json
            existing.inputs_hash = inputs_hash
            existing.computed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        snap = RecommendationSnapshot(
            user_id=user_id,
            type=rec_type,
            results_json=results_json,
            inputs_hash=inputs_hash,
        )
        self.db.add(snap)
        self.db.commit()
        self.db.refresh(snap)
        return snap
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/repositories/recommendation_snapshot.py
git commit -m "feat: add RecommendationSnapshot repository with upsert"
```

---

## Task 5: SpendingProfileService

**Files:**
- Create: `apps/api/app/services/spending_profile.py`
- Create: `apps/api/tests/test_spending_profile_service.py`

- [ ] **Step 1: Write failing tests**

Create `apps/api/tests/test_spending_profile_service.py`:

```python
from datetime import date

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User


class TestSpendingProfileService:
    def _seed_transactions(self, db_session: Session, user: User) -> None:
        account = Account(
            user_id=user.id, name="Checking", type="checking", balance=5000.0
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)

        transactions = [
            # January — dining
            Transaction(
                user_id=user.id, account_id=account.id, occurred_on=date(2026, 1, 5),
                amount=-50.0, merchant="Chipotle", normalized_merchant="chipotle",
                category="food and drink", is_income=False, dedupe_hash="h1",
            ),
            Transaction(
                user_id=user.id, account_id=account.id, occurred_on=date(2026, 1, 15),
                amount=-80.0, merchant="Sushi Place", normalized_merchant="sushi place",
                category="food and drink", is_income=False, dedupe_hash="h2",
            ),
            # January — travel
            Transaction(
                user_id=user.id, account_id=account.id, occurred_on=date(2026, 1, 20),
                amount=-300.0, merchant="Delta Airlines", normalized_merchant="delta airlines",
                category="travel", is_income=False, dedupe_hash="h3",
            ),
            # February — dining
            Transaction(
                user_id=user.id, account_id=account.id, occurred_on=date(2026, 2, 10),
                amount=-60.0, merchant="Chipotle", normalized_merchant="chipotle",
                category="food and drink", is_income=False, dedupe_hash="h4",
            ),
            # February — groceries
            Transaction(
                user_id=user.id, account_id=account.id, occurred_on=date(2026, 2, 12),
                amount=-200.0, merchant="Whole Foods", normalized_merchant="whole foods",
                category="groceries", is_income=False, dedupe_hash="h5",
            ),
            # Income (should be excluded from spend)
            Transaction(
                user_id=user.id, account_id=account.id, occurred_on=date(2026, 1, 1),
                amount=5000.0, merchant="Employer", normalized_merchant="employer",
                category="income", is_income=True, dedupe_hash="h6",
            ),
        ]
        db_session.add_all(transactions)
        db_session.commit()

    def test_compute_profile(self, db_session: Session, seed_user: User):
        self._seed_transactions(db_session, seed_user)
        from app.services.spending_profile import SpendingProfileService

        service = SpendingProfileService(db_session)
        profile = service.compute_profile(seed_user.id, lookback_months=6)

        assert profile.avg_monthly_spend > 0
        assert profile.period_end >= date(2026, 2, 1)

        import json
        categories = json.loads(profile.category_breakdown_json)
        assert "food and drink" in categories
        assert "travel" in categories

        merchants = json.loads(profile.top_merchants_json)
        merchant_names = [m["name"] for m in merchants]
        assert "chipotle" in merchant_names

    def test_compute_profile_excludes_income(self, db_session: Session, seed_user: User):
        self._seed_transactions(db_session, seed_user)
        from app.services.spending_profile import SpendingProfileService

        service = SpendingProfileService(db_session)
        profile = service.compute_profile(seed_user.id, lookback_months=6)

        # Total expenses: 50 + 80 + 300 + 60 + 200 = 690 over 2 months = 345/mo
        assert profile.avg_monthly_spend < 1000  # should not include 5000 income

    def test_compute_profile_no_transactions(self, db_session: Session, seed_user: User):
        from app.services.spending_profile import SpendingProfileService

        service = SpendingProfileService(db_session)
        profile = service.compute_profile(seed_user.id, lookback_months=6)

        assert profile.avg_monthly_spend == 0.0

    def test_get_or_refresh_caches(self, db_session: Session, seed_user: User):
        self._seed_transactions(db_session, seed_user)
        from app.services.spending_profile import SpendingProfileService

        service = SpendingProfileService(db_session)
        profile1 = service.get_or_refresh(seed_user.id)
        computed_at1 = profile1.computed_at

        # Calling again without new transactions should return cached
        profile2 = service.get_or_refresh(seed_user.id)
        assert profile2.computed_at == computed_at1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_spending_profile_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.spending_profile'`

- [ ] **Step 3: Implement SpendingProfileService**

Create `apps/api/app/services/spending_profile.py`:

```python
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timezone
from math import ceil

from dateutil.relativedelta import relativedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.repositories.spending_profile import SpendingProfileRepository


class SpendingProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SpendingProfileRepository(db)

    def compute_profile(self, user_id: int, lookback_months: int = 6):
        today = date.today()
        period_start = today - relativedelta(months=lookback_months)
        period_end = today

        stmt = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.is_income == False,  # noqa: E712
                Transaction.occurred_on >= period_start,
                Transaction.occurred_on <= period_end,
            )
            .order_by(Transaction.occurred_on)
        )
        expenses = list(self.db.scalars(stmt).all())

        if not expenses:
            return self.repo.upsert(
                user_id=user_id,
                period_start=period_start,
                period_end=period_end,
                avg_monthly_spend=0.0,
                category_breakdown_json="{}",
                top_merchants_json="[]",
            )

        # Calculate monthly averages
        total_spend = sum(abs(t.amount) for t in expenses)
        first_txn = expenses[0].occurred_on
        last_txn = expenses[-1].occurred_on
        months_span = max(
            1,
            (last_txn.year - first_txn.year) * 12 + (last_txn.month - first_txn.month) + 1,
        )
        avg_monthly_spend = round(total_spend / months_span, 2)

        # Category breakdown (monthly averages)
        category_totals: dict[str, float] = defaultdict(float)
        for t in expenses:
            cat = t.category or "uncategorized"
            category_totals[cat] += abs(t.amount)
        category_breakdown = {
            cat: round(total / months_span, 2)
            for cat, total in sorted(category_totals.items(), key=lambda x: -x[1])
        }

        # Top merchants (monthly averages)
        merchant_totals: dict[str, float] = defaultdict(float)
        for t in expenses:
            key = t.normalized_merchant or t.merchant.lower().strip()
            merchant_totals[key] += abs(t.amount)
        top_merchants = [
            {"name": name, "monthly_avg": round(total / months_span, 2)}
            for name, total in sorted(merchant_totals.items(), key=lambda x: -x[1])[:10]
        ]

        return self.repo.upsert(
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
            avg_monthly_spend=avg_monthly_spend,
            category_breakdown_json=json.dumps(category_breakdown),
            top_merchants_json=json.dumps(top_merchants),
        )

    def get_or_refresh(self, user_id: int, lookback_months: int = 6):
        existing = self.repo.get_by_user(user_id)
        if existing:
            # Check if there are newer transactions since last computation
            stmt = (
                select(func.max(Transaction.created_at))
                .where(Transaction.user_id == user_id)
            )
            latest_txn_at = self.db.scalars(stmt).first()
            if latest_txn_at and existing.computed_at >= latest_txn_at:
                return existing
        return self.compute_profile(user_id, lookback_months)
```

- [ ] **Step 4: Add python-dateutil dependency if not present**

Run: `cd apps/api && pip install python-dateutil` (check pyproject.toml first — may already be transitive via another dep)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_spending_profile_service.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/spending_profile.py apps/api/tests/test_spending_profile_service.py
git commit -m "feat: add SpendingProfileService with transaction aggregation"
```

---

## Task 6: CardRecommendationService — Next Card Logic

**Files:**
- Create: `apps/api/app/services/card_recommendation.py`
- Create: `apps/api/tests/test_card_recommendation_service.py`

- [ ] **Step 1: Write failing tests for next card recommendations**

Create `apps/api/tests/test_card_recommendation_service.py`:

```python
from __future__ import annotations

import json
from datetime import date

import pytest


# Minimal card data matching the free API schema
SAMPLE_CARDS = [
    {
        "cardId": "card-sapphire",
        "name": "Sapphire Preferred",
        "issuer": "CHASE",
        "network": "VISA",
        "currency": "CHASE",
        "isBusiness": False,
        "annualFee": 95,
        "isAnnualFeeWaived": False,
        "universalCashbackPercent": 1,
        "url": "https://example.com/sapphire",
        "imageUrl": "/images/sapphire.png",
        "credits": [{"description": "Hotel Credit", "value": 50, "weight": 0.9}],
        "offers": [
            {"spend": 5000, "amount": [{"amount": 75000}], "days": 90, "credits": []}
        ],
        "discontinued": False,
    },
    {
        "cardId": "card-freedom",
        "name": "Freedom Unlimited",
        "issuer": "CHASE",
        "network": "VISA",
        "currency": "CHASE",
        "isBusiness": False,
        "annualFee": 0,
        "isAnnualFeeWaived": False,
        "universalCashbackPercent": 1.5,
        "url": "https://example.com/freedom",
        "imageUrl": "/images/freedom.png",
        "credits": [],
        "offers": [
            {"spend": 500, "amount": [{"amount": 25000}], "days": 90, "credits": []}
        ],
        "discontinued": False,
    },
    {
        "cardId": "card-platinum",
        "name": "Platinum Card",
        "issuer": "AMERICAN_EXPRESS",
        "network": "AMERICAN_EXPRESS",
        "currency": "AMEX_MR",
        "isBusiness": False,
        "annualFee": 695,
        "isAnnualFeeWaived": False,
        "universalCashbackPercent": 1,
        "url": "https://example.com/platinum",
        "imageUrl": "/images/platinum.png",
        "credits": [
            {"description": "Airline Credit", "value": 200, "weight": 0.9},
            {"description": "Hotel Credit", "value": 200, "weight": 0.8},
        ],
        "offers": [
            {"spend": 8000, "amount": [{"amount": 150000}], "days": 180, "credits": []}
        ],
        "discontinued": False,
    },
]


def _make_profile(avg_monthly_spend: float) -> dict:
    return {
        "avg_monthly_spend": avg_monthly_spend,
        "category_breakdown": {"food and drink": 450, "travel": 300},
        "top_merchants": [{"name": "chipotle", "monthly_avg": 100}],
    }


class TestRecommendNextCard:
    def test_ranks_by_achievable_bonus_value(self):
        from app.services.card_recommendation import CardRecommendationService

        service = CardRecommendationService()
        profile = _make_profile(avg_monthly_spend=2000.0)
        user_cards: list[dict] = []

        results = service.recommend_next_card(profile, user_cards, SAMPLE_CARDS)

        assert len(results) > 0
        # Freedom has $500 min spend — very achievable at $2k/mo
        # Sapphire has $5k min spend — achievable in ~2.5 months within 90 days
        # Platinum has $8k min spend — achievable in 4 months within 180 days
        # All achievable, but Platinum bonus (150k) > Sapphire (75k) > Freedom (25k)
        assert results[0]["card_id"] == "card-platinum"

    def test_filters_unachievable_bonuses(self):
        from app.services.card_recommendation import CardRecommendationService

        service = CardRecommendationService()
        profile = _make_profile(avg_monthly_spend=500.0)
        user_cards: list[dict] = []

        results = service.recommend_next_card(profile, user_cards, SAMPLE_CARDS)

        # At $500/mo: Freedom ($500 in 90 days) = achievable
        # Sapphire ($5k in 90 days) = need $1667/mo, not achievable
        # Platinum ($8k in 180 days) = need $1333/mo, not achievable
        card_ids = [r["card_id"] for r in results]
        assert "card-freedom" in card_ids
        assert "card-sapphire" not in card_ids

    def test_excludes_cards_user_already_has(self):
        from app.services.card_recommendation import CardRecommendationService

        service = CardRecommendationService()
        profile = _make_profile(avg_monthly_spend=3000.0)
        user_cards = [{"name": "Sapphire Preferred", "issuer": "CHASE"}]

        results = service.recommend_next_card(profile, user_cards, SAMPLE_CARDS)

        card_ids = [r["card_id"] for r in results]
        assert "card-sapphire" not in card_ids

    def test_no_offers_card_excluded(self):
        from app.services.card_recommendation import CardRecommendationService

        service = CardRecommendationService()
        cards_no_offer = [
            {**SAMPLE_CARDS[0], "cardId": "card-no-offer", "offers": []},
        ]
        profile = _make_profile(avg_monthly_spend=3000.0)

        results = service.recommend_next_card(profile, [], cards_no_offer)
        assert len(results) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_card_recommendation_service.py::TestRecommendNextCard -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement CardRecommendationService — next card logic**

Create `apps/api/app/services/card_recommendation.py`:

```python
from __future__ import annotations

from math import ceil
from typing import Any


class CardRecommendationService:
    """Pure-function recommendation engine. No DB dependency."""

    def recommend_next_card(
        self,
        profile: dict,
        user_cards: list[dict],
        available_cards: list[dict],
        max_results: int = 10,
    ) -> list[dict]:
        avg_monthly = profile["avg_monthly_spend"]
        if avg_monthly <= 0:
            return []

        # Build set of owned cards for exclusion (normalized name + issuer)
        owned = set()
        for uc in user_cards:
            key = (uc.get("name", "").lower().strip(), uc.get("issuer", "").upper().strip())
            owned.add(key)

        results = []
        for card in available_cards:
            if card.get("discontinued"):
                continue

            # Skip cards user already owns
            card_key = (card["name"].lower().strip(), card.get("issuer", "").upper().strip())
            if card_key in owned:
                continue

            offers = card.get("offers", [])
            if not offers:
                continue

            best_offer = max(offers, key=lambda o: sum(a["amount"] for a in o.get("amount", [])))
            bonus_value = sum(a["amount"] for a in best_offer.get("amount", []))
            min_spend = best_offer.get("spend", 0)
            bonus_days = best_offer.get("days", 90)

            if min_spend <= 0:
                months_to_hit = 0.0
                achievable = True
            else:
                months_to_hit = min_spend / avg_monthly
                max_months = bonus_days / 30.0
                achievable = months_to_hit <= max_months

            if not achievable:
                continue

            annual_fee = card.get("annualFee", 0)
            fee_first_year = 0 if card.get("isAnnualFeeWaived") else annual_fee
            credit_value = sum(
                c.get("value", 0) * c.get("weight", 1.0) for c in card.get("credits", [])
            )
            score = bonus_value - fee_first_year + credit_value

            months_str = (
                "less than a month"
                if months_to_hit < 1
                else f"~{ceil(months_to_hit)} month{'s' if ceil(months_to_hit) != 1 else ''}"
            )
            explanation = (
                f"You spend ~${avg_monthly:,.0f}/mo. "
                f"You'd hit the ${min_spend:,.0f} minimum spend in {months_str} "
                f"(within the {bonus_days}-day window). "
                f"Bonus value: {bonus_value:,} points."
            )
            if fee_first_year > 0:
                explanation += f" Annual fee: ${fee_first_year}."
            if credit_value > 0:
                explanation += f" Card credits worth ~${credit_value:,.0f}/yr."

            results.append({
                "card_id": card["cardId"],
                "name": card["name"],
                "issuer": card.get("issuer", ""),
                "network": card.get("network", ""),
                "annual_fee": annual_fee,
                "is_annual_fee_waived": card.get("isAnnualFeeWaived", False),
                "universal_cashback_percent": card.get("universalCashbackPercent", 0),
                "currency": card.get("currency", ""),
                "url": card.get("url", ""),
                "image_url": card.get("imageUrl", ""),
                "bonus": {
                    "amount": bonus_value,
                    "min_spend": min_spend,
                    "days": bonus_days,
                    "months_to_hit": round(months_to_hit, 1),
                    "achievable": achievable,
                },
                "score": score,
                "explanation": explanation,
            })

        results.sort(key=lambda r: -r["score"])
        return results[:max_results]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_card_recommendation_service.py::TestRecommendNextCard -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/card_recommendation.py apps/api/tests/test_card_recommendation_service.py
git commit -m "feat: add CardRecommendationService with next-card scoring"
```

---

## Task 7: CardRecommendationService — Portfolio Analysis Logic

**Files:**
- Modify: `apps/api/app/services/card_recommendation.py`
- Modify: `apps/api/tests/test_card_recommendation_service.py`

- [ ] **Step 1: Write failing tests for portfolio analysis**

Append to `apps/api/tests/test_card_recommendation_service.py`:

```python
class TestAnalyzePortfolio:
    def test_flags_card_costing_money(self):
        from app.services.card_recommendation import CardRecommendationService

        service = CardRecommendationService()
        profile = _make_profile(avg_monthly_spend=500.0)
        # User has Platinum ($695/yr fee) but only spends $500/mo
        # Value: $500 * 12 * 0.01 = $60 cashback + ~$360 credits = $420. Net = 420 - 695 = -275
        user_cards = [
            {"name": "Platinum Card", "issuer": "AMERICAN_EXPRESS", "network": "AMERICAN_EXPRESS", "annual_fee": 695}
        ]

        result = service.analyze_portfolio(profile, user_cards, SAMPLE_CARDS)

        assert len(result) == 1
        assert result[0]["status"] == "costing_money"
        assert result[0]["net_value"] < 0

    def test_flags_card_as_good(self):
        from app.services.card_recommendation import CardRecommendationService

        service = CardRecommendationService()
        profile = _make_profile(avg_monthly_spend=5000.0)
        user_cards = [
            {"name": "Freedom Unlimited", "issuer": "CHASE", "network": "VISA", "annual_fee": 0}
        ]

        result = service.analyze_portfolio(profile, user_cards, SAMPLE_CARDS)

        assert len(result) == 1
        assert result[0]["status"] == "good"
        assert result[0]["net_value"] > 0

    def test_suggests_alternatives_for_bad_cards(self):
        from app.services.card_recommendation import CardRecommendationService

        service = CardRecommendationService()
        profile = _make_profile(avg_monthly_spend=500.0)
        user_cards = [
            {"name": "Platinum Card", "issuer": "AMERICAN_EXPRESS", "network": "AMERICAN_EXPRESS", "annual_fee": 695}
        ]

        result = service.analyze_portfolio(profile, user_cards, SAMPLE_CARDS)

        assert result[0]["status"] == "costing_money"
        assert len(result[0]["alternatives"]) > 0

    def test_empty_portfolio(self):
        from app.services.card_recommendation import CardRecommendationService

        service = CardRecommendationService()
        profile = _make_profile(avg_monthly_spend=2000.0)

        result = service.analyze_portfolio(profile, [], SAMPLE_CARDS)
        assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_card_recommendation_service.py::TestAnalyzePortfolio -v`
Expected: FAIL — `AttributeError: 'CardRecommendationService' has no attribute 'analyze_portfolio'`

- [ ] **Step 3: Implement analyze_portfolio method**

Add to `apps/api/app/services/card_recommendation.py` inside the `CardRecommendationService` class:

```python
    def _estimate_card_value(self, card: dict, avg_monthly_spend: float) -> float:
        cashback = avg_monthly_spend * 12 * card.get("universalCashbackPercent", 0) / 100
        credit_value = sum(
            c.get("value", 0) * c.get("weight", 1.0) for c in card.get("credits", [])
        )
        return round(cashback + credit_value, 2)

    def _find_api_card(self, user_card: dict, available_cards: list[dict]) -> dict | None:
        name = user_card.get("name", "").lower().strip()
        issuer = user_card.get("issuer", "").upper().strip()
        for card in available_cards:
            if card["name"].lower().strip() == name:
                if issuer and card.get("issuer", "").upper().strip() == issuer:
                    return card
                if not issuer:
                    return card
        return None

    def analyze_portfolio(
        self,
        profile: dict,
        user_cards: list[dict],
        available_cards: list[dict],
    ) -> list[dict]:
        if not user_cards:
            return []

        avg_monthly = profile["avg_monthly_spend"]
        results = []

        for uc in user_cards:
            annual_fee = uc.get("annual_fee", 0)
            api_card = self._find_api_card(uc, available_cards)

            if api_card:
                estimated_value = self._estimate_card_value(api_card, avg_monthly)
            else:
                # Fallback: just use universal 1% estimate
                estimated_value = round(avg_monthly * 12 * 0.01, 2)

            net_value = round(estimated_value - annual_fee, 2)

            if net_value < 0:
                status = "costing_money"
            elif net_value < annual_fee * 0.5 and annual_fee > 0:
                status = "underperforming"
            else:
                status = "good"

            # Find alternatives for non-good cards
            alternatives = []
            if status != "good":
                for card in available_cards:
                    if card.get("discontinued"):
                        continue
                    alt_fee = card.get("annualFee", 0)
                    if alt_fee > annual_fee:
                        continue
                    alt_value = self._estimate_card_value(card, avg_monthly)
                    alt_net = round(alt_value - alt_fee, 2)
                    if alt_net > net_value:
                        alternatives.append({
                            "card_id": card["cardId"],
                            "name": card["name"],
                            "issuer": card.get("issuer", ""),
                            "annual_fee": alt_fee,
                            "estimated_annual_value": alt_value,
                            "net_value": alt_net,
                            "url": card.get("url", ""),
                        })
                alternatives.sort(key=lambda a: -a["net_value"])
                alternatives = alternatives[:5]

            explanation = f"Estimated annual value: ${estimated_value:,.0f}."
            if annual_fee > 0:
                explanation += f" Annual fee: ${annual_fee:,.0f}."
            if status == "costing_money":
                explanation += f" Net cost: ${abs(net_value):,.0f}/yr."
            elif status == "underperforming":
                explanation += f" Barely breaking even at ${net_value:,.0f}/yr net."
            else:
                explanation += f" Net value: ${net_value:,.0f}/yr."

            results.append({
                "card_name": uc.get("name", ""),
                "card_network": uc.get("network", ""),
                "annual_fee": annual_fee,
                "estimated_annual_value": estimated_value,
                "net_value": net_value,
                "status": status,
                "explanation": explanation,
                "alternatives": alternatives,
            })

        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_card_recommendation_service.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/card_recommendation.py apps/api/tests/test_card_recommendation_service.py
git commit -m "feat: add portfolio analysis to CardRecommendationService"
```

---

## Task 8: RecommendationSnapshotService

**Files:**
- Create: `apps/api/app/services/recommendation_snapshot.py`
- Create: `apps/api/tests/test_recommendation_snapshot_service.py`

- [ ] **Step 1: Write failing tests**

Create `apps/api/tests/test_recommendation_snapshot_service.py`:

```python
from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, patch

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.card import Card
from app.models.transaction import Transaction
from app.models.user import User


class TestRecommendationSnapshotService:
    def _seed_data(self, db_session: Session, user: User) -> None:
        account = Account(
            user_id=user.id, name="Checking", type="checking", balance=5000.0
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)

        db_session.add(
            Transaction(
                user_id=user.id, account_id=account.id, occurred_on=date(2026, 1, 5),
                amount=-2000.0, merchant="Store", normalized_merchant="store",
                category="shopping", is_income=False, dedupe_hash="snap-h1",
            )
        )
        db_session.add(
            Card(
                user_id=user.id, name="Freedom Unlimited", network="VISA",
                issuer="CHASE", annual_fee=0,
            )
        )
        db_session.commit()

    @patch("app.services.recommendation_snapshot._fetch_cards")
    def test_get_next_card_recommendations(self, mock_fetch, db_session: Session, seed_user: User):
        from app.services.recommendation_snapshot import RecommendationSnapshotService

        mock_fetch.return_value = [
            {
                "cardId": "card-test",
                "name": "Test Card",
                "issuer": "TEST",
                "network": "VISA",
                "currency": "USD",
                "isBusiness": False,
                "annualFee": 0,
                "isAnnualFeeWaived": False,
                "universalCashbackPercent": 2,
                "url": "https://example.com",
                "imageUrl": "/test.png",
                "credits": [],
                "offers": [{"spend": 500, "amount": [{"amount": 20000}], "days": 90, "credits": []}],
                "discontinued": False,
            }
        ]
        self._seed_data(db_session, seed_user)

        service = RecommendationSnapshotService(db_session)
        result = service.get_recommendations(seed_user.id, "next_card")

        assert "recommendations" in result
        assert "spending_profile" in result

    @patch("app.services.recommendation_snapshot._fetch_cards")
    def test_caches_on_second_call(self, mock_fetch, db_session: Session, seed_user: User):
        from app.services.recommendation_snapshot import RecommendationSnapshotService

        mock_fetch.return_value = [
            {
                "cardId": "card-test",
                "name": "Test Card",
                "issuer": "TEST",
                "network": "VISA",
                "currency": "USD",
                "isBusiness": False,
                "annualFee": 0,
                "isAnnualFeeWaived": False,
                "universalCashbackPercent": 2,
                "url": "https://example.com",
                "imageUrl": "/test.png",
                "credits": [],
                "offers": [{"spend": 500, "amount": [{"amount": 20000}], "days": 90, "credits": []}],
                "discontinued": False,
            }
        ]
        self._seed_data(db_session, seed_user)

        service = RecommendationSnapshotService(db_session)
        result1 = service.get_recommendations(seed_user.id, "next_card")
        result2 = service.get_recommendations(seed_user.id, "next_card")

        # fetch_cards called once for compute, second call uses cache
        assert mock_fetch.call_count == 1

    @patch("app.services.recommendation_snapshot._fetch_cards")
    def test_invalidate_forces_recompute(self, mock_fetch, db_session: Session, seed_user: User):
        from app.services.recommendation_snapshot import RecommendationSnapshotService

        mock_fetch.return_value = []
        self._seed_data(db_session, seed_user)

        service = RecommendationSnapshotService(db_session)
        service.get_recommendations(seed_user.id, "next_card")
        service.invalidate(seed_user.id)
        service.get_recommendations(seed_user.id, "next_card")

        assert mock_fetch.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_recommendation_snapshot_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement RecommendationSnapshotService**

Create `apps/api/app/services/recommendation_snapshot.py`:

```python
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.card import Card
from app.repositories.recommendation_snapshot import RecommendationSnapshotRepository
from app.services.card_bonuses import _fetch_cards
from app.services.card_recommendation import CardRecommendationService
from app.services.spending_profile import SpendingProfileService


def _compute_inputs_hash(profile_json: str, cards_json: str) -> str:
    raw = f"{profile_json}|{cards_json}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class RecommendationSnapshotService:
    def __init__(self, db: Session):
        self.db = db
        self.snapshot_repo = RecommendationSnapshotRepository(db)
        self.profile_service = SpendingProfileService(db)
        self.recommendation_service = CardRecommendationService()

    def _get_user_cards(self, user_id: int) -> list[dict]:
        stmt = select(Card).where(Card.user_id == user_id)
        cards = list(self.db.scalars(stmt).all())
        return [
            {
                "name": c.name,
                "issuer": c.issuer or "",
                "network": c.network,
                "annual_fee": c.annual_fee,
            }
            for c in cards
        ]

    def _profile_to_dict(self, profile) -> dict:
        import json as _json
        return {
            "avg_monthly_spend": profile.avg_monthly_spend,
            "category_breakdown": _json.loads(profile.category_breakdown_json),
            "top_merchants": _json.loads(profile.top_merchants_json),
        }

    def _profile_to_read(self, profile) -> dict:
        import json as _json
        return {
            "user_id": profile.user_id,
            "period_start": str(profile.period_start),
            "period_end": str(profile.period_end),
            "avg_monthly_spend": profile.avg_monthly_spend,
            "categories": [
                {"category": k, "monthly_avg": v}
                for k, v in _json.loads(profile.category_breakdown_json).items()
            ],
            "top_merchants": _json.loads(profile.top_merchants_json),
            "computed_at": str(profile.computed_at),
        }

    def get_recommendations(self, user_id: int, rec_type: str) -> dict:
        profile = self.profile_service.get_or_refresh(user_id)
        user_cards = self._get_user_cards(user_id)

        profile_json = profile.category_breakdown_json + str(profile.avg_monthly_spend)
        cards_json = json.dumps(user_cards, sort_keys=True)
        current_hash = _compute_inputs_hash(profile_json, cards_json)

        # Check cache
        existing = self.snapshot_repo.get(user_id, rec_type)
        if existing and existing.inputs_hash == current_hash:
            return {
                "recommendations" if rec_type == "next_card" else "cards": json.loads(existing.results_json),
                "spending_profile": self._profile_to_read(profile),
            }

        # Recompute
        available_cards = _fetch_cards()
        profile_dict = self._profile_to_dict(profile)

        if rec_type == "next_card":
            results = self.recommendation_service.recommend_next_card(
                profile_dict, user_cards, available_cards
            )
            result_key = "recommendations"
        else:
            results = self.recommendation_service.analyze_portfolio(
                profile_dict, user_cards, available_cards
            )
            result_key = "cards"

        self.snapshot_repo.upsert(
            user_id=user_id,
            rec_type=rec_type,
            results_json=json.dumps(results),
            inputs_hash=current_hash,
        )

        return {
            result_key: results,
            "spending_profile": self._profile_to_read(profile),
        }

    def invalidate(self, user_id: int) -> None:
        for rec_type in ("next_card", "portfolio_gap"):
            existing = self.snapshot_repo.get(user_id, rec_type)
            if existing:
                existing.inputs_hash = "invalidated"
                self.db.commit()
```

Note: `_fetch_cards` from `card_bonuses.py` is async. Since the snapshot service is sync, we need a sync wrapper. Update the import — the existing `_fetch_cards` is async but the test mocks patch it. For production, we need to make it sync or use `asyncio.run`. Let's add a sync fetch helper:

Replace the import and add at the top of `recommendation_snapshot.py`:

```python
import time
import httpx

from app.services.card_bonuses import DATA_URL, CACHE_TTL_SECONDS

_sync_cache: dict[str, Any] = {"data": None, "fetched_at": 0.0}


def _fetch_cards() -> list[dict[str, Any]]:
    now = time.time()
    if _sync_cache["data"] is not None and now - _sync_cache["fetched_at"] < CACHE_TTL_SECONDS:
        return _sync_cache["data"]
    resp = httpx.get(DATA_URL, timeout=15)
    resp.raise_for_status()
    cards = resp.json()
    _sync_cache["data"] = cards
    _sync_cache["fetched_at"] = now
    return cards
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_recommendation_snapshot_service.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/recommendation_snapshot.py apps/api/tests/test_recommendation_snapshot_service.py
git commit -m "feat: add RecommendationSnapshotService with caching"
```

---

## Task 9: Recommendations API Router

**Files:**
- Create: `apps/api/app/api/recommendations.py`
- Modify: `apps/api/app/api/router.py`
- Create: `apps/api/tests/test_recommendations_api.py`

- [ ] **Step 1: Write failing tests**

Create `apps/api/tests/test_recommendations_api.py`:

```python
from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.card import Card
from app.models.transaction import Transaction
from app.models.user import User

MOCK_CARDS = [
    {
        "cardId": "card-test",
        "name": "Test Rewards Card",
        "issuer": "TEST_BANK",
        "network": "VISA",
        "currency": "USD",
        "isBusiness": False,
        "annualFee": 0,
        "isAnnualFeeWaived": False,
        "universalCashbackPercent": 2,
        "url": "https://example.com",
        "imageUrl": "/test.png",
        "credits": [],
        "offers": [{"spend": 500, "amount": [{"amount": 20000}], "days": 90, "credits": []}],
        "discontinued": False,
    }
]


class TestRecommendationsAPI:
    def _seed(self, db_session: Session, user: User) -> None:
        account = Account(
            user_id=user.id, name="Checking", type="checking", balance=5000.0
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)

        db_session.add(
            Transaction(
                user_id=user.id, account_id=account.id, occurred_on=date(2026, 1, 5),
                amount=-1500.0, merchant="Store", normalized_merchant="store",
                category="shopping", is_income=False, dedupe_hash="api-h1",
            )
        )
        db_session.commit()

    @patch("app.services.recommendation_snapshot._fetch_cards", return_value=MOCK_CARDS)
    def test_get_next_card(self, mock_fetch, client: TestClient, db_session: Session, seed_user: User):
        self._seed(db_session, seed_user)
        resp = client.get("/recommendations/next-card")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data
        assert "spending_profile" in data

    @patch("app.services.recommendation_snapshot._fetch_cards", return_value=MOCK_CARDS)
    def test_get_portfolio(self, mock_fetch, client: TestClient, db_session: Session, seed_user: User):
        self._seed(db_session, seed_user)
        resp = client.get("/recommendations/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "cards" in data
        assert "spending_profile" in data

    @patch("app.services.recommendation_snapshot._fetch_cards", return_value=MOCK_CARDS)
    def test_get_spending_profile(self, mock_fetch, client: TestClient, db_session: Session, seed_user: User):
        self._seed(db_session, seed_user)
        resp = client.get("/recommendations/spending-profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "avg_monthly_spend" in data
        assert "categories" in data

    @patch("app.services.recommendation_snapshot._fetch_cards", return_value=MOCK_CARDS)
    def test_refresh(self, mock_fetch, client: TestClient, db_session: Session, seed_user: User):
        self._seed(db_session, seed_user)
        resp = client.post("/recommendations/refresh")
        assert resp.status_code == 200
        assert resp.json()["status"] == "refreshed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_recommendations_api.py -v`
Expected: FAIL — 404 (route not registered)

- [ ] **Step 3: Create recommendations router**

Create `apps/api/app/api/recommendations.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.services.recommendation_snapshot import RecommendationSnapshotService
from app.services.spending_profile import SpendingProfileService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/next-card")
def get_next_card(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    service = RecommendationSnapshotService(db)
    return service.get_recommendations(user_id, "next_card")


@router.get("/portfolio")
def get_portfolio(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    service = RecommendationSnapshotService(db)
    return service.get_recommendations(user_id, "portfolio_gap")


@router.get("/spending-profile")
def get_spending_profile(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    service = SpendingProfileService(db)
    profile = service.get_or_refresh(user_id)
    import json
    return {
        "user_id": profile.user_id,
        "period_start": str(profile.period_start),
        "period_end": str(profile.period_end),
        "avg_monthly_spend": profile.avg_monthly_spend,
        "categories": [
            {"category": k, "monthly_avg": v}
            for k, v in json.loads(profile.category_breakdown_json).items()
        ],
        "top_merchants": json.loads(profile.top_merchants_json),
        "computed_at": str(profile.computed_at),
    }


@router.post("/refresh")
def refresh_recommendations(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    service = RecommendationSnapshotService(db)
    service.invalidate(user_id)
    service.get_recommendations(user_id, "next_card")
    service.get_recommendations(user_id, "portfolio_gap")
    return {"status": "refreshed"}
```

- [ ] **Step 4: Register router in app/api/router.py**

Edit `apps/api/app/api/router.py` to add:

```python
from app.api.recommendations import router as recommendations_router
```

And add:

```python
api_router.include_router(recommendations_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_recommendations_api.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Run full test suite**

Run: `cd apps/api && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/api/recommendations.py apps/api/app/api/router.py apps/api/tests/test_recommendations_api.py
git commit -m "feat: add /recommendations API endpoints"
```

---

## Task 10: Frontend Types and API Functions

**Files:**
- Modify: `apps/web/src/lib/types.ts`
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1: Add recommendation types**

Add to `apps/web/src/lib/types.ts`:

```typescript
export interface CategorySpend {
  category: string;
  monthly_avg: number;
}

export interface TopMerchant {
  name: string;
  monthly_avg: number;
}

export interface SpendingProfile {
  user_id: number;
  period_start: string;
  period_end: string;
  avg_monthly_spend: number;
  categories: CategorySpend[];
  top_merchants: TopMerchant[];
  computed_at: string;
}

export interface BonusInfo {
  amount: number;
  min_spend: number;
  days: number;
  months_to_hit: number;
  achievable: boolean;
}

export interface NextCardRecommendation {
  card_id: string;
  name: string;
  issuer: string;
  network: string;
  annual_fee: number;
  is_annual_fee_waived: boolean;
  universal_cashback_percent: number;
  currency: string;
  url: string;
  image_url: string;
  bonus: BonusInfo | null;
  score: number;
  explanation: string;
}

export interface NextCardResponse {
  recommendations: NextCardRecommendation[];
  spending_profile: SpendingProfile;
}

export interface AlternativeCard {
  card_id: string;
  name: string;
  issuer: string;
  annual_fee: number;
  estimated_annual_value: number;
  net_value: number;
  url: string;
}

export interface CardAnalysis {
  card_name: string;
  card_network: string;
  annual_fee: number;
  estimated_annual_value: number;
  net_value: number;
  status: "good" | "underperforming" | "costing_money";
  explanation: string;
  alternatives: AlternativeCard[];
}

export interface PortfolioResponse {
  cards: CardAnalysis[];
  spending_profile: SpendingProfile;
}
```

- [ ] **Step 2: Add API functions**

Add to `apps/web/src/lib/api.ts`:

```typescript
import type {
  // ... existing imports ...
  NextCardResponse,
  PortfolioResponse,
  SpendingProfile,
} from "./types";

// Recommendations
export const getNextCardRecommendations = () =>
  request<NextCardResponse>("/recommendations/next-card");
export const getPortfolioAnalysis = () =>
  request<PortfolioResponse>("/recommendations/portfolio");
export const getSpendingProfile = () =>
  request<SpendingProfile>("/recommendations/spending-profile");
export const refreshRecommendations = () =>
  request<{ status: string }>("/recommendations/refresh", { method: "POST" });
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/types.ts apps/web/src/lib/api.ts
git commit -m "feat: add recommendation types and API functions to frontend"
```

---

## Task 11: Recommendations Page

**Files:**
- Create: `apps/web/src/app/(app)/recommendations/page.tsx`
- Modify: `apps/web/src/components/sidebar.tsx`

**Important:** Read `node_modules/next/dist/docs/` before writing Next.js code, as the AGENTS.md warns about breaking changes.

- [ ] **Step 1: Read Next.js docs for any breaking changes**

Run: `ls apps/web/node_modules/next/dist/docs/` and read relevant files to check for App Router changes.

- [ ] **Step 2: Create the recommendations page**

Create `apps/web/src/app/(app)/recommendations/page.tsx`:

```tsx
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getNextCardRecommendations,
  getPortfolioAnalysis,
  refreshRecommendations,
} from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { useState } from "react";
import { Lightbulb, RefreshCw, TrendingUp, AlertTriangle, CheckCircle, ExternalLink } from "lucide-react";

function NextCardTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["recommendations", "next-card"],
    queryFn: getNextCardRecommendations,
  });

  if (isLoading) {
    return <div className="text-muted text-sm">Analyzing your spending...</div>;
  }

  const recs = data?.recommendations ?? [];

  if (recs.length === 0) {
    return (
      <div className="text-center py-12 text-muted">
        <Lightbulb className="w-8 h-8 mx-auto mb-3 opacity-50" />
        <p>No recommendations yet. Add more transactions to get personalized suggestions.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {recs.map((rec) => (
        <div key={rec.card_id} className="bg-card rounded-xl border border-border p-6">
          <div className="flex items-start justify-between mb-3">
            <div>
              <h3 className="font-semibold text-card-foreground">{rec.name}</h3>
              <p className="text-sm text-muted">{rec.issuer} &middot; {rec.network}</p>
            </div>
            {rec.url && (
              <a
                href={rec.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-card-foreground transition-colors"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            )}
          </div>

          {rec.bonus && (
            <div className="flex gap-4 mb-3 text-sm">
              <div>
                <span className="text-muted">Bonus:</span>{" "}
                <span className="font-mono font-medium text-card-foreground">
                  {rec.bonus.amount.toLocaleString()} pts
                </span>
              </div>
              <div>
                <span className="text-muted">Min spend:</span>{" "}
                <span className="font-mono text-card-foreground">
                  {formatCurrency(rec.bonus.min_spend)}
                </span>
              </div>
              <div>
                <span className="text-muted">Time to hit:</span>{" "}
                <span className="font-mono text-card-foreground">
                  ~{Math.ceil(rec.bonus.months_to_hit)} mo
                </span>
              </div>
            </div>
          )}

          <p className="text-sm text-muted-foreground">{rec.explanation}</p>

          {rec.annual_fee > 0 && (
            <div className="mt-2 text-xs text-muted">
              Annual fee: {formatCurrency(rec.annual_fee)}
              {rec.is_annual_fee_waived && " (waived first year)"}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function PortfolioTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["recommendations", "portfolio"],
    queryFn: getPortfolioAnalysis,
  });

  if (isLoading) {
    return <div className="text-muted text-sm">Analyzing your portfolio...</div>;
  }

  const cards = data?.cards ?? [];

  if (cards.length === 0) {
    return (
      <div className="text-center py-12 text-muted">
        <Lightbulb className="w-8 h-8 mx-auto mb-3 opacity-50" />
        <p>Add your credit cards to get a portfolio analysis.</p>
      </div>
    );
  }

  const statusIcon = {
    good: <CheckCircle className="w-5 h-5 text-emerald-500" />,
    underperforming: <AlertTriangle className="w-5 h-5 text-amber-500" />,
    costing_money: <AlertTriangle className="w-5 h-5 text-red-500" />,
  };

  return (
    <div className="space-y-4">
      {cards.map((card, i) => (
        <div key={i} className="bg-card rounded-xl border border-border p-6">
          <div className="flex items-start gap-3 mb-3">
            {statusIcon[card.status]}
            <div>
              <h3 className="font-semibold text-card-foreground">{card.card_name}</h3>
              <p className="text-sm text-muted">{card.card_network}</p>
            </div>
          </div>

          <div className="flex gap-4 mb-3 text-sm">
            <div>
              <span className="text-muted">Annual fee:</span>{" "}
              <span className="font-mono text-card-foreground">{formatCurrency(card.annual_fee)}</span>
            </div>
            <div>
              <span className="text-muted">Est. value:</span>{" "}
              <span className="font-mono text-card-foreground">{formatCurrency(card.estimated_annual_value)}</span>
            </div>
            <div>
              <span className="text-muted">Net:</span>{" "}
              <span className={`font-mono font-medium ${card.net_value >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                {formatCurrency(card.net_value)}
              </span>
            </div>
          </div>

          <p className="text-sm text-muted-foreground">{card.explanation}</p>

          {card.alternatives.length > 0 && (
            <div className="mt-4 pt-3 border-t border-border">
              <p className="text-xs font-medium text-muted mb-2">Better alternatives:</p>
              <div className="space-y-2">
                {card.alternatives.slice(0, 3).map((alt) => (
                  <div key={alt.card_id} className="flex items-center justify-between text-sm">
                    <div>
                      <span className="text-card-foreground">{alt.name}</span>
                      <span className="text-muted ml-2">{alt.issuer}</span>
                    </div>
                    <div className="flex gap-3 text-xs">
                      <span className="text-muted">Fee: {formatCurrency(alt.annual_fee)}</span>
                      <span className="text-emerald-500 font-mono">Net: {formatCurrency(alt.net_value)}</span>
                      {alt.url && (
                        <a href={alt.url} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-card-foreground">
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function RecommendationsPage() {
  const [tab, setTab] = useState<"next-card" | "portfolio">("next-card");
  const queryClient = useQueryClient();

  const refreshMutation = useMutation({
    mutationFn: refreshRecommendations,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-card-foreground">Recommendations</h1>
          <p className="text-sm text-muted mt-1">Personalized credit card advice based on your spending</p>
        </div>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-border hover:bg-accent/50 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${refreshMutation.isPending ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      <div className="flex gap-1 mb-6 bg-muted/30 rounded-lg p-1">
        <button
          onClick={() => setTab("next-card")}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm rounded-md transition-colors ${
            tab === "next-card"
              ? "bg-card text-card-foreground shadow-sm"
              : "text-muted hover:text-card-foreground"
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          Next Card
        </button>
        <button
          onClick={() => setTab("portfolio")}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm rounded-md transition-colors ${
            tab === "portfolio"
              ? "bg-card text-card-foreground shadow-sm"
              : "text-muted hover:text-card-foreground"
          }`}
        >
          <Lightbulb className="w-4 h-4" />
          Portfolio Analysis
        </button>
      </div>

      {tab === "next-card" ? <NextCardTab /> : <PortfolioTab />}
    </div>
  );
}
```

- [ ] **Step 3: Add Recommendations to sidebar navigation**

Edit `apps/web/src/components/sidebar.tsx` — add to imports:

```typescript
import { Lightbulb } from "lucide-react";
```

Add to `navItems` array (after Cards):

```typescript
{ href: "/recommendations", label: "Recommendations", icon: Lightbulb },
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd apps/web && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/app/\(app\)/recommendations/page.tsx apps/web/src/components/sidebar.tsx
git commit -m "feat: add recommendations page and sidebar nav item"
```

---

## Task 12: Dashboard Recommendation Widget

**Files:**
- Modify: `apps/web/src/app/(app)/dashboard/page.tsx`

- [ ] **Step 1: Add recommendation widget to dashboard**

Edit `apps/web/src/app/(app)/dashboard/page.tsx`:

Add import:

```typescript
import { getNextCardRecommendations } from "@/lib/api";
import { Lightbulb } from "lucide-react";
import Link from "next/link";
```

Add query inside `DashboardPage`:

```typescript
const { data: recommendations } = useQuery({
  queryKey: ["recommendations", "next-card"],
  queryFn: getNextCardRecommendations,
});
```

Add widget after the stats grid and before `<Chat />`:

```tsx
{recommendations?.recommendations && recommendations.recommendations.length > 0 && (
  <div className="bg-card rounded-xl border border-border p-6 mb-8">
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <Lightbulb className="w-5 h-5 text-muted-foreground" />
        <h2 className="font-semibold text-card-foreground">Top Card Picks</h2>
      </div>
      <Link
        href="/recommendations"
        className="text-sm text-muted hover:text-card-foreground transition-colors"
      >
        View all &rarr;
      </Link>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {recommendations.recommendations.slice(0, 2).map((rec) => (
        <div key={rec.card_id} className="rounded-lg border border-border p-4">
          <div className="flex items-start justify-between mb-2">
            <div>
              <p className="font-medium text-sm text-card-foreground">{rec.name}</p>
              <p className="text-xs text-muted">{rec.issuer}</p>
            </div>
            {rec.bonus && (
              <span className="text-xs font-mono bg-emerald-500/10 text-emerald-500 px-2 py-0.5 rounded">
                {rec.bonus.amount.toLocaleString()} pts
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground line-clamp-2">{rec.explanation}</p>
        </div>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 2: Verify frontend builds**

Run: `cd apps/web && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/\(app\)/dashboard/page.tsx
git commit -m "feat: add recommendation widget to dashboard"
```

---

## Task 13: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update changelog**

Add under `[Unreleased]`:

```markdown
### Added
- Credit card recommendation engine with sign-up bonus achievability scoring
- Portfolio analysis to flag underperforming cards and suggest alternatives
- Spending profile aggregation service with caching
- `/recommendations` API endpoints (next-card, portfolio, spending-profile, refresh)
- Recommendations page with Next Card and Portfolio Analysis tabs
- Dashboard widget showing top 2 card recommendations
- `issuer` field on Card model for better card matching
- `spending_profiles` and `recommendation_snapshots` database tables
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: update changelog with recommendation engine feature"
```
