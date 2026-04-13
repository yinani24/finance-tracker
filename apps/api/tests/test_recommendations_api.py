from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
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


def _seed(db_session: Session, user: User) -> None:
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


class TestRecommendationsAPI:
    @patch("app.services.recommendation_snapshot._fetch_cards", return_value=MOCK_CARDS)
    def test_get_next_card(self, mock_fetch, client: TestClient, db_session: Session, seed_user: User):
        _seed(db_session, seed_user)
        resp = client.get("/recommendations/next-card")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data
        assert "spending_profile" in data

    @patch("app.services.recommendation_snapshot._fetch_cards", return_value=MOCK_CARDS)
    def test_get_portfolio(self, mock_fetch, client: TestClient, db_session: Session, seed_user: User):
        _seed(db_session, seed_user)
        resp = client.get("/recommendations/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "cards" in data
        assert "spending_profile" in data

    @patch("app.services.recommendation_snapshot._fetch_cards", return_value=MOCK_CARDS)
    def test_get_spending_profile(self, mock_fetch, client: TestClient, db_session: Session, seed_user: User):
        _seed(db_session, seed_user)
        resp = client.get("/recommendations/spending-profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "avg_monthly_spend" in data
        assert "categories" in data

    @patch("app.services.recommendation_snapshot._fetch_cards", return_value=MOCK_CARDS)
    def test_refresh(self, mock_fetch, client: TestClient, db_session: Session, seed_user: User):
        _seed(db_session, seed_user)
        resp = client.post("/recommendations/refresh")
        assert resp.status_code == 200
        assert resp.json()["status"] == "refreshed"
