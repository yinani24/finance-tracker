from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestCardAPI:
    def test_list_empty(self, client: TestClient, db_session: Session):
        response = client.get("/cards")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_card(self, client: TestClient, db_session: Session):
        payload = {"name": "Chase Sapphire Preferred", "network": "visa", "annual_fee": 95.00, "rewards_config_json": '{"dining": 3, "travel": 2, "other": 1}'}
        response = client.post("/cards", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Chase Sapphire Preferred"
        assert data["annual_fee"] == 95.00

    def test_create_no_fee_card(self, client: TestClient, db_session: Session):
        payload = {"name": "Chase Freedom Unlimited", "network": "visa", "rewards_config_json": '{"other": 1.5}'}
        response = client.post("/cards", json=payload)
        assert response.status_code == 201
        assert response.json()["annual_fee"] == 0.0

    def test_update_card(self, client: TestClient, db_session: Session):
        create_resp = client.post("/cards", json={"name": "Old Card", "network": "visa", "annual_fee": 0})
        card_id = create_resp.json()["id"]
        resp = client.patch(f"/cards/{card_id}", json={"annual_fee": 250.00})
        assert resp.status_code == 200
        assert resp.json()["annual_fee"] == 250.00

    def test_update_nonexistent(self, client: TestClient, db_session: Session):
        resp = client.patch("/cards/9999", json={"annual_fee": 100})
        assert resp.status_code == 404
