from __future__ import annotations

from app.services.card_recommendation import CardRecommendationService

SAMPLE_CARDS = [
    {
        "cardId": "card-sapphire", "name": "Sapphire Preferred", "issuer": "CHASE",
        "network": "VISA", "currency": "CHASE", "isBusiness": False, "annualFee": 95,
        "isAnnualFeeWaived": False, "universalCashbackPercent": 1,
        "url": "https://example.com/sapphire", "imageUrl": "/images/sapphire.png",
        "credits": [{"description": "Hotel Credit", "value": 50, "weight": 0.9}],
        "offers": [{"spend": 5000, "amount": [{"amount": 75000}], "days": 90, "credits": []}],
        "discontinued": False,
    },
    {
        "cardId": "card-freedom", "name": "Freedom Unlimited", "issuer": "CHASE",
        "network": "VISA", "currency": "CHASE", "isBusiness": False, "annualFee": 0,
        "isAnnualFeeWaived": False, "universalCashbackPercent": 1.5,
        "url": "https://example.com/freedom", "imageUrl": "/images/freedom.png",
        "credits": [],
        "offers": [{"spend": 500, "amount": [{"amount": 25000}], "days": 90, "credits": []}],
        "discontinued": False,
    },
    {
        "cardId": "card-platinum", "name": "Platinum Card", "issuer": "AMERICAN_EXPRESS",
        "network": "AMERICAN_EXPRESS", "currency": "AMEX_MR", "isBusiness": False,
        "annualFee": 695, "isAnnualFeeWaived": False, "universalCashbackPercent": 1,
        "url": "https://example.com/platinum", "imageUrl": "/images/platinum.png",
        "credits": [
            {"description": "Airline Credit", "value": 200, "weight": 0.9},
            {"description": "Hotel Credit", "value": 200, "weight": 0.8},
        ],
        "offers": [{"spend": 8000, "amount": [{"amount": 150000}], "days": 180, "credits": []}],
        "discontinued": False,
    },
]


def _make_profile(avg_monthly_spend: float) -> dict:
    return {
        "avg_monthly_spend": avg_monthly_spend,
        "category_breakdown": {"food and drink": 450, "travel": 300},
        "top_merchants": [{"name": "chipotle", "monthly_avg": 100}],
    }


class TestRecommendNextCard:
    def test_ranks_by_achievable_bonus_value(self):
        service = CardRecommendationService()
        results = service.recommend_next_card(_make_profile(2000.0), [], SAMPLE_CARDS)

        assert len(results) > 0
        # Platinum has highest bonus (150k) so should score highest
        assert results[0]["card"]["cardId"] == "card-platinum"

    def test_filters_unachievable_bonuses(self):
        service = CardRecommendationService()
        results = service.recommend_next_card(_make_profile(500.0), [], SAMPLE_CARDS)

        card_ids = [r["card"]["cardId"] for r in results]
        assert "card-freedom" in card_ids
        # Sapphire needs $5k in 90 days = $1667/mo, not achievable at $500/mo
        assert "card-sapphire" not in card_ids

    def test_excludes_cards_user_already_has(self):
        service = CardRecommendationService()
        user_cards = [{"name": "Sapphire Preferred", "issuer": "CHASE"}]
        results = service.recommend_next_card(_make_profile(3000.0), user_cards, SAMPLE_CARDS)

        card_ids = [r["card"]["cardId"] for r in results]
        assert "card-sapphire" not in card_ids

    def test_no_offers_card_excluded(self):
        service = CardRecommendationService()
        cards_no_offer = [{**SAMPLE_CARDS[0], "cardId": "card-no-offer", "offers": []}]
        results = service.recommend_next_card(_make_profile(3000.0), [], cards_no_offer)
        assert len(results) == 0


class TestAnalyzePortfolio:
    def test_flags_card_costing_money(self):
        service = CardRecommendationService()
        user_cards = [{"name": "Platinum Card", "issuer": "AMERICAN_EXPRESS", "network": "AMERICAN_EXPRESS", "annual_fee": 695}]
        result = service.analyze_portfolio(_make_profile(500.0), user_cards, SAMPLE_CARDS)

        assert len(result) == 1
        assert result[0]["status"] == "costing_money"
        assert result[0]["net_value"] < 0

    def test_flags_card_as_good(self):
        service = CardRecommendationService()
        user_cards = [{"name": "Freedom Unlimited", "issuer": "CHASE", "network": "VISA", "annual_fee": 0}]
        result = service.analyze_portfolio(_make_profile(5000.0), user_cards, SAMPLE_CARDS)

        assert len(result) == 1
        assert result[0]["status"] == "good"
        assert result[0]["net_value"] > 0

    def test_suggests_alternatives_for_bad_cards(self):
        service = CardRecommendationService()
        user_cards = [{"name": "Platinum Card", "issuer": "AMERICAN_EXPRESS", "network": "AMERICAN_EXPRESS", "annual_fee": 695}]
        result = service.analyze_portfolio(_make_profile(500.0), user_cards, SAMPLE_CARDS)

        assert result[0]["status"] == "costing_money"
        assert len(result[0]["alternatives"]) > 0

    def test_empty_portfolio(self):
        service = CardRecommendationService()
        result = service.analyze_portfolio(_make_profile(2000.0), [], SAMPLE_CARDS)
        assert result == []
