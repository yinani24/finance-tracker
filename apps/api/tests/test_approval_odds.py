from app.services.approval_odds import (
    ApprovalProfile,
    band_for_score,
    card_tier,
    estimate_approval_odds,
    odds_label,
)
from app.services.card_recommendation import CardRecommendationService

PREMIUM = {"cardId": "p", "name": "Premium", "issuer": "AMERICAN_EXPRESS", "annualFee": 695}
MID = {"cardId": "m", "name": "Mid", "issuer": "CITI", "annualFee": 95}
ENTRY = {"cardId": "e", "name": "Entry", "issuer": "CITI", "annualFee": 0}
CHASE = {"cardId": "c", "name": "Chase Card", "issuer": "CHASE", "annualFee": 95}


class TestBandsAndTiers:
    def test_score_to_band(self):
        assert band_for_score(780) == "excellent"
        assert band_for_score(700) == "good"
        assert band_for_score(600) == "fair"
        assert band_for_score(500) == "poor"
        assert band_for_score(None) is None

    def test_tier_from_annual_fee(self):
        assert card_tier(PREMIUM) == "premium"
        assert card_tier(MID) == "mid"
        assert card_tier(ENTRY) == "entry"


class TestEstimateApprovalOdds:
    def test_no_profile_is_a_noop(self):
        # Without a credit profile we must not invent odds — ranking is unchanged.
        odds, reason = estimate_approval_odds(PREMIUM, None)
        assert odds == 1.0 and reason is None

    def test_premium_card_is_unlikely_on_a_weak_profile(self):
        strong, _ = estimate_approval_odds(PREMIUM, ApprovalProfile.from_score(790))
        weak, _ = estimate_approval_odds(PREMIUM, ApprovalProfile.from_score(600))
        assert strong > 0.7 and weak < 0.2

    def test_entry_card_stays_attainable_on_a_weak_profile(self):
        odds, _ = estimate_approval_odds(ENTRY, ApprovalProfile.from_score(600))
        assert odds > 0.5

    def test_issuer_velocity_rule_dominates(self):
        # Chase 5/24: excellent credit still isn't enough past the threshold.
        profile = ApprovalProfile.from_score(800, recent_applications=6)
        odds, reason = estimate_approval_odds(CHASE, profile)
        assert odds < 0.1
        assert "24 months" in reason

    def test_business_cards_are_discounted(self):
        p = ApprovalProfile.from_score(790)
        personal, _ = estimate_approval_odds(MID, p)
        business, _ = estimate_approval_odds({**MID, "isBusiness": True}, p)
        assert business < personal

    def test_label_never_claims_false_precision(self):
        assert odds_label(0.9) == "excellent"
        assert odds_label(0.6) == "good"
        assert odds_label(0.3) == "fair"
        assert odds_label(0.05) == "poor"


class TestRankingUsesExpectedValue:
    def _cards(self):
        mk = lambda cid, fee, bonus: {  # noqa: E731
            "cardId": cid, "name": cid, "issuer": "CITI", "network": "VISA",
            "currency": "PTS", "isBusiness": False, "annualFee": fee,
            "isAnnualFeeWaived": False, "universalCashbackPercent": 1,
            "credits": [], "discontinued": False,
            "offers": [{"spend": 500, "days": 90, "amount": [{"amount": bonus}], "credits": []}],
        }
        # The premium card has the bigger headline bonus.
        return [mk("premium", 695, 120000), mk("entry", 0, 40000)]

    def _profile(self):
        return {"avg_monthly_spend": 2000.0, "category_breakdown": {}, "top_merchants": []}

    def test_without_profile_headline_value_wins(self):
        res = CardRecommendationService().recommend_next_card(
            self._profile(), [], self._cards()
        )
        assert res[0]["card"]["cardId"] == "premium"
        assert res[0]["approval_odds"] == 1.0

    def test_weak_credit_demotes_the_unattainable_premium_card(self):
        res = CardRecommendationService().recommend_next_card(
            self._profile(), [], self._cards(),
            approval_profile=ApprovalProfile.from_score(600),
        )
        # Still the richer card on paper, but not the one to actually apply for.
        assert res[0]["card"]["cardId"] == "entry"
        assert res[0]["expected_value"] < res[0]["score"]
        assert res[0]["approval_label"] in {"excellent", "good", "fair", "poor"}
