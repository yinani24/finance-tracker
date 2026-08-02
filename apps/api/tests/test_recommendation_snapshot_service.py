from __future__ import annotations

from datetime import date
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.card import Card
from app.models.transaction import Transaction
from app.models.user import User

MOCK_CARDS = [
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


def _seed_data(db_session: Session, user: User) -> None:
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


class TestRecommendationSnapshotService:
    @patch("app.services.recommendation_snapshot._fetch_cards", return_value=MOCK_CARDS)
    def test_get_next_card_recommendations(self, mock_fetch, db_session: Session, seed_user: User):
        from app.services.recommendation_snapshot import RecommendationSnapshotService

        _seed_data(db_session, seed_user)
        service = RecommendationSnapshotService(db_session)
        result = service.get_recommendations(seed_user.id, "next_card")

        assert "recommendations" in result
        assert "spending_profile" in result

    @patch("app.services.recommendation_snapshot._fetch_cards", return_value=MOCK_CARDS)
    def test_caches_on_second_call(self, mock_fetch, db_session: Session, seed_user: User):
        from app.services.recommendation_snapshot import RecommendationSnapshotService

        _seed_data(db_session, seed_user)
        service = RecommendationSnapshotService(db_session)
        # Spy on the write path: a cache hit must NOT recompute/upsert. (The
        # dataset fetch is a cheap process-wide TTL read and now runs on every
        # call so its contents can be folded into the cache key, so asserting on
        # the fetch count no longer measures caching — the upsert does.)
        with patch.object(
            service.snapshot_repo, "upsert", wraps=service.snapshot_repo.upsert
        ) as spy_upsert:
            service.get_recommendations(seed_user.id, "next_card")
            service.get_recommendations(seed_user.id, "next_card")

        assert spy_upsert.call_count == 1

    def test_dataset_change_recomputes(self, db_session: Session, seed_user: User):
        """A change in the card dataset must invalidate the cache (PRD FR5).

        The cache key previously omitted the dataset, so a second GET after an
        upstream sign-up-bonus change served the stale ranking. Now the dataset
        is fingerprinted into the key, so the snapshot is recomputed.
        """
        from app.services.recommendation_snapshot import RecommendationSnapshotService

        changed_cards = [dict(MOCK_CARDS[0])]
        # Same card, larger sign-up bonus — a real upstream refresh.
        changed_cards[0]["offers"] = [
            {"spend": 500, "amount": [{"amount": 50000}], "days": 90, "credits": []}
        ]

        _seed_data(db_session, seed_user)
        service = RecommendationSnapshotService(db_session)

        with patch(
            "app.services.recommendation_snapshot._fetch_cards",
            side_effect=[MOCK_CARDS, changed_cards],
        ):
            with patch.object(
                service.snapshot_repo, "upsert", wraps=service.snapshot_repo.upsert
            ) as spy_upsert:
                first = service.get_recommendations(seed_user.id, "next_card")
                second = service.get_recommendations(seed_user.id, "next_card")

        # Both GETs recomputed (dataset differed) → the second did not reuse the
        # first's stale snapshot.
        assert spy_upsert.call_count == 2
        # Bonuses have no ``currency`` field → valued as points at 1.0¢
        # (20000 pts → $200, 50000 pts → $500). The ranking reflects the newer,
        # larger bonus rather than the cached stale one.
        assert first["recommendations"][0]["bonus_value"] == 200.0
        assert second["recommendations"][0]["bonus_value"] == 500.0

    @patch(
        "app.services.recommendation_snapshot._fetch_cards",
        return_value=[
            {
                "cardId": "card-freedom", "name": "Freedom Unlimited", "issuer": "CHASE",
                "network": "VISA", "currency": "USD", "isBusiness": False, "annualFee": 0,
                "isAnnualFeeWaived": False, "universalCashbackPercent": 1.5,
                "url": "https://example.com", "imageUrl": "/f.png", "credits": [],
                "offers": [
                    {"spend": 500, "amount": [{"amount": 20000}], "days": 90, "credits": []}
                ],
                "discontinued": False,
            }
        ],
    )
    def test_portfolio_category_assignments_survive_cache_hit(
        self, mock_fetch, db_session: Session, seed_user: User
    ):
        """Portfolio responses carry ``category_assignments`` (#177), and the
        combined blob must return identically on a cache hit — the second read
        must NOT double-nest the cached dict under ``cards`` (regression guard
        for the two-return-site cache trap)."""
        from app.services.recommendation_snapshot import RecommendationSnapshotService

        _seed_data(db_session, seed_user)  # seeds a Freedom Unlimited / CHASE card
        service = RecommendationSnapshotService(db_session)

        with patch.object(
            service.snapshot_repo, "upsert", wraps=service.snapshot_repo.upsert
        ) as spy_upsert:
            first = service.get_recommendations(seed_user.id, "portfolio_gap")
            second = service.get_recommendations(seed_user.id, "portfolio_gap")

        # Computed once; the second read is a cache hit (no recompute/upsert).
        assert spy_upsert.call_count == 1
        for result in (first, second):
            # ``cards`` stays a flat list — never {"cards": {"cards": [...]}}.
            assert isinstance(result["cards"], list)
            assert isinstance(result["category_assignments"], list)
            assert "spending_profile" in result
        # Seeded spend lands in 'shopping' → an assignment exists for it.
        assert "shopping" in {a["category"] for a in first["category_assignments"]}
        # Cold path and cache-hit path yield the identical payload.
        assert first["cards"] == second["cards"]
        assert first["category_assignments"] == second["category_assignments"]

    @patch("app.services.recommendation_snapshot._fetch_cards", return_value=MOCK_CARDS)
    def test_invalidate_forces_recompute(self, mock_fetch, db_session: Session, seed_user: User):
        from app.services.recommendation_snapshot import RecommendationSnapshotService

        _seed_data(db_session, seed_user)
        service = RecommendationSnapshotService(db_session)
        service.get_recommendations(seed_user.id, "next_card")
        service.invalidate(seed_user.id)
        service.get_recommendations(seed_user.id, "next_card")

        assert mock_fetch.call_count == 2
