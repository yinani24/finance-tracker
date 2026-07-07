from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestGoalAPI:
    def test_list_empty(self, client: TestClient, db_session: Session):
        response = client.get("/goals")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_goal(self, client: TestClient, db_session: Session):
        payload = {"name": "Emergency Fund", "goal_type": "savings", "target_amount": 10000.00, "current_amount": 2500.00, "is_monthly": False}
        response = client.post("/goals", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Emergency Fund"
        assert data["target_amount"] == 10000.00

    def test_create_monthly_goal(self, client: TestClient, db_session: Session):
        payload = {"name": "Food Budget", "goal_type": "monthly", "target_amount": 500.00, "is_monthly": True}
        response = client.post("/goals", json=payload)
        assert response.status_code == 201
        assert response.json()["is_monthly"] is True

    def test_update_goal(self, client: TestClient, db_session: Session):
        create_resp = client.post("/goals", json={"name": "Fund", "goal_type": "savings", "target_amount": 5000, "is_monthly": False})
        goal_id = create_resp.json()["id"]
        resp = client.patch(f"/goals/{goal_id}", json={"current_amount": 3000.00})
        assert resp.status_code == 200
        assert resp.json()["current_amount"] == 3000.00

    def test_update_nonexistent(self, client: TestClient, db_session: Session):
        resp = client.patch("/goals/9999", json={"current_amount": 100})
        assert resp.status_code == 404
