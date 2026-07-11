from fastapi.testclient import TestClient


class TestMeEndpoint:
    def test_get_me(self, client: TestClient):
        response = client.get("/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "id" in data
        assert "created_at" in data

    def test_get_preferences_defaults(self, client: TestClient):
        response = client.get("/me/preferences")
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "light"
        assert data["timezone"] == "UTC"
        assert data["currency"] == "USD"

    def test_update_preferences(self, client: TestClient):
        response = client.patch(
            "/me/preferences", json={"theme": "dark", "timezone": "America/New_York"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "dark"
        assert data["timezone"] == "America/New_York"
        assert data["currency"] == "USD"

    def test_update_preferences_partial(self, client: TestClient):
        client.patch("/me/preferences", json={"theme": "dark"})
        response = client.patch("/me/preferences", json={"currency": "EUR"})
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "dark"
        assert data["currency"] == "EUR"
