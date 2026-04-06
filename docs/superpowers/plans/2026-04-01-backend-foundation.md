# Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a FastAPI backend with PostgreSQL-backed models, Alembic migrations, and CRUD APIs for accounts, transactions, goals, and cards — replacing flat-file storage with a proper relational data layer.

**Architecture:** Modular monolith under `apps/api/`. SQLAlchemy 2.x models with mapped_column syntax, Pydantic v2 schemas, repository pattern for data access, FastAPI dependency injection for sessions. A placeholder auth dependency returns a hardcoded user ID (replaced by real auth in Plan 2).

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, pydantic-settings, pytest, httpx, SQLite (tests), PostgreSQL (prod)

**Spec:** `docs/superpowers/specs/2026-04-01-full-app-migration-architecture.md`

---

## File Structure

```
apps/api/
├── pyproject.toml
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory (create_app)
│   ├── config.py             # Settings via pydantic-settings
│   ├── database.py           # Engine, session factory, Base, get_db
│   ├── models/
│   │   ├── __init__.py       # Re-exports all models
│   │   ├── user.py           # User, UserPreference
│   │   ├── account.py        # Account
│   │   ├── transaction.py    # Transaction
│   │   ├── goal.py           # Goal
│   │   ├── card.py           # Card
│   │   └── import_record.py  # Import, ImportFile
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── account.py        # AccountCreate, AccountUpdate, AccountRead
│   │   ├── transaction.py    # TransactionCreate, TransactionUpdate, TransactionRead
│   │   ├── goal.py           # GoalCreate, GoalUpdate, GoalRead
│   │   └── card.py           # CardCreate, CardUpdate, CardRead
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── account.py        # AccountRepository
│   │   ├── transaction.py    # TransactionRepository
│   │   ├── goal.py           # GoalRepository
│   │   └── card.py           # CardRepository
│   └── api/
│       ├── __init__.py
│       ├── deps.py           # get_current_user_id (placeholder), get_db re-export
│       ├── router.py         # Top-level router combining all sub-routers
│       ├── accounts.py       # GET/POST/PATCH /accounts
│       ├── transactions.py   # GET/POST/PATCH /transactions
│       ├── goals.py          # GET/POST/PATCH /goals
│       └── cards.py          # GET/POST/PATCH /cards
└── tests/
    ├── __init__.py
    ├── conftest.py           # db_session, client, seed_user fixtures
    ├── test_health.py        # App factory + health check
    ├── test_models.py        # Model creation + relationships
    ├── test_accounts.py      # Account repo + API
    ├── test_transactions.py  # Transaction repo + API
    ├── test_goals.py         # Goal repo + API
    └── test_cards.py         # Card repo + API
```

---

## Task 1: Project Scaffold + FastAPI App

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/app/__init__.py`
- Create: `apps/api/app/main.py`
- Create: `apps/api/app/config.py`
- Create: `apps/api/tests/__init__.py`
- Create: `apps/api/tests/test_health.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p apps/api/app/models apps/api/app/schemas apps/api/app/repositories apps/api/app/api apps/api/tests apps/api/alembic/versions
touch apps/api/app/__init__.py apps/api/app/models/__init__.py apps/api/app/schemas/__init__.py apps/api/app/repositories/__init__.py apps/api/app/api/__init__.py apps/api/tests/__init__.py
```

- [ ] **Step 2: Write pyproject.toml**

Create `apps/api/pyproject.toml`:

```toml
[project]
name = "finance-tracker-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.14.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "psycopg2-binary>=2.9.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.27.0",
    "ruff>=0.11.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.ruff.lint.isort]
known-first-party = ["app"]
```

- [ ] **Step 3: Write config.py**

Create `apps/api/app/config.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./finance.db"
    debug: bool = False

    model_config = {"env_prefix": "FT_"}


settings = Settings()
```

- [ ] **Step 4: Write the failing test for the app factory and health check**

Create `apps/api/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_check():
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it fails**

```bash
cd apps/api && pip install -e ".[dev]" && pytest tests/test_health.py -v
```

Expected: FAIL — `app.main` does not exist yet or `create_app` is not defined.

- [ ] **Step 6: Write app/main.py**

Create `apps/api/app/main.py`:

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Finance Tracker API", version="0.1.0")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

- [ ] **Step 7: Run test to verify it passes**

```bash
cd apps/api && pytest tests/test_health.py -v
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add apps/api/pyproject.toml apps/api/app/__init__.py apps/api/app/main.py apps/api/app/config.py apps/api/app/models/__init__.py apps/api/app/schemas/__init__.py apps/api/app/repositories/__init__.py apps/api/app/api/__init__.py apps/api/tests/__init__.py apps/api/tests/test_health.py
git commit -m "feat(api): scaffold FastAPI app with health check"
```

---

## Task 2: Database Layer

**Files:**
- Create: `apps/api/app/database.py`
- Create: `apps/api/tests/conftest.py`

- [ ] **Step 1: Write app/database.py**

Create `apps/api/app/database.py`:

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Write tests/conftest.py with shared fixtures**

Create `apps/api/tests/conftest.py`:

```python
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import create_app

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture()
def db_engine():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=db_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 3: Update test_health.py to use the client fixture**

Replace `apps/api/tests/test_health.py` with:

```python
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 4: Run tests to verify everything passes**

```bash
cd apps/api && pytest tests/ -v
```

Expected: PASS — health check uses the client fixture with in-memory SQLite.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/database.py apps/api/tests/conftest.py apps/api/tests/test_health.py
git commit -m "feat(api): add database layer with SQLAlchemy and test fixtures"
```

---

## Task 3: SQLAlchemy Models

**Files:**
- Create: `apps/api/app/models/user.py`
- Create: `apps/api/app/models/account.py`
- Create: `apps/api/app/models/transaction.py`
- Create: `apps/api/app/models/goal.py`
- Create: `apps/api/app/models/card.py`
- Create: `apps/api/app/models/import_record.py`
- Modify: `apps/api/app/models/__init__.py`
- Create: `apps/api/tests/test_models.py`

- [ ] **Step 1: Write the failing model tests**

Create `apps/api/tests/test_models.py`:

```python
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.user import User, UserPreference
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.goal import Goal
from app.models.card import Card
from app.models.import_record import Import, ImportFile


def _make_user(db: Session) -> User:
    user = User(auth_provider="test", auth_subject="test-user-1", email="test@example.com")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_user(db_session: Session):
    user = _make_user(db_session)
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.created_at is not None


def test_create_user_preference(db_session: Session):
    user = _make_user(db_session)
    pref = UserPreference(user_id=user.id, theme="dark", timezone="America/New_York", currency="USD")
    db_session.add(pref)
    db_session.commit()
    db_session.refresh(pref)
    assert pref.theme == "dark"
    assert pref.user_id == user.id


def test_create_account(db_session: Session):
    user = _make_user(db_session)
    account = Account(
        user_id=user.id,
        name="Chase Checking",
        type="checking",
        institution_name="Chase",
        balance=1500.00,
        currency="USD",
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    assert account.id is not None
    assert account.name == "Chase Checking"
    assert account.balance == 1500.00


def test_create_transaction(db_session: Session):
    user = _make_user(db_session)
    account = Account(
        user_id=user.id, name="Chase Checking", type="checking", balance=0, currency="USD"
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    txn = Transaction(
        user_id=user.id,
        account_id=account.id,
        occurred_on=date(2026, 3, 15),
        amount=-42.50,
        merchant="Whole Foods",
        normalized_merchant="whole foods",
        category="Food",
        dedupe_hash="abc123",
    )
    db_session.add(txn)
    db_session.commit()
    db_session.refresh(txn)
    assert txn.id is not None
    assert txn.amount == -42.50
    assert txn.is_income is False


def test_create_goal(db_session: Session):
    user = _make_user(db_session)
    goal = Goal(
        user_id=user.id,
        name="Emergency Fund",
        goal_type="savings",
        target_amount=10000.00,
        current_amount=2500.00,
        is_monthly=False,
    )
    db_session.add(goal)
    db_session.commit()
    db_session.refresh(goal)
    assert goal.id is not None
    assert goal.target_amount == 10000.00


def test_create_card(db_session: Session):
    user = _make_user(db_session)
    card = Card(
        user_id=user.id,
        name="Chase Sapphire Preferred",
        network="visa",
        annual_fee=95,
        rewards_config_json='{"dining": 3, "travel": 2, "other": 1}',
    )
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    assert card.id is not None
    assert card.annual_fee == 95


def test_create_import_with_file(db_session: Session):
    user = _make_user(db_session)
    account = Account(
        user_id=user.id, name="Chase Checking", type="checking", balance=0, currency="USD"
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    imp = Import(
        user_id=user.id,
        account_id=account.id,
        provider="chase",
        import_type="csv",
        status="queued",
    )
    db_session.add(imp)
    db_session.commit()
    db_session.refresh(imp)

    imp_file = ImportFile(
        import_id=imp.id,
        storage_key="uploads/abc123.csv",
        original_filename="statement.csv",
        mime_type="text/csv",
        size_bytes=4096,
    )
    db_session.add(imp_file)
    db_session.commit()
    db_session.refresh(imp_file)
    assert imp_file.import_id == imp.id
    assert imp.status == "queued"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/api && pytest tests/test_models.py -v
```

Expected: FAIL — model modules don't exist yet.

- [ ] **Step 3: Write app/models/user.py**

Create `apps/api/app/models/user.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    auth_provider: Mapped[str] = mapped_column(String(50))
    auth_subject: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    theme: Mapped[str] = mapped_column(String(20), default="light")
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Write app/models/account.py**

Create `apps/api/app/models/account.py`:

```python
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20))
    institution_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    external_account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 5: Write app/models/transaction.py**

Create `apps/api/app/models/transaction.py`:

```python
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    occurred_on: Mapped[date] = mapped_column(Date)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    merchant: Mapped[str] = mapped_column(String(255))
    normalized_merchant: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_income: Mapped[bool] = mapped_column(Boolean, default=False)
    is_savings: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_import_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("imports.id"), nullable=True
    )
    dedupe_hash: Mapped[str] = mapped_column(String(64), index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 6: Write app/models/goal.py**

Create `apps/api/app/models/goal.py`:

```python
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    goal_type: Mapped[str] = mapped_column(String(20))
    target_amount: Mapped[float] = mapped_column(Float)
    current_amount: Mapped[float] = mapped_column(Float, default=0.0)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_monthly: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 7: Write app/models/card.py**

Create `apps/api/app/models/card.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    network: Mapped[str] = mapped_column(String(20))
    annual_fee: Mapped[float] = mapped_column(Float, default=0.0)
    rewards_config_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 8: Write app/models/import_record.py**

Create `apps/api/app/models/import_record.py`:

```python
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    import_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ImportFile(Base):
    __tablename__ = "import_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("imports.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 9: Write app/models/__init__.py to re-export all models**

Replace `apps/api/app/models/__init__.py` with:

```python
from app.models.user import User, UserPreference
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.goal import Goal
from app.models.card import Card
from app.models.import_record import Import, ImportFile

__all__ = [
    "User",
    "UserPreference",
    "Account",
    "Transaction",
    "Goal",
    "Card",
    "Import",
    "ImportFile",
]
```

- [ ] **Step 10: Update conftest.py to import all models so Base.metadata knows about them**

Add this import at the top of `apps/api/tests/conftest.py`, after the existing imports:

```python
import app.models  # noqa: F401 — ensures all models are registered with Base.metadata
```

- [ ] **Step 11: Run model tests to verify they pass**

```bash
cd apps/api && pytest tests/test_models.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 12: Commit**

```bash
git add apps/api/app/models/ apps/api/tests/test_models.py apps/api/tests/conftest.py
git commit -m "feat(api): add SQLAlchemy models for all domain entities"
```

---

## Task 4: Alembic Setup

**Files:**
- Create: `apps/api/alembic.ini`
- Create: `apps/api/alembic/env.py`
- Create: `apps/api/alembic/versions/001_initial_schema.py`

- [ ] **Step 1: Create alembic.ini**

Create `apps/api/alembic.ini`:

```ini
[alembic]
script_location = alembic
sqlalchemy.url = sqlite:///./finance.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Create alembic/env.py**

Create `apps/api/alembic/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.database import Base
import app.models  # noqa: F401 — register all models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Generate initial migration**

```bash
cd apps/api && alembic revision --autogenerate -m "initial schema" --rev-id 001
```

Verify the generated file in `apps/api/alembic/versions/001_initial_schema.py` creates all 8 tables: users, user_preferences, accounts, transactions, goals, cards, imports, import_files.

- [ ] **Step 4: Test the migration runs cleanly**

```bash
cd apps/api && rm -f finance.db && alembic upgrade head && alembic downgrade base && rm -f finance.db
```

Expected: no errors on upgrade or downgrade.

- [ ] **Step 5: Commit**

```bash
git add apps/api/alembic.ini apps/api/alembic/
git commit -m "feat(api): add Alembic setup with initial schema migration"
```

---

## Task 5: Accounts CRUD

**Files:**
- Create: `apps/api/app/api/deps.py`
- Create: `apps/api/app/schemas/account.py`
- Create: `apps/api/app/repositories/account.py`
- Create: `apps/api/app/api/accounts.py`
- Create: `apps/api/app/api/router.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_accounts.py`

- [ ] **Step 1: Write app/api/deps.py (shared dependencies)**

Create `apps/api/app/api/deps.py`:

```python
def get_current_user_id() -> int:
    """Placeholder — returns a hardcoded user ID. Replaced by real auth in Plan 2."""
    return 1
```

- [ ] **Step 2: Write the failing test for account CRUD**

Create `apps/api/tests/test_accounts.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def _seed_user(db: Session) -> User:
    user = User(id=1, auth_provider="test", auth_subject="test-1", email="test@example.com")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestAccountAPI:
    def test_list_accounts_empty(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        response = client.get("/accounts")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_account(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
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
        _seed_user(db_session)
        client.post(
            "/accounts",
            json={"name": "Acct1", "type": "checking", "balance": 100, "currency": "USD"},
        )
        client.post(
            "/accounts",
            json={"name": "Acct2", "type": "savings", "balance": 200, "currency": "USD"},
        )
        response = client.get("/accounts")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_update_account(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        create_resp = client.post(
            "/accounts",
            json={"name": "Old Name", "type": "checking", "balance": 0, "currency": "USD"},
        )
        account_id = create_resp.json()["id"]
        response = client.patch(f"/accounts/{account_id}", json={"balance": 999.99})
        assert response.status_code == 200
        assert response.json()["balance"] == 999.99
        assert response.json()["name"] == "Old Name"

    def test_update_nonexistent_account(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        response = client.patch("/accounts/9999", json={"balance": 100})
        assert response.status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd apps/api && pytest tests/test_accounts.py -v
```

Expected: FAIL — routes don't exist yet.

- [ ] **Step 4: Write app/schemas/account.py**

Create `apps/api/app/schemas/account.py`:

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AccountCreate(BaseModel):
    name: str
    type: str
    institution_name: Optional[str] = None
    external_account_id: Optional[str] = None
    balance: float = 0.0
    currency: str = "USD"


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    institution_name: Optional[str] = None
    external_account_id: Optional[str] = None
    balance: Optional[float] = None
    currency: Optional[str] = None


class AccountRead(BaseModel):
    id: int
    user_id: int
    name: str
    type: str
    institution_name: Optional[str]
    external_account_id: Optional[str]
    balance: float
    currency: str
    last_synced_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Write app/repositories/account.py**

Create `apps/api/app/repositories/account.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.schemas.account import AccountCreate, AccountUpdate


class AccountRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(self, user_id: int) -> list[Account]:
        stmt = select(Account).where(Account.user_id == user_id)
        return list(self.db.scalars(stmt).all())

    def get(self, account_id: int, user_id: int) -> Account | None:
        stmt = select(Account).where(Account.id == account_id, Account.user_id == user_id)
        return self.db.scalars(stmt).first()

    def create(self, user_id: int, data: AccountCreate) -> Account:
        account = Account(user_id=user_id, **data.model_dump())
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def update(self, account: Account, data: AccountUpdate) -> Account:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(account, field, value)
        self.db.commit()
        self.db.refresh(account)
        return account
```

- [ ] **Step 6: Write app/api/accounts.py**

Create `apps/api/app/api/accounts.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.repositories.account import AccountRepository
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountRead])
def list_accounts(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[AccountRead]:
    repo = AccountRepository(db)
    return repo.list_by_user(user_id)


@router.post("", response_model=AccountRead, status_code=201)
def create_account(
    data: AccountCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> AccountRead:
    repo = AccountRepository(db)
    return repo.create(user_id, data)


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    account_id: int,
    data: AccountUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> AccountRead:
    repo = AccountRepository(db)
    account = repo.get(account_id, user_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return repo.update(account, data)
```

- [ ] **Step 7: Write app/api/router.py and wire it into the app**

Create `apps/api/app/api/router.py`:

```python
from fastapi import APIRouter

from app.api.accounts import router as accounts_router

api_router = APIRouter()
api_router.include_router(accounts_router)
```

- [ ] **Step 8: Update app/main.py to include the router**

Replace `apps/api/app/main.py` with:

```python
from fastapi import FastAPI

from app.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(title="Finance Tracker API", version="0.1.0")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)

    return app
```

- [ ] **Step 9: Run tests to verify they pass**

```bash
cd apps/api && pytest tests/test_accounts.py tests/test_health.py -v
```

Expected: all tests PASS.

- [ ] **Step 10: Commit**

```bash
git add apps/api/app/api/ apps/api/app/schemas/account.py apps/api/app/repositories/account.py apps/api/tests/test_accounts.py
git commit -m "feat(api): add accounts CRUD endpoints with repository"
```

---

## Task 6: Transactions CRUD

**Files:**
- Create: `apps/api/app/schemas/transaction.py`
- Create: `apps/api/app/repositories/transaction.py`
- Create: `apps/api/app/api/transactions.py`
- Modify: `apps/api/app/api/router.py`
- Create: `apps/api/tests/test_transactions.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_transactions.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.user import User


def _seed(db: Session) -> int:
    """Seed a user and account; return account_id."""
    user = User(id=1, auth_provider="test", auth_subject="test-1", email="t@example.com")
    db.add(user)
    db.flush()
    account = Account(user_id=1, name="Checking", type="checking", balance=0, currency="USD")
    db.add(account)
    db.commit()
    db.refresh(account)
    return account.id


class TestTransactionAPI:
    def test_list_empty(self, client: TestClient, db_session: Session):
        _seed(db_session)
        response = client.get("/transactions")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_transaction(self, client: TestClient, db_session: Session):
        acct_id = _seed(db_session)
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
        acct_id = _seed(db_session)
        client.post(
            "/transactions",
            json={
                "account_id": acct_id,
                "occurred_on": "2026-03-01",
                "amount": -10,
                "merchant": "A",
                "dedupe_hash": "h1",
                "category": "Food",
            },
        )
        client.post(
            "/transactions",
            json={
                "account_id": acct_id,
                "occurred_on": "2026-04-01",
                "amount": -20,
                "merchant": "B",
                "dedupe_hash": "h2",
                "category": "Transport",
            },
        )
        # Filter by category
        resp = client.get("/transactions", params={"category": "Food"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["merchant"] == "A"

    def test_update_transaction(self, client: TestClient, db_session: Session):
        acct_id = _seed(db_session)
        create_resp = client.post(
            "/transactions",
            json={
                "account_id": acct_id,
                "occurred_on": "2026-03-15",
                "amount": -42.50,
                "merchant": "Whole Foods",
                "dedupe_hash": "h1",
            },
        )
        txn_id = create_resp.json()["id"]
        resp = client.patch(f"/transactions/{txn_id}", json={"category": "Groceries"})
        assert resp.status_code == 200
        assert resp.json()["category"] == "Groceries"

    def test_update_nonexistent(self, client: TestClient, db_session: Session):
        _seed(db_session)
        resp = client.patch("/transactions/9999", json={"category": "X"})
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/api && pytest tests/test_transactions.py -v
```

Expected: FAIL — transaction endpoints don't exist.

- [ ] **Step 3: Write app/schemas/transaction.py**

Create `apps/api/app/schemas/transaction.py`:

```python
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class TransactionCreate(BaseModel):
    account_id: int
    external_id: Optional[str] = None
    occurred_on: date
    amount: float
    merchant: str
    normalized_merchant: Optional[str] = None
    category: Optional[str] = None
    is_income: bool = False
    is_savings: bool = False
    source: Optional[str] = None
    dedupe_hash: str
    notes: Optional[str] = None


class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    is_income: Optional[bool] = None
    is_savings: Optional[bool] = None
    notes: Optional[str] = None


class TransactionRead(BaseModel):
    id: int
    user_id: int
    account_id: int
    external_id: Optional[str]
    occurred_on: date
    posted_at: Optional[datetime]
    amount: float
    merchant: str
    normalized_merchant: Optional[str]
    category: Optional[str]
    is_income: bool
    is_savings: bool
    source: Optional[str]
    source_import_id: Optional[int]
    dedupe_hash: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Write app/repositories/transaction.py**

Create `apps/api/app/repositories/transaction.py`:

```python
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate, TransactionUpdate


class TransactionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(
        self,
        user_id: int,
        category: Optional[str] = None,
        account_id: Optional[int] = None,
    ) -> list[Transaction]:
        stmt = select(Transaction).where(Transaction.user_id == user_id)
        if category:
            stmt = stmt.where(Transaction.category == category)
        if account_id:
            stmt = stmt.where(Transaction.account_id == account_id)
        stmt = stmt.order_by(Transaction.occurred_on.desc())
        return list(self.db.scalars(stmt).all())

    def get(self, txn_id: int, user_id: int) -> Transaction | None:
        stmt = select(Transaction).where(
            Transaction.id == txn_id, Transaction.user_id == user_id
        )
        return self.db.scalars(stmt).first()

    def create(self, user_id: int, data: TransactionCreate) -> Transaction:
        txn = Transaction(user_id=user_id, **data.model_dump())
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def update(self, txn: Transaction, data: TransactionUpdate) -> Transaction:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(txn, field, value)
        self.db.commit()
        self.db.refresh(txn)
        return txn
```

- [ ] **Step 5: Write app/api/transactions.py**

Create `apps/api/app/api/transactions.py`:

```python
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.repositories.transaction import TransactionRepository
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionRead])
def list_transactions(
    category: Optional[str] = None,
    account_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[TransactionRead]:
    repo = TransactionRepository(db)
    return repo.list_by_user(user_id, category=category, account_id=account_id)


@router.post("", response_model=TransactionRead, status_code=201)
def create_transaction(
    data: TransactionCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> TransactionRead:
    repo = TransactionRepository(db)
    return repo.create(user_id, data)


@router.patch("/{transaction_id}", response_model=TransactionRead)
def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> TransactionRead:
    repo = TransactionRepository(db)
    txn = repo.get(transaction_id, user_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return repo.update(txn, data)
```

- [ ] **Step 6: Update app/api/router.py**

Replace `apps/api/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api.accounts import router as accounts_router
from app.api.transactions import router as transactions_router

api_router = APIRouter()
api_router.include_router(accounts_router)
api_router.include_router(transactions_router)
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd apps/api && pytest tests/test_transactions.py tests/test_health.py -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/api/app/schemas/transaction.py apps/api/app/repositories/transaction.py apps/api/app/api/transactions.py apps/api/app/api/router.py apps/api/tests/test_transactions.py
git commit -m "feat(api): add transactions CRUD endpoints with filtering"
```

---

## Task 7: Goals CRUD

**Files:**
- Create: `apps/api/app/schemas/goal.py`
- Create: `apps/api/app/repositories/goal.py`
- Create: `apps/api/app/api/goals.py`
- Modify: `apps/api/app/api/router.py`
- Create: `apps/api/tests/test_goals.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_goals.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def _seed_user(db: Session) -> None:
    user = User(id=1, auth_provider="test", auth_subject="test-1", email="t@example.com")
    db.add(user)
    db.commit()


class TestGoalAPI:
    def test_list_empty(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        response = client.get("/goals")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_goal(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        payload = {
            "name": "Emergency Fund",
            "goal_type": "savings",
            "target_amount": 10000.00,
            "current_amount": 2500.00,
            "is_monthly": False,
        }
        response = client.post("/goals", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Emergency Fund"
        assert data["target_amount"] == 10000.00

    def test_create_monthly_goal(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        payload = {
            "name": "Food Budget",
            "goal_type": "monthly",
            "target_amount": 500.00,
            "is_monthly": True,
        }
        response = client.post("/goals", json=payload)
        assert response.status_code == 201
        assert response.json()["is_monthly"] is True

    def test_update_goal(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        create_resp = client.post(
            "/goals",
            json={
                "name": "Fund",
                "goal_type": "savings",
                "target_amount": 5000,
                "is_monthly": False,
            },
        )
        goal_id = create_resp.json()["id"]
        resp = client.patch(f"/goals/{goal_id}", json={"current_amount": 3000.00})
        assert resp.status_code == 200
        assert resp.json()["current_amount"] == 3000.00

    def test_update_nonexistent(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        resp = client.patch("/goals/9999", json={"current_amount": 100})
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/api && pytest tests/test_goals.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write app/schemas/goal.py**

Create `apps/api/app/schemas/goal.py`:

```python
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class GoalCreate(BaseModel):
    name: str
    goal_type: str
    target_amount: float
    current_amount: float = 0.0
    deadline: Optional[date] = None
    is_monthly: bool = False


class GoalUpdate(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[float] = None
    current_amount: Optional[float] = None
    deadline: Optional[date] = None


class GoalRead(BaseModel):
    id: int
    user_id: int
    name: str
    goal_type: str
    target_amount: float
    current_amount: float
    deadline: Optional[date]
    is_monthly: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Write app/repositories/goal.py**

Create `apps/api/app/repositories/goal.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.schemas.goal import GoalCreate, GoalUpdate


class GoalRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(self, user_id: int) -> list[Goal]:
        stmt = select(Goal).where(Goal.user_id == user_id)
        return list(self.db.scalars(stmt).all())

    def get(self, goal_id: int, user_id: int) -> Goal | None:
        stmt = select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
        return self.db.scalars(stmt).first()

    def create(self, user_id: int, data: GoalCreate) -> Goal:
        goal = Goal(user_id=user_id, **data.model_dump())
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def update(self, goal: Goal, data: GoalUpdate) -> Goal:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(goal, field, value)
        self.db.commit()
        self.db.refresh(goal)
        return goal
```

- [ ] **Step 5: Write app/api/goals.py**

Create `apps/api/app/api/goals.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.repositories.goal import GoalRepository
from app.schemas.goal import GoalCreate, GoalRead, GoalUpdate

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalRead])
def list_goals(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[GoalRead]:
    repo = GoalRepository(db)
    return repo.list_by_user(user_id)


@router.post("", response_model=GoalRead, status_code=201)
def create_goal(
    data: GoalCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> GoalRead:
    repo = GoalRepository(db)
    return repo.create(user_id, data)


@router.patch("/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: int,
    data: GoalUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> GoalRead:
    repo = GoalRepository(db)
    goal = repo.get(goal_id, user_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return repo.update(goal, data)
```

- [ ] **Step 6: Update app/api/router.py**

Replace `apps/api/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api.accounts import router as accounts_router
from app.api.goals import router as goals_router
from app.api.transactions import router as transactions_router

api_router = APIRouter()
api_router.include_router(accounts_router)
api_router.include_router(transactions_router)
api_router.include_router(goals_router)
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd apps/api && pytest tests/test_goals.py -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/api/app/schemas/goal.py apps/api/app/repositories/goal.py apps/api/app/api/goals.py apps/api/app/api/router.py apps/api/tests/test_goals.py
git commit -m "feat(api): add goals CRUD endpoints"
```

---

## Task 8: Cards CRUD

**Files:**
- Create: `apps/api/app/schemas/card.py`
- Create: `apps/api/app/repositories/card.py`
- Create: `apps/api/app/api/cards.py`
- Modify: `apps/api/app/api/router.py`
- Create: `apps/api/tests/test_cards.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_cards.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def _seed_user(db: Session) -> None:
    user = User(id=1, auth_provider="test", auth_subject="test-1", email="t@example.com")
    db.add(user)
    db.commit()


class TestCardAPI:
    def test_list_empty(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        response = client.get("/cards")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_card(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        payload = {
            "name": "Chase Sapphire Preferred",
            "network": "visa",
            "annual_fee": 95.00,
            "rewards_config_json": '{"dining": 3, "travel": 2, "other": 1}',
        }
        response = client.post("/cards", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Chase Sapphire Preferred"
        assert data["annual_fee"] == 95.00

    def test_create_no_fee_card(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        payload = {
            "name": "Chase Freedom Unlimited",
            "network": "visa",
            "rewards_config_json": '{"other": 1.5}',
        }
        response = client.post("/cards", json=payload)
        assert response.status_code == 201
        assert response.json()["annual_fee"] == 0.0

    def test_update_card(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        create_resp = client.post(
            "/cards",
            json={"name": "Old Card", "network": "visa", "annual_fee": 0},
        )
        card_id = create_resp.json()["id"]
        resp = client.patch(f"/cards/{card_id}", json={"annual_fee": 250.00})
        assert resp.status_code == 200
        assert resp.json()["annual_fee"] == 250.00

    def test_update_nonexistent(self, client: TestClient, db_session: Session):
        _seed_user(db_session)
        resp = client.patch("/cards/9999", json={"annual_fee": 100})
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/api && pytest tests/test_cards.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write app/schemas/card.py**

Create `apps/api/app/schemas/card.py`:

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CardCreate(BaseModel):
    name: str
    network: str
    annual_fee: float = 0.0
    rewards_config_json: str = "{}"


class CardUpdate(BaseModel):
    name: Optional[str] = None
    network: Optional[str] = None
    annual_fee: Optional[float] = None
    rewards_config_json: Optional[str] = None


class CardRead(BaseModel):
    id: int
    user_id: int
    name: str
    network: str
    annual_fee: float
    rewards_config_json: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Write app/repositories/card.py**

Create `apps/api/app/repositories/card.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.card import Card
from app.schemas.card import CardCreate, CardUpdate


class CardRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(self, user_id: int) -> list[Card]:
        stmt = select(Card).where(Card.user_id == user_id)
        return list(self.db.scalars(stmt).all())

    def get(self, card_id: int, user_id: int) -> Card | None:
        stmt = select(Card).where(Card.id == card_id, Card.user_id == user_id)
        return self.db.scalars(stmt).first()

    def create(self, user_id: int, data: CardCreate) -> Card:
        card = Card(user_id=user_id, **data.model_dump())
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        return card

    def update(self, card: Card, data: CardUpdate) -> Card:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(card, field, value)
        self.db.commit()
        self.db.refresh(card)
        return card
```

- [ ] **Step 5: Write app/api/cards.py**

Create `apps/api/app/api/cards.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.repositories.card import CardRepository
from app.schemas.card import CardCreate, CardRead, CardUpdate

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("", response_model=list[CardRead])
def list_cards(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[CardRead]:
    repo = CardRepository(db)
    return repo.list_by_user(user_id)


@router.post("", response_model=CardRead, status_code=201)
def create_card(
    data: CardCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> CardRead:
    repo = CardRepository(db)
    return repo.create(user_id, data)


@router.patch("/{card_id}", response_model=CardRead)
def update_card(
    card_id: int,
    data: CardUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> CardRead:
    repo = CardRepository(db)
    card = repo.get(card_id, user_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return repo.update(card, data)
```

- [ ] **Step 6: Update app/api/router.py (final version)**

Replace `apps/api/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api.accounts import router as accounts_router
from app.api.cards import router as cards_router
from app.api.goals import router as goals_router
from app.api.transactions import router as transactions_router

api_router = APIRouter()
api_router.include_router(accounts_router)
api_router.include_router(transactions_router)
api_router.include_router(goals_router)
api_router.include_router(cards_router)
```

- [ ] **Step 7: Run full test suite**

```bash
cd apps/api && pytest tests/ -v
```

Expected: all tests across all files PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/api/app/schemas/card.py apps/api/app/repositories/card.py apps/api/app/api/cards.py apps/api/app/api/router.py apps/api/tests/test_cards.py
git commit -m "feat(api): add cards CRUD endpoints"
```

---

## Final Verification

After all 8 tasks, the full test suite should pass:

```bash
cd apps/api && pytest tests/ -v --tb=short
```

Expected output: 7 model tests + 1 health test + 5 account tests + 5 transaction tests + 5 goal tests + 5 card tests = **28 tests PASS**.

The API should be runnable locally:

```bash
cd apps/api && uvicorn app.main:create_app --factory --reload
```

Visit `http://localhost:8000/docs` for the auto-generated OpenAPI docs showing all endpoints.
