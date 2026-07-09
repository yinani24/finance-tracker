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
        # Platinum wins on dollar value: 150k pts @ 1.0¢ = $1500, - $695 fee
        # + $340 credits = $1145, ahead of Sapphire ($700) and Freedom ($250).
        assert results[0]["card"]["cardId"] == "card-platinum"
        # bonus_value is now dollars, not raw points.
        assert results[0]["bonus_value"] == 1500.0

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


class TestBonusValueUsd:
    """Sign-up-bonus valuation in dollars (issue #24)."""

    def test_usd_bonus_passes_through_at_face_value(self):
        offer = {"amount": [{"amount": 200, "currency": "USD"}]}
        assert CardRecommendationService._bonus_value_usd(offer) == 200.0

    def test_points_convert_at_default_rate(self):
        offer = {"amount": [{"amount": 75000}]}
        # default 1.0¢/point → $750
        assert CardRecommendationService._bonus_value_usd(offer) == 750.0

    def test_points_rate_is_configurable(self):
        offer = {"amount": [{"amount": 75000}]}
        assert CardRecommendationService._bonus_value_usd(offer, 1.5) == 1125.0

    def test_mixed_offer_sums_dollars_and_converted_points(self):
        offer = {"amount": [{"amount": 50000}, {"amount": 100, "currency": "USD"}]}
        # 50000 @ 1.0¢ = $500, + $100 face = $600
        assert CardRecommendationService._bonus_value_usd(offer) == 600.0

    def test_bonus_points_counts_only_non_usd_entries(self):
        offer = {"amount": [{"amount": 50000}, {"amount": 100, "currency": "USD"}]}
        assert CardRecommendationService._bonus_points(offer) == 50000.0


class TestCrossTypeRanking:
    """Points and cashback cards must rank on the same dollar scale (issue #24)."""

    # A big-points card and a strong-cashback card constructed so the OLD
    # points-magnitude scoring (90,000 > 500) would rank the points card first,
    # while true dollar value ranks the cashback card first.
    POINTS_CARD = {
        "cardId": "card-bigpoints", "name": "Big Points", "issuer": "TESTBANK",
        "network": "VISA", "annualFee": 600, "universalCashbackPercent": 1,
        "credits": [],
        "offers": [{"spend": 4000, "amount": [{"amount": 90000}], "days": 90, "credits": []}],
        "discontinued": False,
    }
    CASHBACK_CARD = {
        "cardId": "card-cashback", "name": "Cash Back", "issuer": "TESTBANK2",
        "network": "VISA", "annualFee": 0, "universalCashbackPercent": 2,
        "credits": [],
        "offers": [
            {
                "spend": 3000,
                "amount": [{"amount": 500, "currency": "USD"}],
                "days": 90,
                "credits": [],
            }
        ],
        "discontinued": False,
    }

    def test_cashback_outranks_points_when_dollar_value_is_higher(self):
        service = CardRecommendationService()
        cards = [self.POINTS_CARD, self.CASHBACK_CARD]
        results = service.recommend_next_card(_make_profile(2000.0), [], cards)

        by_id = {r["card"]["cardId"]: r for r in results}
        # Both achievable at $2000/mo ($4k in 90d = 2mo; $3k in 90d = 1.5mo).
        assert set(by_id) == {"card-bigpoints", "card-cashback"}
        # New dollar scores: points = $900 - $600 = $300; cashback = $500 - $0 = $500.
        assert by_id["card-bigpoints"]["score"] == 300.0
        assert by_id["card-cashback"]["score"] == 500.0
        # Cashback now ranks first, reversing the old points-magnitude ordering.
        assert results[0]["card"]["cardId"] == "card-cashback"

    def test_explanation_is_dollar_denominated(self):
        service = CardRecommendationService()
        results = service.recommend_next_card(_make_profile(2000.0), [], [self.POINTS_CARD])
        explanation = results[0]["explanation"]
        assert "$" in explanation
        assert "bonus points" not in explanation
        # points bonus shows the conversion clause
        assert "pts @" in explanation


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
