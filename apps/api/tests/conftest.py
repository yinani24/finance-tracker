from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.auth import get_current_user
from app.config import settings
from app.database import Base, get_db
from app.main import create_app
from app.models.user import User

TEST_DATABASE_URL = settings.test_database_url


def month_first_before_today(months_ago: int) -> date:
    """First day of the calendar month ``months_ago`` months before today.

    Fixtures that seed transactions and then assert on the recommendation /
    spending-profile lookback window must stay *inside* that window as the wall
    clock advances. Hardcoded absolute dates silently age out of the 6-month
    lookback and turn the trunk red (see #220 — the Jan-2026 seed dates dropped
    out of range once "today" reached August 2026). Anchoring seed dates to
    ``date.today()`` keeps them window-relative and time-independent.

    ``months_ago`` must be less than the lookback (6) so the date is always in
    range; pass 0 for the current month.
    """
    total = date.today().year * 12 + (date.today().month - 1) - months_ago
    return date(total // 12, total % 12 + 1, 1)


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
