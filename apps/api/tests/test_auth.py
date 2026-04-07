from __future__ import annotations

import time

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import MAX_TOKEN_AGE_SECONDS, decode_supabase_jwt, get_current_user
from app.database import get_db
from app.models.user import User

TEST_JWT_SECRET = "test-secret-that-is-long-enough-for-hs256-signing-key"


def _make_token(
    sub: str,
    email: str,
    secret: str = TEST_JWT_SECRET,
    iat: float | None = None,
    exp: float | None = None,
) -> str:
    now = time.time()
    payload = {
        "sub": sub,
        "email": email,
        "iat": iat if iat is not None else now,
        "exp": exp if exp is not None else now + MAX_TOKEN_AGE_SECONDS,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


class TestDecodeJWT:
    def test_valid_token(self):
        token = _make_token("user-123", "a@b.com")
        payload = decode_supabase_jwt(token, TEST_JWT_SECRET)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "a@b.com"

    def test_invalid_token(self):
        payload = decode_supabase_jwt("garbage", TEST_JWT_SECRET)
        assert payload is None

    def test_wrong_secret(self):
        token = _make_token("user-123", "a@b.com", secret="wrong-secret-padding-for-length-xxxxx")
        payload = decode_supabase_jwt(token, TEST_JWT_SECRET)
        assert payload is None

    def test_expired_token(self):
        now = time.time()
        token = _make_token("user-123", "a@b.com", iat=now - 7200, exp=now - 3600)
        payload = decode_supabase_jwt(token, TEST_JWT_SECRET)
        assert payload is None

    def test_token_older_than_max_age(self):
        now = time.time()
        # Token issued 2 hours ago but exp set far in the future — should still be rejected
        token = _make_token("user-123", "a@b.com", iat=now - 7200, exp=now + 3600)
        payload = decode_supabase_jwt(token, TEST_JWT_SECRET)
        assert payload is None

    def test_token_missing_iat_rejected(self):
        token = jwt.encode(
            {"sub": "user-123", "email": "a@b.com", "exp": time.time() + 3600},
            TEST_JWT_SECRET,
            algorithm="HS256",
        )
        payload = decode_supabase_jwt(token, TEST_JWT_SECRET)
        assert payload is None

    def test_token_missing_exp_rejected(self):
        token = jwt.encode(
            {"sub": "user-123", "email": "a@b.com", "iat": time.time()},
            TEST_JWT_SECRET,
            algorithm="HS256",
        )
        payload = decode_supabase_jwt(token, TEST_JWT_SECRET)
        assert payload is None


class TestGetCurrentUser:
    def test_creates_user_on_first_login(self, db_session: Session):
        token = _make_token("supabase-id-1", "new@example.com")

        app = FastAPI()

        @app.get("/test")
        def endpoint(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
            return {"user_id": user_id}

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.auth.settings.supabase_jwt_secret", TEST_JWT_SECRET)
            mp.setattr("app.auth.settings.auth_disabled", False)
            response = client.get("/test")

        assert response.status_code == 200
        user = db_session.query(User).filter_by(auth_subject="supabase-id-1").first()
        assert user is not None
        assert user.email == "new@example.com"
        assert response.json()["user_id"] == user.id

    def test_returns_existing_user(self, db_session: Session):
        existing = User(auth_provider="supabase", auth_subject="existing-id", email="old@example.com")
        db_session.add(existing)
        db_session.commit()
        db_session.refresh(existing)

        token = _make_token("existing-id", "old@example.com")

        app = FastAPI()

        @app.get("/test")
        def endpoint(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
            return {"user_id": user_id}

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.auth.settings.supabase_jwt_secret", TEST_JWT_SECRET)
            mp.setattr("app.auth.settings.auth_disabled", False)
            response = client.get("/test")

        assert response.status_code == 200
        assert response.json()["user_id"] == existing.id

    def test_missing_token_returns_401(self, db_session: Session):
        app = FastAPI()

        @app.get("/test")
        def endpoint(user_id: int = Depends(get_current_user)):
            return {"user_id": user_id}

        client = TestClient(app)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.auth.settings.supabase_jwt_secret", TEST_JWT_SECRET)
            mp.setattr("app.auth.settings.auth_disabled", False)
            response = client.get("/test")

        assert response.status_code == 401

    def test_auth_disabled_returns_default_user(self, db_session: Session):
        default_user = User(id=1, auth_provider="dev", auth_subject="dev-user", email="dev@local")
        db_session.add(default_user)
        db_session.commit()

        app = FastAPI()

        @app.get("/test")
        def endpoint(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
            return {"user_id": user_id}

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.auth.settings.supabase_jwt_secret", TEST_JWT_SECRET)
            mp.setattr("app.auth.settings.auth_disabled", True)
            response = client.get("/test")

        assert response.status_code == 200
        assert response.json()["user_id"] == 1
