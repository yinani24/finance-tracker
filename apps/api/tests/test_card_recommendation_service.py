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


# A card with two concurrent offer tiers (like 27 of the 179 dataset cards,
# e.g. Delta SkyMiles Gold): a high-spend/high-bonus tier and a
# low-spend/low-bonus tier.
TIERED_CARD = {
    "cardId": "card-tiered", "name": "Tiered Rewards", "issuer": "CHASE",
    "network": "VISA", "currency": "CHASE", "isBusiness": False, "annualFee": 0,
    "isAnnualFeeWaived": False, "universalCashbackPercent": 1,
    "url": "https://example.com/tiered", "imageUrl": "/images/tiered.png",
    "credits": [],
    "offers": [
        {"spend": 5000, "amount": [{"amount": 90000}], "days": 180, "credits": []},
        {"spend": 2000, "amount": [{"amount": 50000}], "days": 180, "credits": []},
    ],
    "discontinued": False,
}


class TestMultiTierOffers:
    """A card must not be dropped just because its *top* tier is unachievable
    when a smaller tier is within reach (issue #55)."""

    def test_smaller_tier_used_when_top_tier_unachievable(self):
        service = CardRecommendationService()
        # $400/mo: top tier ($5k/180d ≈ $833/mo) is out of reach, but the
        # smaller tier ($2k/180d ≈ $333/mo) is achievable.
        results = service.recommend_next_card(_make_profile(400.0), [], [TIERED_CARD])
        assert len(results) == 1
        r = results[0]
        # 50k pts @ 1.0¢ = $500 (the smaller tier), not the 90k top tier.
        assert r["bonus_value"] == 500.0
        assert r["months_to_hit"] == 2000 / 400

    def test_top_tier_used_when_achievable(self):
        service = CardRecommendationService()
        # $1500/mo: top tier ($5k/180d ≈ $833/mo) is achievable and worth more.
        results = service.recommend_next_card(_make_profile(1500.0), [], [TIERED_CARD])
        assert len(results) == 1
        r = results[0]
        # 90k pts @ 1.0¢ = $900 (the top tier wins on value).
        assert r["bonus_value"] == 900.0
        assert r["months_to_hit"] == 5000 / 1500

    def test_card_dropped_only_when_no_tier_achievable(self):
        service = CardRecommendationService()
        # $200/mo: even the smaller tier ($2k/180d ≈ $333/mo) is out of reach.
        results = service.recommend_next_card(_make_profile(200.0), [], [TIERED_CARD])
        assert results == []


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

    # --- issue #201: field-less amount inherits the card's currency ---------

    def test_fieldless_amount_on_usd_card_is_dollars_not_points(self):
        # A $250 cash bonus with no per-amount currency, on a currency:"USD"
        # cashback card, must score $250 — not $2.50 (the ~100× bug).
        offer = {"amount": [{"amount": 250}]}
        assert (
            CardRecommendationService._bonus_value_usd(offer, 1.0, "USD") == 250.0
        )

    def test_fieldless_amount_on_points_card_still_converts_as_points(self):
        # Same field-less shape on a points card keeps points valuation.
        offer = {"amount": [{"amount": 60000}]}
        assert (
            CardRecommendationService._bonus_value_usd(offer, 1.0, "CHASE") == 600.0
        )

    def test_explicit_usd_amount_unaffected_by_points_card_currency(self):
        # An explicitly USD-tagged amount stays dollars even on a points card.
        offer = {"amount": [{"amount": 200, "currency": "USD"}]}
        assert (
            CardRecommendationService._bonus_value_usd(offer, 1.0, "CHASE") == 200.0
        )

    def test_mixed_offer_on_usd_card_sums_dollars(self):
        # Field-less + explicit-USD amounts on a USD card: both dollars.
        offer = {"amount": [{"amount": 250}, {"amount": 100, "currency": "USD"}]}
        assert (
            CardRecommendationService._bonus_value_usd(offer, 1.0, "USD") == 350.0
        )

    def test_fieldless_without_card_currency_defaults_to_points(self):
        # No card context (legacy bare call) → field-less treated as points.
        offer = {"amount": [{"amount": 75000}]}
        assert CardRecommendationService._bonus_value_usd(offer) == 750.0

    def test_bonus_points_excludes_fieldless_amount_on_usd_card(self):
        # The explanation copy must not render "(250 pts @ 1.0¢)" for cash.
        offer = {"amount": [{"amount": 250}]}
        assert CardRecommendationService._bonus_points(offer, "USD") == 0.0

    def test_bonus_points_counts_fieldless_amount_on_points_card(self):
        offer = {"amount": [{"amount": 60000}]}
        assert CardRecommendationService._bonus_points(offer, "CHASE") == 60000.0


class TestCreditValue:
    """Recurring/anniversary credit valuation in dollars."""

    def test_usd_credit_at_face_value(self):
        card = {"credits": [{"value": 200, "currency": "USD"}]}
        assert CardRecommendationService._credit_value(card) == 200.0

    def test_points_credit_converts_at_cents_not_face(self):
        # A 15,000-point anniversary credit is ~$150 at 1.0¢/pt, NOT $15,000.
        card = {"credits": [{"value": 15000, "currency": "WYNDHAM"}]}
        assert CardRecommendationService._credit_value(card) == 150.0

    def test_points_credit_rate_is_configurable(self):
        card = {"credits": [{"value": 15000, "currency": "WYNDHAM"}]}
        assert CardRecommendationService._credit_value(card, 1.5) == 225.0

    def test_missing_currency_treated_as_dollars(self):
        card = {"credits": [{"value": 300}]}
        assert CardRecommendationService._credit_value(card) == 300.0

    def test_weight_is_applied(self):
        card = {"credits": [{"value": 100, "currency": "USD", "weight": 2}]}
        assert CardRecommendationService._credit_value(card) == 200.0


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


class TestFieldlessCashbackBonus:
    """Field-less USD-card bonuses value at face, not ~1% (issue #201)."""

    # A real-dataset shape: a currency:"USD" cashback card whose $250 bonus
    # amount carries no per-amount currency field. Before the fix this scored
    # $2.50 of bonus (~100× low) and lost to any modest points card.
    USD_FIELDLESS_CARD = {
        "cardId": "card-usd-fieldless", "name": "Cash Rewards", "issuer": "TESTBANK",
        "network": "VISA", "currency": "USD", "annualFee": 0,
        "universalCashbackPercent": 1.5, "credits": [],
        "offers": [{"spend": 1000, "amount": [{"amount": 250}], "days": 90, "credits": []}],
        "discontinued": False,
    }

    def test_fieldless_usd_bonus_scores_full_dollar_value(self):
        service = CardRecommendationService()
        results = service.recommend_next_card(
            _make_profile(2000.0), [], [self.USD_FIELDLESS_CARD]
        )
        rec = results[0]
        assert rec["bonus_value"] == 250.0  # not 2.50
        # $250 bonus + 1.5% × $24k ongoing = $250 + $360 = $610
        assert rec["score"] == 610.0

    def test_fieldless_usd_bonus_explanation_has_no_points_clause(self):
        service = CardRecommendationService()
        results = service.recommend_next_card(
            _make_profile(2000.0), [], [self.USD_FIELDLESS_CARD]
        )
        explanation = results[0]["explanation"]
        assert "pts @" not in explanation
        assert "Earn ~$250 in bonus value" in explanation


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
        # $3,000/mo × 12 × 2% = $720 — flat model, no category breakdown given.
        two_pct = {"cardId": "x", "universalCashbackPercent": 2}
        assert CardRecommendationService._ongoing_value(two_pct, 3000.0) == 720.0
        # zero-cashback card earns nothing ongoing
        zero_pct = {"cardId": "y", "universalCashbackPercent": 0}
        assert CardRecommendationService._ongoing_value(zero_pct, 3000.0) == 0.0
        # an uncurated card with a breakdown still equals the flat number, since
        # sum(breakdown) == avg_monthly_spend and every category earns the flat
        # rate (additivity guarantee).
        assert (
            CardRecommendationService._ongoing_value(
                two_pct, 3000.0, {"dining": 1000.0, "travel": 2000.0}
            )
            == 720.0
        )

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
        # the ongoing clause surfaces the (blended) rate and the annual spend it
        # applies to. CARD_A is not in the curated category table → the blended
        # rate equals its flat 2% cashback.
        assert "2.0% blended on $36,000" in explanation


class TestAnalyzePortfolio:
    def test_flags_card_costing_money(self):
        service = CardRecommendationService()
        user_cards = [
            {"name": "Platinum Card", "issuer": "AMERICAN_EXPRESS",
             "network": "AMERICAN_EXPRESS", "annual_fee": 695}
        ]
        result = service.analyze_portfolio(_make_profile(500.0), user_cards, SAMPLE_CARDS)

        assert len(result) == 1
        assert result[0]["status"] == "costing_money"
        assert result[0]["net_value"] < 0

    def test_flags_card_as_good(self):
        service = CardRecommendationService()
        user_cards = [
            {"name": "Freedom Unlimited", "issuer": "CHASE", "network": "VISA", "annual_fee": 0}
        ]
        result = service.analyze_portfolio(_make_profile(5000.0), user_cards, SAMPLE_CARDS)

        assert len(result) == 1
        assert result[0]["status"] == "good"
        assert result[0]["net_value"] > 0

    def test_suggests_alternatives_for_bad_cards(self):
        service = CardRecommendationService()
        user_cards = [
            {"name": "Platinum Card", "issuer": "AMERICAN_EXPRESS",
             "network": "AMERICAN_EXPRESS", "annual_fee": 695}
        ]
        result = service.analyze_portfolio(_make_profile(500.0), user_cards, SAMPLE_CARDS)

        assert result[0]["status"] == "costing_money"
        assert len(result[0]["alternatives"]) > 0

    def test_empty_portfolio(self):
        service = CardRecommendationService()
        result = service.analyze_portfolio(_make_profile(2000.0), [], SAMPLE_CARDS)
        assert result == []


class TestAlternativesExclusions:
    """analyze_portfolio alternatives must only suggest actionable cards —
    never discontinued or already-owned ones (parity with recommend_next_card, #44).
    """

    # A held card that will be flagged non-good: $95 fee, 1% earn at $500/mo
    # ($60/yr) nets negative, so alternatives are computed.
    HELD = {"name": "Held Card", "issuer": "HELDBANK", "network": "VISA", "annual_fee": 95}
    HELD_CARD = {
        "cardId": "card-held", "name": "Held Card", "issuer": "HELDBANK",
        "network": "VISA", "annualFee": 95, "isAnnualFeeWaived": False,
        "universalCashbackPercent": 1, "credits": [], "offers": [],
        "discontinued": False,
    }
    # A strong $0-fee 2% alternative — would be a top alternative if eligible.
    GOOD_ALT = {
        "cardId": "card-goodalt", "name": "Good Alt", "issuer": "ALTBANK",
        "network": "VISA", "annualFee": 0, "isAnnualFeeWaived": False,
        "universalCashbackPercent": 2, "credits": [], "offers": [],
        "discontinued": False,
    }

    def _alt_ids(self, result):
        return [a["card"]["cardId"] for a in result[0]["alternatives"]]

    def test_discontinued_card_excluded_from_alternatives(self):
        service = CardRecommendationService()
        disc_alt = {**self.GOOD_ALT, "cardId": "card-disc", "name": "Disc Alt",
                    "issuer": "DISCBANK", "discontinued": True}
        cards = [self.HELD_CARD, disc_alt]
        result = service.analyze_portfolio(_make_profile(500.0), [self.HELD], cards)
        assert result[0]["status"] != "good"
        assert "card-disc" not in self._alt_ids(result)

    def test_already_owned_card_excluded_from_alternatives(self):
        service = CardRecommendationService()
        # User owns both the flagged card AND the otherwise-attractive alternative.
        owned_alt = {"name": "Good Alt", "issuer": "ALTBANK"}
        cards = [self.HELD_CARD, self.GOOD_ALT]
        result = service.analyze_portfolio(
            _make_profile(500.0), [self.HELD, owned_alt], cards
        )
        assert "card-goodalt" not in self._alt_ids(result)

    def test_valid_alternative_still_surfaced(self):
        service = CardRecommendationService()
        cards = [self.HELD_CARD, self.GOOD_ALT]
        result = service.analyze_portfolio(_make_profile(500.0), [self.HELD], cards)
        assert result[0]["status"] != "good"
        assert "card-goodalt" in self._alt_ids(result)


class TestFirstYearFeeWaiver:
    """First-year fee waiver (isAnnualFeeWaived) in recommend_next_card (#41).

    The objective is *first-year* value, so a card that waives its annual fee
    the first year costs $0 in year one — its listed annualFee must not be
    subtracted from the first-year score.
    """

    # $95 fee waived the first year; both cards below are otherwise identical
    # and their bonuses are trivially achievable at $3,000/mo.
    WAIVED = {
        "cardId": "card-waived", "name": "Waived W", "issuer": "BANKW",
        "network": "VISA", "annualFee": 95, "isAnnualFeeWaived": True,
        "universalCashbackPercent": 1, "credits": [],
        "offers": [
            {
                "spend": 500,
                "amount": [{"amount": 200, "currency": "USD"}],
                "days": 90,
                "credits": [],
            }
        ],
        "discontinued": False,
    }
    UNWAIVED = {**WAIVED, "cardId": "card-unwaived", "name": "Unwaived U",
                "issuer": "BANKU", "isAnnualFeeWaived": False}

    def test_first_year_fee_waived_is_zero(self):
        assert CardRecommendationService._first_year_fee(
            {"annualFee": 95, "isAnnualFeeWaived": True}
        ) == 0.0

    def test_first_year_fee_not_waived_is_full(self):
        assert CardRecommendationService._first_year_fee(
            {"annualFee": 95, "isAnnualFeeWaived": False}
        ) == 95.0

    def test_first_year_fee_missing_flag_defaults_to_full(self):
        # A card with no isAnnualFeeWaived key pays the full fee.
        assert CardRecommendationService._first_year_fee({"annualFee": 95}) == 95.0

    def test_score_excludes_waived_fee(self):
        service = CardRecommendationService()
        results = service.recommend_next_card(_make_profile(3000.0), [], [self.WAIVED])
        # $200 bonus + $360 ongoing (1% of $36k) - $0 first-year fee + $0 credits
        assert results[0]["score"] == 560.0

    def test_waived_card_outranks_identical_unwaived_by_the_fee(self):
        service = CardRecommendationService()
        results = service.recommend_next_card(
            _make_profile(3000.0), [], [self.UNWAIVED, self.WAIVED]
        )
        by_id = {r["card"]["cardId"]: r for r in results}
        assert by_id["card-waived"]["score"] == 560.0     # fee waived year 1
        assert by_id["card-unwaived"]["score"] == 465.0   # 560 - 95 fee
        assert results[0]["card"]["cardId"] == "card-waived"

    def test_explanation_notes_the_waiver(self):
        service = CardRecommendationService()
        results = service.recommend_next_card(_make_profile(3000.0), [], [self.WAIVED])
        explanation = results[0]["explanation"]
        assert "waived year 1" in explanation
        assert "fee $0" in explanation


class TestCategoryAwareEarn:
    """Category-aware ongoing earn from the curated per-category rate table (#38).

    Uses a real curated ``cardId`` — Amex Gold
    (``cafe43d37256bec116dff4be6cced2cf``: dining 4, groceries 4, travel 3 in
    ``app/data/card_category_rates.json``) — so these tests also assert the
    shipped data file is wired in correctly.
    """

    GOLD_ID = "cafe43d37256bec116dff4be6cced2cf"

    def _curated_card(self, **overrides):
        card = {
            "cardId": self.GOLD_ID, "name": "Gold", "issuer": "AMERICAN_EXPRESS",
            "network": "AMERICAN_EXPRESS", "annualFee": 0, "isAnnualFeeWaived": False,
            "universalCashbackPercent": 1, "credits": [], "discontinued": False,
            "offers": [{"spend": 500, "amount": [{"amount": 100, "currency": "USD"}],
                        "days": 90, "credits": []}],
        }
        card.update(overrides)
        return card

    def test_curated_rate_applied_per_category(self):
        # $1,000/mo all dining → Gold earns the curated 4% on dining, not 1%.
        gold = self._curated_card()
        assert CardRecommendationService._ongoing_value(
            gold, 1000.0, {"dining": 1000.0}
        ) == 480.0  # 1000 × 12 × 4%

    def test_uncurated_category_falls_back_to_flat(self):
        # Dining is curated at 4; 'bills' is not curated for Gold → its flat 1%.
        gold = self._curated_card()
        got = CardRecommendationService._ongoing_value(
            gold, 1000.0, {"dining": 500.0, "bills": 500.0}
        )
        assert got == 500 * 12 * 4 / 100 + 500 * 12 * 1 / 100  # 240 + 60 = 300

    def test_uncurated_card_identical_to_flat(self):
        # A card absent from the table earns exactly the flat number even with a
        # breakdown present — the additivity / non-regression guarantee.
        flat = {"cardId": "not-in-table", "universalCashbackPercent": 2}
        assert CardRecommendationService._ongoing_value(
            flat, 1000.0, {"dining": 400.0, "travel": 600.0}
        ) == 1000.0 * 12 * 2 / 100  # 240.0

    def test_ranking_shifts_with_category_spend(self):
        """PRD success criterion: moving spend between categories changes the
        ranking. A dining-4x curated card beats a flat-2% card when spend is
        dining-heavy, and loses when the same spend moves off dining."""
        service = CardRecommendationService()
        gold = self._curated_card()  # dining 4%, flat 1% elsewhere
        flat2 = {
            "cardId": "flat-2pct", "name": "Flat Two", "issuer": "BANKF",
            "network": "VISA", "annualFee": 0, "universalCashbackPercent": 2,
            "credits": [], "discontinued": False,
            "offers": [{"spend": 500, "amount": [{"amount": 100, "currency": "USD"}],
                        "days": 90, "credits": []}],
        }
        cards = [gold, flat2]

        dining_heavy = {"avg_monthly_spend": 1000.0,
                        "category_breakdown": {"dining": 1000.0}, "top_merchants": []}
        res = service.recommend_next_card(dining_heavy, [], cards)
        # Gold: 100 bonus + 480 ongoing = 580; Flat: 100 + 240 = 340.
        assert res[0]["card"]["cardId"] == self.GOLD_ID
        by_id = {r["card"]["cardId"]: r for r in res}
        assert by_id[self.GOLD_ID]["ongoing_value"] == 480.0

        # Same total spend, now on a category Gold doesn't bonus → Gold drops to
        # its flat 1% and the flat-2% card wins. Ranking flips.
        bills_heavy = {"avg_monthly_spend": 1000.0,
                       "category_breakdown": {"bills": 1000.0}, "top_merchants": []}
        res2 = service.recommend_next_card(bills_heavy, [], cards)
        assert res2[0]["card"]["cardId"] == "flat-2pct"

    def test_analyze_portfolio_uses_curated_rate(self):
        """The held-card path shares the same seam, so a curated held card is
        valued category-aware too."""
        service = CardRecommendationService()
        gold = self._curated_card()
        user_cards = [{"name": "Gold", "issuer": "AMERICAN_EXPRESS",
                       "network": "AMERICAN_EXPRESS", "annual_fee": 0}]
        profile = {"avg_monthly_spend": 1000.0,
                   "category_breakdown": {"dining": 1000.0}, "top_merchants": []}
        result = service.analyze_portfolio(profile, user_cards, [gold])
        assert len(result) == 1
        # dining 4% on $12k = $480 (vs the old flat 1% = $120).
        assert result[0]["estimated_annual_value"] == 480.0


class TestBestCardPerCategory:
    """Per-category "best held card" assignment (#177, PRD User Story 2).

    Uses the real curated Amex Gold ``cardId``
    (``cafe43d37256bec116dff4be6cced2cf``: dining 4, groceries 4, travel 3) so
    the assignment shares the exact rate lookup ``_ongoing_value`` uses.
    """

    GOLD_ID = "cafe43d37256bec116dff4be6cced2cf"

    def _gold(self):
        return {
            "cardId": self.GOLD_ID, "name": "Gold", "issuer": "AMERICAN_EXPRESS",
            "network": "AMERICAN_EXPRESS", "annualFee": 250, "universalCashbackPercent": 1,
            "credits": [], "discontinued": False, "offers": [],
        }

    def _flat(self, name="Flat Two", issuer="BANKF", pct=2, fee=0, card_id=None):
        return {
            "cardId": card_id or f"flat-{name.lower().replace(' ', '-')}",
            "name": name, "issuer": issuer, "network": "VISA", "annualFee": fee,
            "universalCashbackPercent": pct, "credits": [], "discontinued": False,
            "offers": [],
        }

    @staticmethod
    def _held(card):
        return {
            "name": card["name"], "issuer": card["issuer"],
            "network": card.get("network", "VISA"),
            "annual_fee": card.get("annualFee", 0),
        }

    def test_dining_strong_card_wins_dining_flat_wins_elsewhere(self):
        service = CardRecommendationService()
        gold, flat = self._gold(), self._flat(pct=2)
        available = [gold, flat]
        user_cards = [self._held(gold), self._held(flat)]
        profile = {
            "avg_monthly_spend": 1000.0,
            "category_breakdown": {"dining": 500.0, "groceries": 200.0, "shopping": 300.0},
            "top_merchants": [],
        }
        assignments = service.best_card_per_category(profile, user_cards, available)
        by_cat = {a["category"]: a for a in assignments}

        # Gold's curated 4% beats the flat 2% for dining and groceries.
        assert by_cat["dining"]["best_card"]["name"] == "Gold"
        assert by_cat["dining"]["rate"] == 4
        assert by_cat["groceries"]["best_card"]["name"] == "Gold"
        # Shopping isn't curated for Gold → its flat 1% loses to the flat 2% card.
        assert by_cat["shopping"]["best_card"]["name"] == "Flat Two"
        assert by_cat["shopping"]["rate"] == 2
        # Rationale names the winner + both rates.
        assert "Gold" in by_cat["dining"]["rationale"]
        assert "4%" in by_cat["dining"]["rationale"]

    def test_zeroed_category_is_dropped(self):
        service = CardRecommendationService()
        gold = self._gold()
        profile = {
            "avg_monthly_spend": 500.0,
            "category_breakdown": {"dining": 500.0, "shopping": 0.0},
            "top_merchants": [],
        }
        assignments = service.best_card_per_category(profile, [self._held(gold)], [gold])
        cats = {a["category"] for a in assignments}
        assert cats == {"dining"}  # zero-spend 'shopping' excluded

    def test_flat_only_wallet_assigns_deterministically(self):
        """No curated rates anywhere → the higher flat-cashback card wins, and
        the assignment is still produced (fallback path)."""
        service = CardRecommendationService()
        a = self._flat(name="Three", issuer="BANKA", pct=3, card_id="flat-a")
        b = self._flat(name="One", issuer="BANKB", pct=1, card_id="flat-b")
        available = [a, b]
        user_cards = [self._held(a), self._held(b)]
        profile = {
            "avg_monthly_spend": 400.0,
            "category_breakdown": {"dining": 400.0},
            "top_merchants": [],
        }
        assignments = service.best_card_per_category(profile, user_cards, available)
        assert len(assignments) == 1
        assert assignments[0]["best_card"]["name"] == "Three"
        assert assignments[0]["rate"] == 3

    def test_tie_breaks_to_lower_fee_then_name(self):
        service = CardRecommendationService()
        # Same 2% rate, different fees → lower fee wins.
        cheap = self._flat(name="Cheap", issuer="BANKC", pct=2, fee=0, card_id="flat-cheap")
        pricey = self._flat(name="Pricey", issuer="BANKP", pct=2, fee=95, card_id="flat-pricey")
        available = [pricey, cheap]  # order shouldn't matter
        user_cards = [self._held(pricey), self._held(cheap)]
        profile = {
            "avg_monthly_spend": 300.0,
            "category_breakdown": {"dining": 300.0},
            "top_merchants": [],
        }
        assignments = service.best_card_per_category(profile, user_cards, available)
        assert assignments[0]["best_card"]["name"] == "Cheap"

        # Same rate AND same fee → alphabetical by name.
        alpha = self._flat(name="Alpha", issuer="BANKX", pct=2, fee=0, card_id="flat-alpha")
        zeta = self._flat(name="Zeta", issuer="BANKZ", pct=2, fee=0, card_id="flat-zeta")
        assignments2 = service.best_card_per_category(
            profile, [self._held(zeta), self._held(alpha)], [zeta, alpha]
        )
        assert assignments2[0]["best_card"]["name"] == "Alpha"

    def test_categories_sorted_and_shape(self):
        service = CardRecommendationService()
        gold = self._gold()
        profile = {
            "avg_monthly_spend": 900.0,
            "category_breakdown": {"travel": 300.0, "dining": 300.0, "groceries": 300.0},
            "top_merchants": [],
        }
        assignments = service.best_card_per_category(profile, [self._held(gold)], [gold])
        assert [a["category"] for a in assignments] == ["dining", "groceries", "travel"]
        for a in assignments:
            assert set(a) == {"category", "best_card", "rate", "rationale"}
            assert set(a["best_card"]) == {"name", "issuer"}

    def test_empty_wallet_returns_no_assignments(self):
        service = CardRecommendationService()
        profile = {
            "avg_monthly_spend": 500.0,
            "category_breakdown": {"dining": 500.0},
            "top_merchants": [],
        }
        assert service.best_card_per_category(profile, [], []) == []

    def test_unmatched_held_card_falls_back_to_zero_rate(self):
        """A held card absent from the dataset earns its flat rate (0 for a bare
        owned-card record) — still deterministic, never crashes."""
        service = CardRecommendationService()
        unknown = {"name": "Store Card", "issuer": "STOREBANK", "annual_fee": 0}
        profile = {
            "avg_monthly_spend": 200.0,
            "category_breakdown": {"dining": 200.0},
            "top_merchants": [],
        }
        assignments = service.best_card_per_category(profile, [unknown], [])
        assert len(assignments) == 1
        assert assignments[0]["best_card"]["name"] == "Store Card"
        assert assignments[0]["rate"] == 0


class TestOfferCreditValue:
    """Credits attached to a sign-up offer are first-year value too (#202)."""

    def test_usd_offer_credit_counts(self):
        offer = {"credits": [{"value": 400, "weight": 1}]}
        assert CardRecommendationService._offer_credit_value(offer) == 400.0

    def test_points_offer_credit_valued_at_cents(self):
        # A 50,000-point free-night certificate is ~$500 at 1¢, not $50,000.
        offer = {"credits": [{"value": 50000, "weight": 1, "currency": "MARRIOTT"}]}
        assert CardRecommendationService._offer_credit_value(offer) == 500.0

    def test_fieldless_offer_credit_is_dollars_not_card_points(self):
        # Statement credits / waived fees carry no currency but ARE dollars —
        # they must not inherit a card's points currency.
        offer = {"credits": [{"description": "Statement Credit", "value": 400}]}
        assert CardRecommendationService._offer_credit_value(offer) == 400.0

    def test_weight_is_applied(self):
        offer = {"credits": [{"value": 100, "weight": 0.6}]}
        assert CardRecommendationService._offer_credit_value(offer) == 60.0

    def test_no_credits_is_zero(self):
        assert CardRecommendationService._offer_credit_value({}) == 0.0

    def test_offer_credits_reach_the_score(self):
        card = {
            "cardId": "c1", "name": "Credited", "issuer": "TEST", "network": "VISA",
            "currency": "TEST_POINTS", "isBusiness": False, "annualFee": 0,
            "isAnnualFeeWaived": False, "universalCashbackPercent": 1,
            "credits": [], "discontinued": False,
            "offers": [{
                "spend": 500, "days": 90, "amount": [{"amount": 10000}],
                "credits": [{"description": "Statement Credit", "value": 400}],
            }],
        }
        profile = {"avg_monthly_spend": 1000.0, "category_breakdown": {}, "top_merchants": []}
        (res,) = CardRecommendationService().recommend_next_card(profile, [], [card])
        # $100 bonus (10k pts @1c) + ongoing - $0 fee + $400 offer credit
        assert res["score"] > 400.0
