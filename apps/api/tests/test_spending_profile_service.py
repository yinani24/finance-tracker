from datetime import date

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User


def _seed_transactions(db_session: Session, user: User) -> None:
    account = Account(
        user_id=user.id, name="Checking", type="checking", balance=5000.0
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    transactions = [
        Transaction(
            user_id=user.id, account_id=account.id, occurred_on=date(2026, 1, 5),
            amount=-50.0, merchant="Chipotle", normalized_merchant="chipotle",
            category="food and drink", is_income=False, dedupe_hash="sp-h1",
        ),
        Transaction(
            user_id=user.id, account_id=account.id, occurred_on=date(2026, 1, 15),
            amount=-80.0, merchant="Sushi Place", normalized_merchant="sushi place",
            category="food and drink", is_income=False, dedupe_hash="sp-h2",
        ),
        Transaction(
            user_id=user.id, account_id=account.id, occurred_on=date(2026, 1, 20),
            amount=-300.0, merchant="Delta Airlines", normalized_merchant="delta airlines",
            category="travel", is_income=False, dedupe_hash="sp-h3",
        ),
        Transaction(
            user_id=user.id, account_id=account.id, occurred_on=date(2026, 2, 10),
            amount=-60.0, merchant="Chipotle", normalized_merchant="chipotle",
            category="food and drink", is_income=False, dedupe_hash="sp-h4",
        ),
        Transaction(
            user_id=user.id, account_id=account.id, occurred_on=date(2026, 2, 12),
            amount=-200.0, merchant="Whole Foods", normalized_merchant="whole foods",
            category="groceries", is_income=False, dedupe_hash="sp-h5",
        ),
        Transaction(
            user_id=user.id, account_id=account.id, occurred_on=date(2026, 1, 1),
            amount=5000.0, merchant="Employer", normalized_merchant="employer",
            category="income", is_income=True, dedupe_hash="sp-h6",
        ),
    ]
    db_session.add_all(transactions)
    db_session.commit()


class TestComputeProfile:
    def test_computes_categories_and_merchants(self, db_session: Session, seed_user: User):
        _seed_transactions(db_session, seed_user)
        import json

        from app.services.spending_profile import compute_profile

        # Pin ``today`` so the fixed Jan/Feb-2026 seed dates stay inside the
        # 6-month lookback regardless of the wall clock (see #220). Matches the
        # window used by the window-slide tests below.
        profile = compute_profile(
            db_session, seed_user.id, lookback_months=6, today=date(2026, 2, 28)
        )

        assert profile.avg_monthly_spend > 0
        categories = json.loads(profile.category_breakdown_json)
        assert "food and drink" in categories
        assert "travel" in categories

        merchants = json.loads(profile.top_merchants_json)
        merchant_names = [m["merchant"] for m in merchants]
        assert "chipotle" in merchant_names

    def test_excludes_income(self, db_session: Session, seed_user: User):
        _seed_transactions(db_session, seed_user)
        from app.services.spending_profile import compute_profile

        profile = compute_profile(db_session, seed_user.id, lookback_months=6)
        # Total expenses: 50+80+300+60+200 = 690 over 2 months = 345/mo
        assert profile.avg_monthly_spend < 1000

    def test_no_transactions(self, db_session: Session, seed_user: User):
        from app.services.spending_profile import compute_profile

        profile = compute_profile(db_session, seed_user.id, lookback_months=6)
        assert profile.avg_monthly_spend == 0.0

    def test_records_category_counts(self, db_session: Session, seed_user: User):
        _seed_transactions(db_session, seed_user)
        import json

        from app.services.spending_profile import compute_profile

        # Pin ``today`` so the fixed Jan/Feb-2026 seed dates stay inside the
        # 6-month lookback regardless of the wall clock (see #220).
        profile = compute_profile(
            db_session, seed_user.id, lookback_months=6, today=date(2026, 2, 28)
        )
        counts = json.loads(profile.category_counts_json)
        # 3 food-and-drink txns, 1 travel, 1 groceries (income excluded).
        assert counts["food and drink"] == 3
        assert counts["travel"] == 1
        assert counts["groceries"] == 1
        assert "income" not in counts

    def test_empty_profile_has_empty_counts(self, db_session: Session, seed_user: User):
        import json

        from app.services.spending_profile import compute_profile

        profile = compute_profile(db_session, seed_user.id, lookback_months=6)
        assert json.loads(profile.category_counts_json) == {}


class TestGetOrRefresh:
    def test_caches_when_no_new_transactions(self, db_session: Session, seed_user: User):
        _seed_transactions(db_session, seed_user)
        from app.services.spending_profile import get_or_refresh

        profile1 = get_or_refresh(db_session, seed_user.id)
        profile2 = get_or_refresh(db_session, seed_user.id)
        assert profile2.computed_at == profile1.computed_at

    def test_recomputes_when_window_slides(self, db_session: Session, seed_user: User):
        """A profile must be recomputed once wall-clock time slides the lookback
        window past its data, even when no new transaction has arrived."""
        _seed_transactions(db_session, seed_user)  # Jan/Feb 2026 expenses
        from app.services.spending_profile import get_or_refresh

        # Compute for a "today" where the Jan/Feb 2026 window is fully in range
        # (6-month lookback cutoff = 2025-08-01).
        profile1 = get_or_refresh(db_session, seed_user.id, today=date(2026, 2, 28))
        assert profile1.avg_monthly_spend > 0
        assert profile1.period_start == date(2026, 1, 5)

        # Advance "today" so the window slides past every seeded transaction
        # (cutoff = 2026-06-01). No new transaction is inserted.
        profile2 = get_or_refresh(db_session, seed_user.id, today=date(2026, 12, 1))

        # It must recompute against the slid window, not serve stale averages.
        assert profile2.period_start == date(2026, 6, 1)
        assert profile2.avg_monthly_spend == 0.0

    def test_caches_when_window_unchanged(self, db_session: Session, seed_user: User):
        """Same window + no new transaction ⇒ still a cache hit (no recompute)."""
        _seed_transactions(db_session, seed_user)
        from app.services.spending_profile import get_or_refresh

        profile1 = get_or_refresh(db_session, seed_user.id, today=date(2026, 2, 28))
        profile2 = get_or_refresh(db_session, seed_user.id, today=date(2026, 2, 28))
        assert profile2.computed_at == profile1.computed_at
