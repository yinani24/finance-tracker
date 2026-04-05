from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestAccountAPI:
    def test_list_accounts_empty(self, client: TestClient, db_session: Session):
        response = client.get("/accounts")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_account(self, client: TestClient, db_session: Session):
        payload = {
            "name": "Chase Checking",
            "type": "checking",
            "institution_name": "Chase",
            "balance": 1500.00,
            "currency": "USD",
        }
        response = client.post("/accounts", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Chase Checking"
        assert data["balance"] == 1500.00
        assert "id" in data

    def test_list_accounts_after_create(self, client: TestClient, db_session: Session):
        client.post("/accounts", json={"name": "Acct1", "type": "checking", "balance": 100, "currency": "USD"})
        client.post("/accounts", json={"name": "Acct2", "type": "savings", "balance": 200, "currency": "USD"})
        response = client.get("/accounts")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_update_account(self, client: TestClient, db_session: Session):
        create_resp = client.post("/accounts", json={"name": "Old Name", "type": "checking", "balance": 0, "currency": "USD"})
        account_id = create_resp.json()["id"]
        response = client.patch(f"/accounts/{account_id}", json={"balance": 999.99})
        assert response.status_code == 200
        assert response.json()["balance"] == 999.99
        assert response.json()["name"] == "Old Name"

    def test_update_nonexistent_account(self, client: TestClient, db_session: Session):
        response = client.patch("/accounts/9999", json={"balance": 100})
        assert response.status_code == 404
