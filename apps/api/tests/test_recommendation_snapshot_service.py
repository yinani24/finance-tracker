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
        service.get_recommendations(seed_user.id, "next_card")
        service.get_recommendations(seed_user.id, "next_card")

        assert mock_fetch.call_count == 1

    @patch("app.services.recommendation_snapshot._fetch_cards", return_value=MOCK_CARDS)
    def test_invalidate_forces_recompute(self, mock_fetch, db_session: Session, seed_user: User):
        from app.services.recommendation_snapshot import RecommendationSnapshotService

        _seed_data(db_session, seed_user)
        service = RecommendationSnapshotService(db_session)
        service.get_recommendations(seed_user.id, "next_card")
        service.invalidate(seed_user.id)
        service.get_recommendations(seed_user.id, "next_card")

        assert mock_fetch.call_count == 2
