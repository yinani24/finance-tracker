"""Tests for core/cards.py credit card intelligence engine."""

import json

import pytest

from core.cards import (
    CURATED_CARDS,
    compute_card_annual_value,
    compute_card_value_per_category,
    compute_missed_rewards,
    compute_optimal_card_per_category,
    compute_upgrade_recommendations,
    load_cards,
)


@pytest.fixture
def csp():
    return {
        "name": "Chase Sapphire Preferred",
        "issuer": "Chase",
        "annual_fee": 95,
        "reward_type": "points",
        "points_cpp": 0.0125,
        "rewards": {
            "Food & Dining": 3.0,
            "Transport": 2.0,
            "Subscriptions": 1.0,
            "Shopping": 1.0,
            "Health": 1.0,
            "Other": 1.0,
        },
    }


@pytest.fixture
def quicksilver():
    return {
        "name": "Quicksilver",
        "issuer": "Capital One",
        "annual_fee": 0,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {
            "Food & Dining": 1.5,
            "Transport": 1.5,
            "Subscriptions": 1.5,
            "Shopping": 1.5,
            "Health": 1.5,
            "Other": 1.5,
        },
    }


class TestLoadCards:
    def test_missing_file_returns_empty(self, tmp_path):
        result = load_cards(str(tmp_path / "cards.json"))
        assert result == {"cards": []}

    def test_loads_existing_file(self, tmp_path):
        data = {"cards": [{"name": "Test Card"}]}
        (tmp_path / "cards.json").write_text(json.dumps(data))
        result = load_cards(str(tmp_path / "cards.json"))
        assert result["cards"][0]["name"] == "Test Card"


class TestComputeCardValuePerCategory:
    def test_correct_arithmetic(self, csp):
        # 3.0 × 0.0125 × 4200 = 157.50
        result = compute_card_value_per_category(csp, "Food & Dining", 4200.0)
        assert result == pytest.approx(157.50)

    def test_fallback_to_other(self, csp):
        # "Entertainment" not in rewards → Other rate (1.0 × 0.0125 × 1200 = 15.0)
        result = compute_card_value_per_category(csp, "Entertainment", 1200.0)
        assert result == pytest.approx(15.0)

    def test_fallback_to_zero_when_other_absent(self):
        card = {"rewards": {"Food & Dining": 3.0}, "points_cpp": 0.01}
        result = compute_card_value_per_category(card, "Transport", 1000.0)
        assert result == pytest.approx(0.0)


class TestComputeOptimalCardPerCategory:
    def test_single_card_returns_itself(self, csp):
        result = compute_optimal_card_per_category([csp], {"Food & Dining": 4200.0})
        assert len(result) == 1
        assert result[0]["best_card"] == "Chase Sapphire Preferred"

    def test_multiple_cards_picks_highest_earner(self, csp, quicksilver):
        spending = {"Food & Dining": 4200.0, "Subscriptions": 500.0}
        result = compute_optimal_card_per_category([csp, quicksilver], spending)
        food = next(r for r in result if r["category"] == "Food & Dining")
        subs = next(r for r in result if r["category"] == "Subscriptions")
        # CSP dining: 3×0.0125=3.75% > QS 1.5×0.01=1.5% → CSP wins
        assert food["best_card"] == "Chase Sapphire Preferred"
        # QS subs: 1.5×0.01=1.5% > CSP 1.0×0.0125=1.25% → QS wins
        assert subs["best_card"] == "Quicksilver"

    def test_returns_sorted_by_annual_gain_descending(self, csp, quicksilver):
        spending = {"Food & Dining": 4200.0, "Subscriptions": 500.0}
        result = compute_optimal_card_per_category([csp, quicksilver], spending)
        gains = [r["annual_gain"] for r in result]
        assert gains == sorted(gains, reverse=True)

    def test_empty_cards_returns_empty(self):
        assert compute_optimal_card_per_category([], {"Food & Dining": 100.0}) == []

    def test_effective_pct_is_correct(self, csp):
        result = compute_optimal_card_per_category([csp], {"Food & Dining": 4200.0})
        # 3.0 × 0.0125 × 100 = 3.75%
        assert result[0]["effective_pct"] == pytest.approx(3.75)


class TestComputeCardAnnualValue:
    def test_net_value_is_gross_minus_fee(self, csp):
        result = compute_card_annual_value(csp, {"Food & Dining": 4200.0})
        assert result["name"] == "Chase Sapphire Preferred"
        assert result["gross_rewards"] == pytest.approx(157.50)
        assert result["annual_fee"] == 95
        assert result["net_value"] == pytest.approx(62.50)

    def test_zero_fee_card(self, quicksilver):
        result = compute_card_annual_value(quicksilver, {"Food & Dining": 1000.0})
        assert result["annual_fee"] == 0
        # 1.5 × 0.01 × 1000 = 15.0
        assert result["gross_rewards"] == pytest.approx(15.0)
        assert result["net_value"] == pytest.approx(15.0)


class TestComputeMissedRewards:
    def test_single_card_is_zero(self, csp):
        result = compute_missed_rewards({"Food & Dining": 4200.0}, [csp])
        assert result == pytest.approx(0.0)

    def test_empty_cards_is_zero(self):
        assert compute_missed_rewards({"Food & Dining": 1000.0}, []) == pytest.approx(0.0)

    def test_detects_missed_value(self):
        default_card = {
            "name": "Default",
            "annual_fee": 0,
            "points_cpp": 0.01,
            "rewards": {"Food & Dining": 1.0, "Transport": 1.0, "Other": 1.0},
        }
        better_card = {
            "name": "Better",
            "annual_fee": 0,
            "points_cpp": 0.01,
            "rewards": {"Food & Dining": 3.0, "Transport": 1.0, "Other": 1.0},
        }
        spending = {"Food & Dining": 1200.0, "Transport": 600.0}
        result = compute_missed_rewards(spending, [default_card, better_card])
        # Food: Better=3×0.01×1200=36 vs Default=1×0.01×1200=12 → missed=24
        # Transport: equal → missed=0
        assert result == pytest.approx(24.0)


class TestComputeUpgradeRecommendations:
    def test_empty_user_cards_returns_empty(self):
        assert compute_upgrade_recommendations({"Food & Dining": 5000.0}, []) == []

    def test_returns_at_most_two(self):
        basic = {
            "name": "Basic",
            "annual_fee": 0,
            "points_cpp": 0.01,
            "rewards": {"Food & Dining": 1.0, "Other": 1.0},
        }
        result = compute_upgrade_recommendations({"Food & Dining": 5000.0}, [basic])
        assert len(result) <= 2

    def test_sorted_by_gain_over_best_descending(self):
        basic = {
            "name": "Basic",
            "annual_fee": 0,
            "points_cpp": 0.01,
            "rewards": {"Food & Dining": 1.0, "Other": 1.0},
        }
        recs = compute_upgrade_recommendations({"Food & Dining": 5000.0}, [basic])
        gains = [r["gain_over_best"] for r in recs]
        assert gains == sorted(gains, reverse=True)

    def test_excludes_owned_cards(self):
        cfu = {
            "name": "Chase Freedom Unlimited",
            "annual_fee": 0,
            "points_cpp": 0.01,
            "rewards": {"Food & Dining": 3.0, "Other": 1.5},
        }
        basic = {"name": "Basic", "annual_fee": 0, "points_cpp": 0.01, "rewards": {"Other": 1.0}}
        recs = compute_upgrade_recommendations({"Food & Dining": 5000.0}, [basic, cfu])
        assert all(r["name"].lower() != "chase freedom unlimited" for r in recs)

    def test_no_gain_returns_empty(self):
        super_card = {
            "name": "Super Card",
            "annual_fee": 0,
            "points_cpp": 0.01,
            "rewards": {"Food & Dining": 10.0, "Other": 10.0},
        }
        recs = compute_upgrade_recommendations({"Food & Dining": 100.0}, [super_card])
        assert recs == []

    def test_why_field_is_non_empty_string(self):
        basic = {
            "name": "Basic",
            "annual_fee": 0,
            "points_cpp": 0.01,
            "rewards": {"Food & Dining": 1.0, "Other": 1.0},
        }
        recs = compute_upgrade_recommendations({"Food & Dining": 5000.0}, [basic])
        for r in recs:
            assert isinstance(r["why"], str) and len(r["why"]) > 0


class TestCuratedCards:
    def test_has_eight_cards(self):
        assert len(CURATED_CARDS) == 8

    def test_all_have_required_fields(self):
        required = {"name", "issuer", "annual_fee", "reward_type", "points_cpp", "rewards"}
        for card in CURATED_CARDS:
            assert required.issubset(set(card.keys()))

    def test_all_have_other_in_rewards(self):
        for card in CURATED_CARDS:
            assert "Other" in card["rewards"], f"{card['name']} missing 'Other' in rewards"
