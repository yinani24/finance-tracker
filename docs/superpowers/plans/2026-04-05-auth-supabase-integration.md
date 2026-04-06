# Auth & Supabase Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Supabase JWT authentication so all API endpoints require a valid token, auto-create users on first login, and expose user profile/preferences endpoints.

**Architecture:** Supabase issues JWTs when users sign in. Our API validates those JWTs by checking the signature against the Supabase JWT secret. On each request, `get_current_user` decodes the token, finds-or-creates the user in our `users` table, and returns the user ID. All existing CRUD endpoints already use `Depends(get_current_user_id)` — we just replace the placeholder implementation. A `FT_AUTH_DISABLED=true` env var bypasses auth for local dev.

**Tech Stack:** PyJWT, FastAPI dependency injection, Supabase (external auth provider)

**Spec:** `docs/superpowers/specs/2026-04-01-full-app-migration-architecture.md` — Auth section, V1 API (`GET /me`, `PATCH /me/preferences`)

---

## File Structure

```
apps/api/
├── app/
│   ├── config.py              # Add supabase_jwt_secret, auth_disabled settings
│   ├── auth.py                # NEW: decode_jwt(), get_current_user() dependency
│   ├── api/
│   │   ├── deps.py            # Replace placeholder with real auth import
│   │   ├── me.py              # NEW: GET /me, PATCH /me/preferences
│   │   └── router.py          # Add me_router
│   ├── schemas/
│   │   └── user.py            # NEW: UserRead, PreferenceRead, PreferenceUpdate
│   └── repositories/
│       └── user.py            # NEW: UserRepository (find_or_create, get prefs, update prefs)
└── tests/
    ├── conftest.py            # Add auth override fixture
    ├── test_auth.py           # NEW: JWT decode, user resolution, auth bypass
    └── test_me.py             # NEW: /me and /me/preferences endpoints
```

---

## Task 1: Add PyJWT Dependency + Auth Config

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/app/config.py`

- [ ] **Step 1: Add PyJWT to dependencies**

In `apps/api/pyproject.toml`, add `"pyjwt[crypto]>=2.8.0"` to the `dependencies` list.

- [ ] **Step 2: Add auth settings to config**

Replace `apps/api/app/config.py` with:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://localhost:5432/finance_tracker"
    test_database_url: str = "postgresql://localhost:5432/finance_tracker_test"
    debug: bool = False
    supabase_jwt_secret: str = ""
    auth_disabled: bool = False

    model_config = {"env_prefix": "FT_"}


settings = Settings()
```

- [ ] **Step 3: Install the new dependency**

```bash
cd apps/api && source .venv/bin/activate && pip install -e ".[dev]"
```

- [ ] **Step 4: Verify existing tests still pass**

```bash
cd apps/api && pytest tests/ -v
```

Expected: 28 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/pyproject.toml apps/api/app/config.py
git commit -m "feat(api): add PyJWT dependency and auth config settings"
```

---

## Task 2: JWT Decoding + User Resolution

**Files:**
- Create: `apps/api/app/auth.py`
- Create: `apps/api/app/repositories/user.py`
- Create: `apps/api/app/schemas/user.py`
- Create: `apps/api/tests/test_auth.py`

- [ ] **Step 1: Write the failing tests for auth**

Create `apps/api/tests/test_auth.py`:

```python
import jwt
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import decode_supabase_jwt, get_current_user
from app.database import get_db
from app.models.user import User

TEST_JWT_SECRET = "test-secret-that-is-long-enough-for-hs256-signing-key"


def _make_token(sub: str, email: str, secret: str = TEST_JWT_SECRET) -> str:
    return jwt.encode({"sub": sub, "email": email}, secret, algorithm="HS256")


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
        token = _make_token("user-123", "a@b.com", secret="wrong-secret-padding-for-length")
        payload = decode_supabase_jwt(token, TEST_JWT_SECRET)
        assert payload is None


class TestGetCurrentUser:
    def test_creates_user_on_first_login(self, db_session: Session):
        token = _make_token("supabase-id-1", "new@example.com")

        app = FastAPI()

        @app.get("/test")
        def endpoint(
            user_id: int = Depends(get_current_user),
            db: Session = Depends(get_db),
        ):
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
        def endpoint(
            user_id: int = Depends(get_current_user),
            db: Session = Depends(get_db),
        ):
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
        def endpoint(
            user_id: int = Depends(get_current_user),
            db: Session = Depends(get_db),
        ):
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/api && pytest tests/test_auth.py -v
```

Expected: FAIL — `app.auth` does not exist.

- [ ] **Step 3: Write app/schemas/user.py**

Create `apps/api/app/schemas/user.py`:

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserRead(BaseModel):
    id: int
    email: str
    auth_provider: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PreferenceRead(BaseModel):
    theme: str
    timezone: str
    currency: str

    model_config = {"from_attributes": True}


class PreferenceUpdate(BaseModel):
    theme: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
```

- [ ] **Step 4: Write app/repositories/user.py**

Create `apps/api/app/repositories/user.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, UserPreference
from app.schemas.user import PreferenceUpdate


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_subject(self, auth_subject: str) -> User | None:
        stmt = select(User).where(User.auth_subject == auth_subject)
        return self.db.scalars(stmt).first()

    def find_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def create_from_token(self, auth_subject: str, email: str) -> User:
        user = User(auth_provider="supabase", auth_subject=auth_subject, email=email)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_preferences(self, user_id: int) -> UserPreference:
        pref = self.db.get(UserPreference, user_id)
        if not pref:
            pref = UserPreference(user_id=user_id)
            self.db.add(pref)
            self.db.commit()
            self.db.refresh(pref)
        return pref

    def update_preferences(self, user_id: int, data: PreferenceUpdate) -> UserPreference:
        pref = self.get_preferences(user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(pref, field, value)
        self.db.commit()
        self.db.refresh(pref)
        return pref
```

- [ ] **Step 5: Write app/auth.py**

Create `apps/api/app/auth.py`:

```python
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.repositories.user import UserRepository


def decode_supabase_jwt(token: str, secret: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    except jwt.PyJWTError:
        return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> int:
    if settings.auth_disabled:
        return 1

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")

    token = auth_header.removeprefix("Bearer ")
    payload = decode_supabase_jwt(token, settings.supabase_jwt_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    sub = payload.get("sub")
    email = payload.get("email", "")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    repo = UserRepository(db)
    user = repo.find_by_subject(sub)
    if not user:
        user = repo.create_from_token(sub, email)

    return user.id
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd apps/api && pytest tests/test_auth.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/auth.py apps/api/app/schemas/user.py apps/api/app/repositories/user.py apps/api/tests/test_auth.py
git commit -m "feat(api): add Supabase JWT auth with user auto-creation"
```

---

## Task 3: Wire Auth Into Existing Endpoints

**Files:**
- Modify: `apps/api/app/api/deps.py`
- Modify: `apps/api/tests/conftest.py`

- [ ] **Step 1: Replace the placeholder dep with real auth**

Replace `apps/api/app/api/deps.py` with:

```python
from app.auth import get_current_user

get_current_user_id = get_current_user
```

- [ ] **Step 2: Update conftest.py to override auth for tests**

Replace `apps/api/tests/conftest.py` with:

```python
from collections.abc import Generator

import app.models  # noqa: F401
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth import get_current_user
from app.config import settings
from app.database import Base, get_db
from app.main import create_app
from app.models.user import User

TEST_DATABASE_URL = settings.test_database_url


@pytest.fixture(autouse=True)
def _setup_db():
    """Create all tables before tests, drop after."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_engine():
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=db_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def seed_user(db_session) -> User:
    """Create the default test user (id=1) used by auth override."""
    user = User(id=1, auth_provider="test", auth_subject="test-1", email="test@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def client(db_session, seed_user) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    def override_auth():
        return seed_user.id

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_auth
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 3: Remove `_seed_user` calls from existing test files**

The `client` fixture now auto-seeds the test user. Update all 4 CRUD test files to remove their manual `_seed_user` calls and helpers:

In `tests/test_accounts.py`, remove the `_seed_user` function and all `_seed_user(db_session)` calls from each test method.

In `tests/test_transactions.py`, change `_seed` to only create an account (user is already seeded):

```python
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account


def _seed_account(db: Session) -> int:
    account = Account(user_id=1, name="Checking", type="checking", balance=0, currency="USD")
    db.add(account)
    db.commit()
    db.refresh(account)
    return account.id
```

Then update each test method to call `_seed_account(db_session)` instead of `_seed(db_session)`.

In `tests/test_goals.py`, remove the `_seed_user` function and all `_seed_user(db_session)` calls.

In `tests/test_cards.py`, remove the `_seed_user` function and all `_seed_user(db_session)` calls.

- [ ] **Step 4: Run the full test suite**

```bash
cd apps/api && pytest tests/ -v
```

Expected: all 28 existing tests + 7 auth tests = 35 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/api/deps.py apps/api/tests/
git commit -m "feat(api): wire Supabase auth into all endpoints"
```

---

## Task 4: User Profile & Preferences Endpoints

**Files:**
- Create: `apps/api/app/api/me.py`
- Modify: `apps/api/app/api/router.py`
- Create: `apps/api/tests/test_me.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_me.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


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
        response = client.patch("/me/preferences", json={"theme": "dark", "timezone": "America/New_York"})
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/api && pytest tests/test_me.py -v
```

Expected: FAIL — `/me` route not found.

- [ ] **Step 3: Write app/api/me.py**

Create `apps/api/app/api/me.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.repositories.user import UserRepository
from app.schemas.user import PreferenceRead, PreferenceUpdate, UserRead

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserRead)
def get_me(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> UserRead:
    repo = UserRepository(db)
    return repo.find_by_id(user_id)


@router.get("/me/preferences", response_model=PreferenceRead)
def get_preferences(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> PreferenceRead:
    repo = UserRepository(db)
    return repo.get_preferences(user_id)


@router.patch("/me/preferences", response_model=PreferenceRead)
def update_preferences(
    data: PreferenceUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> PreferenceRead:
    repo = UserRepository(db)
    return repo.update_preferences(user_id, data)
```

- [ ] **Step 4: Update router.py**

Replace `apps/api/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api.accounts import router as accounts_router
from app.api.cards import router as cards_router
from app.api.goals import router as goals_router
from app.api.me import router as me_router
from app.api.transactions import router as transactions_router

api_router = APIRouter()
api_router.include_router(me_router)
api_router.include_router(accounts_router)
api_router.include_router(transactions_router)
api_router.include_router(goals_router)
api_router.include_router(cards_router)
```

- [ ] **Step 5: Run the full test suite**

```bash
cd apps/api && pytest tests/ -v
```

Expected: 35 + 4 = 39 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/api/me.py apps/api/app/api/router.py apps/api/tests/test_me.py
git commit -m "feat(api): add GET /me and PATCH /me/preferences endpoints"
```

---

## Task 5: Dev Seed Command

**Files:**
- Modify: `apps/api/app/main.py`

For local dev with `FT_AUTH_DISABLED=true`, we need user id=1 to exist. Add a startup event that creates the dev user if auth is disabled and the user doesn't exist.

- [ ] **Step 1: Update app/main.py**

Replace `apps/api/app/main.py` with:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.config import settings
from app.database import SessionLocal
from app.models.user import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auth_disabled:
        db = SessionLocal()
        try:
            if not db.get(User, 1):
                db.add(User(id=1, auth_provider="dev", auth_subject="dev-user", email="dev@local"))
                db.commit()
        finally:
            db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Finance Tracker API", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)

    return app
```

- [ ] **Step 2: Run the full test suite**

```bash
cd apps/api && pytest tests/ -v
```

Expected: 39 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/main.py
git commit -m "feat(api): auto-seed dev user when auth is disabled"
```
