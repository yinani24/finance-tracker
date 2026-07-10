from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.spending_profile import SpendingProfile
from app.models.transaction import Transaction
from app.repositories.spending_profile import SpendingProfileRepository


def _months_spanned(period_start: date, period_end: date) -> float:
    """Return the number of calendar months between two dates (minimum 1)."""
    months = (
        (period_end.year - period_start.year) * 12
        + (period_end.month - period_start.month)
        + 1
    )
    return max(float(months), 1.0)


def _lookback_start(lookback_months: int, today: Optional[date] = None) -> date:
    """Return the first day of the month N months ago (no external deps).

    ``today`` is injectable so callers can simulate a slid window without
    freezing the wall clock; it defaults to ``date.today()``.
    """
    if today is None:
        today = date.today()
    total_months = today.year * 12 + (today.month - 1)
    total_months -= lookback_months
    year = total_months // 12
    month = (total_months % 12) + 1
    return date(year, month, 1)


def compute_profile(
    db: Session,
    user_id: int,
    lookback_months: int = 6,
    today: Optional[date] = None,
) -> SpendingProfile:
    """Aggregate non-income transactions into a SpendingProfile and upsert it.

    ``today`` defaults to ``date.today()`` and only exists so the lookback
    window can be pinned in tests; production callers omit it.
    """
    if today is None:
        today = date.today()
    cutoff = _lookback_start(lookback_months, today=today)

    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.is_income.is_(False))
        .where(Transaction.occurred_on >= cutoff)
        .order_by(Transaction.occurred_on)
    )
    transactions: List[Transaction] = list(db.scalars(stmt).all())

    repo = SpendingProfileRepository(db)

    if not transactions:
        return repo.upsert(
            user_id=user_id,
            period_start=cutoff,
            period_end=today,
            avg_monthly_spend=0.0,
            category_breakdown_json="{}",
            top_merchants_json="[]",
            category_counts_json="{}",
        )

    # Determine actual period from transactions
    period_start = transactions[0].occurred_on
    period_end = transactions[-1].occurred_on
    months = _months_spanned(period_start, period_end)

    total_spend = sum(abs(t.amount) for t in transactions)
    avg_monthly_spend = total_spend / months

    # Category breakdown: monthly average per category, plus transaction counts
    # (the frequency signal — "how many times did I dine out"). Both accumulated
    # in the same pass, no extra query.
    category_totals: Dict[str, float] = defaultdict(float)
    category_counts: Dict[str, int] = defaultdict(int)
    for t in transactions:
        cat = t.category or "uncategorized"
        category_totals[cat] += abs(t.amount)
        category_counts[cat] += 1
    category_breakdown: Dict[str, float] = {
        cat: round(total / months, 2) for cat, total in category_totals.items()
    }

    # Top 10 merchants by monthly avg spend
    merchant_totals: Dict[str, float] = defaultdict(float)
    for t in transactions:
        name = t.normalized_merchant or t.merchant
        merchant_totals[name] += abs(t.amount)
    sorted_merchants = sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)
    top_merchants: List[Dict] = [
        {"merchant": m, "monthly_avg": round(total / months, 2)}
        for m, total in sorted_merchants[:10]
    ]

    return repo.upsert(
        user_id=user_id,
        period_start=period_start,
        period_end=period_end,
        avg_monthly_spend=round(avg_monthly_spend, 2),
        category_breakdown_json=json.dumps(category_breakdown),
        top_merchants_json=json.dumps(top_merchants),
        category_counts_json=json.dumps(dict(category_counts)),
    )


def get_or_refresh(
    db: Session,
    user_id: int,
    lookback_months: int = 6,
    today: Optional[date] = None,
) -> SpendingProfile:
    """Return cached profile if fresh; otherwise recompute.

    Two things can make a cached profile stale:
    1. A newer transaction arrived (``computed_at`` predates it).
    2. Wall-clock time crossed into a new month, so ``_lookback_start`` has
       advanced and the oldest month(s) reflected in the profile have aged out
       of the lookback window — even with no new transaction. Serving the cache
       here would keep inflating the averages until the next ingest.

    ``today`` is injectable (defaults to ``date.today()``) so the window-slide
    path can be exercised in tests without freezing the clock.
    """
    if today is None:
        today = date.today()
    repo = SpendingProfileRepository(db)
    existing = repo.get_by_user(user_id)

    if existing is not None:
        # Window-slide check: the cached profile only reflects transactions on
        # or after the cutoff in force when it was computed. Its earliest such
        # transaction is ``period_start``. If the current cutoff has advanced
        # past ``period_start``, that oldest transaction (and possibly a whole
        # month) has aged out, so the cached averages are stale — recompute.
        current_cutoff = _lookback_start(lookback_months, today=today)
        window_slid = current_cutoff > existing.period_start

        if not window_slid:
            # Find the most recently created transaction for this user
            stmt = (
                select(Transaction.created_at)
                .where(Transaction.user_id == user_id)
                .order_by(Transaction.created_at.desc())
                .limit(1)
            )
            latest_txn_created_at: Optional[datetime] = db.scalars(stmt).first()

            if latest_txn_created_at is not None:
                # Normalise both datetimes to UTC-aware for comparison
                computed_at = existing.computed_at
                if computed_at.tzinfo is None:
                    computed_at = computed_at.replace(tzinfo=timezone.utc)
                if latest_txn_created_at.tzinfo is None:
                    latest_txn_created_at = latest_txn_created_at.replace(
                        tzinfo=timezone.utc
                    )

                if computed_at >= latest_txn_created_at:
                    return existing

    return compute_profile(db, user_id, lookback_months, today=today)
