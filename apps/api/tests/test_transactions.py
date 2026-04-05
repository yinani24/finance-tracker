from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account


def _seed_account(db: Session) -> int:
    account = Account(user_id=1, name="Checking", type="checking", balance=0, currency="USD")
    db.add(account)
    db.commit()
    db.refresh(account)
    return account.id


class TestTransactionAPI:
    def test_list_empty(self, client: TestClient, db_session: Session):
        _seed_account(db_session)
        response = client.get("/transactions")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_transaction(self, client: TestClient, db_session: Session):
        acct_id = _seed_account(db_session)
        payload = {
            "account_id": acct_id,
            "occurred_on": "2026-03-15",
            "amount": -42.50,
            "merchant": "Whole Foods",
            "normalized_merchant": "whole foods",
            "category": "Food",
            "dedupe_hash": "hash1",
        }
        response = client.post("/transactions", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == -42.50
        assert data["merchant"] == "Whole Foods"

    def test_list_with_filters(self, client: TestClient, db_session: Session):
        acct_id = _seed_account(db_session)
        client.post("/transactions", json={"account_id": acct_id, "occurred_on": "2026-03-01", "amount": -10, "merchant": "A", "dedupe_hash": "h1", "category": "Food"})
        client.post("/transactions", json={"account_id": acct_id, "occurred_on": "2026-04-01", "amount": -20, "merchant": "B", "dedupe_hash": "h2", "category": "Transport"})
        resp = client.get("/transactions", params={"category": "Food"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["merchant"] == "A"

    def test_update_transaction(self, client: TestClient, db_session: Session):
        acct_id = _seed_account(db_session)
        create_resp = client.post("/transactions", json={"account_id": acct_id, "occurred_on": "2026-03-15", "amount": -42.50, "merchant": "Whole Foods", "dedupe_hash": "h1"})
        txn_id = create_resp.json()["id"]
        resp = client.patch(f"/transactions/{txn_id}", json={"category": "Groceries"})
        assert resp.status_code == 200
        assert resp.json()["category"] == "Groceries"

    def test_update_nonexistent(self, client: TestClient, db_session: Session):
        _seed_account(db_session)
        resp = client.patch("/transactions/9999", json={"category": "X"})
        assert resp.status_code == 404
