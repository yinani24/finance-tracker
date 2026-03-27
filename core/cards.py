"""Credit card intelligence engine: optimizer, value computation, and upgrade recommendations."""
from __future__ import annotations
import json
import os

CURATED_CARDS: list[dict] = [
    {
        "name": "Amex Gold",
        "issuer": "American Express",
        "annual_fee": 250,
        "reward_type": "points",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 4.0, "Transport": 1.0, "Shopping": 4.0,
                    "Subscriptions": 1.0, "Health": 1.0, "Other": 1.0},
    },
    {
        "name": "Chase Freedom Unlimited",
        "issuer": "Chase",
        "annual_fee": 0,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 3.0, "Transport": 1.5, "Shopping": 1.5,
                    "Subscriptions": 1.5, "Health": 1.5, "Other": 1.5},
    },
    {
        "name": "Citi Double Cash",
        "issuer": "Citi",
        "annual_fee": 0,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 2.0, "Transport": 2.0, "Shopping": 2.0,
                    "Subscriptions": 2.0, "Health": 2.0, "Other": 2.0},
    },
    {
        "name": "Capital One Venture X",
        "issuer": "Capital One",
        "annual_fee": 395,
        "reward_type": "miles",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 2.0, "Transport": 10.0, "Shopping": 2.0,
                    "Subscriptions": 2.0, "Health": 2.0, "Other": 2.0},
    },
    {
        "name": "Chase Freedom Flex",
        "issuer": "Chase",
        "annual_fee": 0,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 3.0, "Transport": 1.0, "Shopping": 5.0,
                    "Subscriptions": 1.0, "Health": 1.0, "Other": 1.0},
    },
    {
        "name": "Amex Blue Cash Preferred",
        "issuer": "American Express",
        "annual_fee": 95,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 3.0, "Transport": 3.0, "Shopping": 6.0,
                    "Subscriptions": 6.0, "Health": 1.0, "Other": 1.0},
    },
    {
        "name": "Wells Fargo Active Cash",
        "issuer": "Wells Fargo",
        "annual_fee": 0,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 2.0, "Transport": 2.0, "Shopping": 2.0,
                    "Subscriptions": 2.0, "Health": 2.0, "Other": 2.0},
    },
    {
        "name": "Discover it",
        "issuer": "Discover",
        "annual_fee": 0,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 5.0, "Transport": 1.0, "Shopping": 5.0,
                    "Subscriptions": 1.0, "Health": 1.0, "Other": 1.0},
    },
]


def load_cards(cards_path: str) -> dict:
    """Load card profiles from cards.json. Returns {"cards": []} if file does not exist."""
    if not os.path.exists(cards_path):
        return {"cards": []}
    with open(cards_path) as f:
        return json.load(f)


def compute_card_value_per_category(card: dict, category: str, annual_spend: float) -> float:
    """Return the annual reward value in dollars for a card in a specific spending category.

    Uses the card's reward rate for the category, falling back to "Other", then 0.0.
    annual_spend is the annualised spend (monthly_avg × 12).
    """
    rate = card["rewards"].get(category, card["rewards"].get("Other", 0.0))
    return round(annual_spend * rate * card["points_cpp"], 2)


def compute_optimal_card_per_category(cards: list, spending_by_category: dict) -> list:
    """For each category, find the card that maximises annual reward value.

    Returns list of dicts sorted by annual_gain (vs cards[0] default) descending:
    [{"category": str, "best_card": str, "annual_gain": float, "effective_pct": float}]
    """
    if not cards:
        return []
    default_card = cards[0]
    result = []
    for cat, annual_spend in spending_by_category.items():
        best = max(cards, key=lambda c: compute_card_value_per_category(c, cat, annual_spend))
        best_value = compute_card_value_per_category(best, cat, annual_spend)
        default_value = compute_card_value_per_category(default_card, cat, annual_spend)
        rate = best["rewards"].get(cat, best["rewards"].get("Other", 0.0))
        result.append({
            "category": cat,
            "best_card": best["name"],
            "annual_gain": round(best_value - default_value, 2),
            "effective_pct": round(rate * best["points_cpp"] * 100, 2),
        })
    return sorted(result, key=lambda x: x["annual_gain"], reverse=True)


def compute_card_annual_value(card: dict, spending_by_category: dict) -> dict:
    """Compute gross rewards, annual fee, and net value for a card.

    Returns {"name": str, "gross_rewards": float, "annual_fee": float, "net_value": float}.
    """
    gross = round(
        sum(compute_card_value_per_category(card, cat, spend)
            for cat, spend in spending_by_category.items()),
        2,
    )
    fee = card.get("annual_fee", 0)
    return {
        "name": card["name"],
        "gross_rewards": gross,
        "annual_fee": fee,
        "net_value": round(gross - fee, 2),
    }


def compute_missed_rewards(spending_by_category: dict, cards: list) -> float:
    """Annual dollars left on the table by always using cards[0] instead of the optimal card.

    Returns 0.0 when cards is empty or has only one card.
    """
    if len(cards) <= 1:
        return 0.0
    optimal = compute_optimal_card_per_category(cards, spending_by_category)
    return round(sum(max(item["annual_gain"], 0.0) for item in optimal), 2)


def compute_upgrade_recommendations(spending_by_category: dict, user_cards: list) -> list:
    """Return up to 2 CURATED_CARDS that improve on the user's best current card net value.

    Returns [] when user_cards is empty (no baseline to compare against).
    Each result dict: {"name", "annual_fee", "net_value", "gain_over_best", "why"}.
    """
    if not user_cards:
        return []

    owned = {c["name"].lower() for c in user_cards}
    user_best_net = max(
        compute_card_annual_value(c, spending_by_category)["net_value"] for c in user_cards
    )

    sorted_cats = sorted(spending_by_category.items(), key=lambda x: x[1], reverse=True)

    recs = []
    for curated in CURATED_CARDS:
        if curated["name"].lower() in owned:
            continue
        net = compute_card_annual_value(curated, spending_by_category)["net_value"]
        gain = round(net - user_best_net, 2)
        if gain <= 0:
            continue
        why = ""
        if sorted_cats:
            top_cat, top_annual = sorted_cats[0]
            rate = curated["rewards"].get(top_cat, curated["rewards"].get("Other", 0.0))
            why = f"{rate:g}x on {top_cat} — your #1 category at ${top_annual / 12:.0f}/mo"
        recs.append({
            "name": curated["name"],
            "annual_fee": curated["annual_fee"],
            "net_value": round(net, 2),
            "gain_over_best": gain,
            "why": why,
        })

    recs.sort(key=lambda x: x["gain_over_best"], reverse=True)
    return recs[:2]
