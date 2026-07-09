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
        # Dollar scores now include flat first-year ongoing earn on $24k/yr:
        #   points   = $900 bonus + $240 (1% × $24k) - $600 fee = $540
        #   cashback = $500 bonus + $480 (2% × $24k) - $0   fee = $980
        assert by_id["card-bigpoints"]["score"] == 540.0
        assert by_id["card-cashback"]["score"] == 980.0
        # Cashback still ranks first, reversing the old points-magnitude ordering.
        assert results[0]["card"]["cardId"] == "card-cashback"

    def test_explanation_is_dollar_denominated(self):
        service = CardRecommendationService()
        results = service.recommend_next_card(_make_profile(2000.0), [], [self.POINTS_CARD])
        explanation = results[0]["explanation"]
        assert "$" in explanation
        assert "bonus points" not in explanation
        # points bonus shows the conversion clause
        assert "pts @" in explanation


class TestOngoingRewards:
    """First-year flat-cashback ongoing-rewards term in recommend_next_card (#35)."""

    # The A-vs-B case from the issue, at $3,000/mo ($36k/yr). Both bonuses are
    # trivially achievable (low spend, 90-day window) so ranking turns purely
    # on true first-year value.
    CARD_A = {
        "cardId": "card-a", "name": "Everyday A", "issuer": "BANKA",
        "network": "VISA", "annualFee": 0, "universalCashbackPercent": 2,
        "credits": [],
        "offers": [
            {
                "spend": 500,
                "amount": [{"amount": 150, "currency": "USD"}],
                "days": 90,
                "credits": [],
            }
        ],
        "discontinued": False,
    }
    CARD_B = {
        "cardId": "card-b", "name": "Bonus B", "issuer": "BANKB",
        "network": "VISA", "annualFee": 95, "universalCashbackPercent": 1,
        "credits": [],
        "offers": [
            {
                "spend": 500,
                "amount": [{"amount": 250, "currency": "USD"}],
                "days": 90,
                "credits": [],
            }
        ],
        "discontinued": False,
    }

    def test_ongoing_value_math(self):
        # $3,000/mo × 12 × 2% = $720
        assert CardRecommendationService._ongoing_value(2, 3000.0) == 720.0
        # zero-cashback card earns nothing ongoing
        assert CardRecommendationService._ongoing_value(0, 3000.0) == 0.0

    def test_score_includes_bonus_and_ongoing(self):
        service = CardRecommendationService()
        results = service.recommend_next_card(_make_profile(3000.0), [], [self.CARD_A])
        r = results[0]
        # $150 bonus + $720 ongoing - $0 fee + $0 credits
        assert r["ongoing_value"] == 720.0
        assert r["score"] == 870.0

    def test_zero_cashback_card_scores_bonus_only(self):
        service = CardRecommendationService()
        zero = {**self.CARD_A, "cardId": "card-zero", "universalCashbackPercent": 0}
        results = service.recommend_next_card(_make_profile(3000.0), [], [zero])
        assert results[0]["ongoing_value"] == 0.0
        assert results[0]["score"] == 150.0  # bonus only

    def test_high_earn_no_fee_card_outranks_bonus_heavy_card(self):
        """Regression: the exact A-vs-B inversion the issue calls out.

        Old score (bonus - fee): A = 150, B = 155 → B wrongly ranked first.
        New score adds ongoing earn: A = $870, B = $515 → A correctly first.
        """
        service = CardRecommendationService()
        results = service.recommend_next_card(_make_profile(3000.0), [], [self.CARD_A, self.CARD_B])
        by_id = {r["card"]["cardId"]: r for r in results}
        assert by_id["card-a"]["score"] == 870.0   # 150 + 720
        assert by_id["card-b"]["score"] == 515.0   # 250 + 360 - 95
        assert results[0]["card"]["cardId"] == "card-a"

    def test_ongoing_respects_achievability(self):
        """A card whose bonus is unachievable is still skipped, ongoing or not."""
        service = CardRecommendationService()
        hard = {
            **self.CARD_A, "cardId": "card-hard",
            "offers": [
                {
                    "spend": 9000,
                    "amount": [{"amount": 150, "currency": "USD"}],
                    "days": 30,
                    "credits": [],
                }
            ],
        }
        # $9k in 30 days needs $9k/mo; at $3k/mo it's unachievable → excluded.
        results = service.recommend_next_card(_make_profile(3000.0), [], [hard])
        assert results == []

    def test_explanation_shows_all_four_components(self):
        service = CardRecommendationService()
        results = service.recommend_next_card(_make_profile(3000.0), [], [self.CARD_A])
        explanation = results[0]["explanation"]
        assert "bonus" in explanation
        assert "ongoing" in explanation
        assert "credits" in explanation
        assert "fee" in explanation
        # the ongoing clause surfaces the rate and the annual spend it applies to
        assert "2.0% on $36,000" in explanation


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
