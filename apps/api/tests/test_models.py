from datetime import date

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.card import Card
from app.models.goal import Goal
from app.models.import_record import Import, ImportFile
from app.models.recommendation_snapshot import RecommendationSnapshot
from app.models.spending_profile import SpendingProfile
from app.models.transaction import Transaction
from app.models.user import User, UserPreference


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
    pref = UserPreference(
        user_id=user.id, theme="dark", timezone="America/New_York", currency="USD"
    )
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


def test_create_spending_profile(db_session: Session):
    user = _make_user(db_session)
    profile = SpendingProfile(
        user_id=user.id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        avg_monthly_spend=2500.00,
        category_breakdown_json='{"food": 800, "travel": 300}',
        top_merchants_json='["Whole Foods", "Delta", "Amazon"]',
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    assert profile.id is not None
    assert profile.user_id == user.id
    assert profile.period_start == date(2026, 1, 1)
    assert profile.period_end == date(2026, 3, 31)
    assert profile.avg_monthly_spend == 2500.00
    assert profile.category_breakdown_json == '{"food": 800, "travel": 300}'
    assert profile.top_merchants_json == '["Whole Foods", "Delta", "Amazon"]'
    assert profile.computed_at is not None


def test_create_recommendation_snapshot(db_session: Session):
    user = _make_user(db_session)
    snapshot = RecommendationSnapshot(
        user_id=user.id,
        type="upgrade",
        results_json='[{"card_id": 1, "score": 95}]',
        inputs_hash="a" * 64,
    )
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)
    assert snapshot.id is not None
    assert snapshot.user_id == user.id
    assert snapshot.type == "upgrade"
    assert snapshot.results_json == '[{"card_id": 1, "score": 95}]'
    assert snapshot.inputs_hash == "a" * 64
    assert snapshot.computed_at is not None


def test_create_card_with_issuer(db_session: Session):
    user = _make_user(db_session)
    card = Card(
        user_id=user.id,
        name="Chase Sapphire Reserve",
        network="visa",
        issuer="Chase",
        annual_fee=550,
        rewards_config_json='{"travel": 3, "dining": 3, "other": 1}',
    )
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    assert card.id is not None
    assert card.issuer == "Chase"
    assert card.annual_fee == 550


def test_create_card_without_issuer(db_session: Session):
    user = _make_user(db_session)
    card = Card(
        user_id=user.id,
        name="Generic Rewards Card",
        network="mastercard",
        annual_fee=0,
        rewards_config_json='{"other": 1}',
    )
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    assert card.id is not None
    assert card.issuer is None
