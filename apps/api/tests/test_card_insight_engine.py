import json
from unittest.mock import patch

from app.services.card_insight_engine import CardInsightEngine
from app.services.insight_types import EngineContext, EngineEvent


def _profile_ctx(**overrides):
    from app.models.spending_profile import SpendingProfile
    from datetime import date, datetime

    profile = SpendingProfile(
        id=1,
        user_id=1,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        avg_monthly_spend=3000.0,
        category_breakdown_json=json.dumps({"dining": 500, "travel": 800}),
        top_merchants_json=json.dumps([]),
        computed_at=datetime(2026, 4, 1),
    )
    from app.models.card import Card

    cards = overrides.get("cards", [
        Card(id=1, user_id=1, name="My Card", network="Visa", issuer="Chase", annual_fee=0.0, rewards_config_json="{}"),
    ])
    ctx = EngineContext(spending_profile=profile, cards=cards)
    return ctx


def test_relevant_events():
    engine = CardInsightEngine()
    events = engine.relevant_events()
    assert EngineEvent.TRANSACTIONS_SYNCED in events
    assert EngineEvent.CARD_MUTATED in events


def test_generate_returns_drafts_with_correct_fields():
    engine = CardInsightEngine()
    ctx = _profile_ctx()

    fake_api_cards = [
        {
            "name": "Sapphire Preferred",
            "issuer": "CHASE",
            "network": "Visa",
            "annualFee": 95,
            "universalCashbackPercent": 1,
            "isAnnualFeeWaived": False,
            "discontinued": False,
            "credits": [],
            "offers": [
                {
                    "amount": [{"amount": 60000}],
                    "spend": 4000,
                    "days": 90,
                }
            ],
        }
    ]

    with patch("app.services.card_insight_engine.fetch_card_bonuses", return_value=fake_api_cards):
        drafts = engine.generate(user_id=1, ctx=ctx)

    assert len(drafts) >= 1
    draft = drafts[0]
    assert draft.kind == "next_card"
    assert draft.impact_one_time_cents > 0
    assert draft.effort == "medium"
    assert "summary" in draft.evidence
    assert draft.inputs_hash != ""


def test_generate_with_no_profile_returns_empty():
    engine = CardInsightEngine()
    ctx = EngineContext()
    with patch("app.services.card_insight_engine.fetch_card_bonuses", return_value=[]):
        drafts = engine.generate(user_id=1, ctx=ctx)
    assert drafts == []


def test_generate_portfolio_insights():
    engine = CardInsightEngine()
    from app.models.card import Card

    cards = [
        Card(id=1, user_id=1, name="Expensive Card", network="Visa", issuer="AMEX", annual_fee=550.0, rewards_config_json="{}"),
    ]
    ctx = _profile_ctx(cards=cards)

    fake_api_cards = [
        {
            "name": "Expensive Card",
            "issuer": "AMEX",
            "network": "Visa",
            "annualFee": 550,
            "universalCashbackPercent": 2,
            "isAnnualFeeWaived": False,
            "discontinued": False,
            "credits": [],
            "offers": [],
        },
        {
            "name": "Free Card",
            "issuer": "DISCOVER",
            "network": "Visa",
            "annualFee": 0,
            "universalCashbackPercent": 2,
            "isAnnualFeeWaived": False,
            "discontinued": False,
            "credits": [],
            "offers": [],
        },
    ]

    with patch("app.services.card_insight_engine.fetch_card_bonuses", return_value=fake_api_cards):
        drafts = engine.generate(user_id=1, ctx=ctx)

    portfolio_drafts = [d for d in drafts if d.kind == "portfolio_underperforming"]
    assert len(portfolio_drafts) >= 1
