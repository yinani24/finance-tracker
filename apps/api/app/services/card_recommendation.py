from __future__ import annotations

from typing import Dict, List, Optional


class CardRecommendationService:
    """Pure-function recommendation engine. No DB dependency."""

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _card_key(name: str, issuer: str) -> str:
        return f"{name.lower()}|{issuer.upper()}"

    @staticmethod
    def _best_offer(card: dict) -> Optional[dict]:
        """Return the offer with the highest total bonus amount, or None."""
        offers: List[dict] = card.get("offers", [])
        if not offers:
            return None
        return max(offers, key=lambda o: sum(a.get("amount", 0) for a in o.get("amount", [])))

    @staticmethod
    def _bonus_value(offer: dict) -> float:
        return float(sum(a.get("amount", 0) for a in offer.get("amount", [])))

    @staticmethod
    def _credit_value(card: dict) -> float:
        credits: List[dict] = card.get("credits", [])
        return float(sum(c.get("value", 0) * c.get("weight", 1.0) for c in credits))

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def recommend_next_card(
        self,
        profile: dict,
        user_cards: List[dict],
        available_cards: List[dict],
        max_results: int = 10,
    ) -> List[dict]:
        """
        Rank available cards by sign-up bonus achievability.

        profile: {"avg_monthly_spend": float, "category_breakdown": dict, "top_merchants": list}
        user_cards: [{"name": str, "issuer": str, "network": str, "annual_fee": float}]
        available_cards: list of cards from the free API

        Logic:
        1. Skip discontinued cards, cards with no offers, cards user already owns
           (matched by name.lower() + issuer.upper())
        2. For best offer on each card: bonus_value = sum of amount fields
        3. months_to_hit = min_spend / avg_monthly_spend
        4. achievable = months_to_hit <= (bonus_days / 30)
        5. Skip non-achievable
        6. score = bonus_value - first_year_fee + credit_value
           (credits = sum(value * weight))
        7. Sort by score desc, return top max_results
        8. Each result includes an explanation string
        """
        avg_monthly_spend: float = profile.get("avg_monthly_spend", 0.0)

        owned_keys = {
            self._card_key(c.get("name", ""), c.get("issuer", ""))
            for c in user_cards
        }

        results: List[dict] = []

        for card in available_cards:
            # 1a. Skip discontinued
            if card.get("discontinued", False):
                continue

            # 1b. Skip already-owned
            key = self._card_key(card.get("name", ""), card.get("issuer", ""))
            if key in owned_keys:
                continue

            # 1c. Skip cards with no offers
            offer = self._best_offer(card)
            if offer is None:
                continue

            # 2. Bonus value
            bonus_val = self._bonus_value(offer)

            # 3. months_to_hit
            min_spend: float = float(offer.get("spend", 0))
            bonus_days: int = int(offer.get("days", 30))

            if avg_monthly_spend <= 0:
                continue

            months_to_hit = min_spend / avg_monthly_spend

            # 4. achievability check
            if months_to_hit > bonus_days / 30:
                continue

            # 6. Score
            annual_fee: float = float(card.get("annualFee", 0))
            credit_val = self._credit_value(card)
            score = bonus_val - annual_fee + credit_val

            # 8. Explanation
            explanation = (
                f"Earn {bonus_val:,.0f} bonus points by spending "
                f"${min_spend:,.0f} in {bonus_days} days. "
                f"Estimated score: {score:,.0f} "
                f"(bonus {bonus_val:,.0f} - fee {annual_fee:,.0f} + credits {credit_val:,.0f})."
            )

            results.append(
                {
                    "card": card,
                    "score": score,
                    "bonus_value": bonus_val,
                    "months_to_hit": months_to_hit,
                    "achievable": True,
                    "explanation": explanation,
                }
            )

        # 7. Sort by score descending, return top N
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:max_results]

    def analyze_portfolio(
        self,
        profile: dict,
        user_cards: List[dict],
        available_cards: List[dict],
    ) -> List[dict]:
        """
        Analyze user's current cards for value.

        For each user card:
        1. Find matching card in available_cards by name/issuer
        2. estimated_annual_value = avg_monthly_spend * 12 * universalCashbackPercent/100
                                    + sum(credit.value * credit.weight)
        3. net_value = estimated_annual_value - annual_fee
        4. status: "good" (net > 0),
                   "underperforming" (0 < net < fee*0.5 and fee > 0),
                   "costing_money" (net < 0)
        5. For non-good cards: find alternatives with lower/equal fee and better net value
        6. Return list with explanation strings
        """
        avg_monthly_spend: float = profile.get("avg_monthly_spend", 0.0)

        # Build lookup for available cards
        available_by_key: Dict[str, dict] = {}
        for ac in available_cards:
            k = self._card_key(ac.get("name", ""), ac.get("issuer", ""))
            available_by_key[k] = ac

        output: List[dict] = []

        for user_card in user_cards:
            key = self._card_key(user_card.get("name", ""), user_card.get("issuer", ""))
            matched = available_by_key.get(key)

            if matched is not None:
                cashback_pct: float = float(matched.get("universalCashbackPercent", 0))
                annual_fee: float = float(matched.get("annualFee", 0))
                credit_val = self._credit_value(matched)
            else:
                cashback_pct = 0.0
                annual_fee = float(user_card.get("annual_fee", 0))
                credit_val = 0.0

            # 2. estimated_annual_value
            estimated_annual_value = (
                avg_monthly_spend * 12 * cashback_pct / 100.0
            ) + credit_val

            # 3. net_value
            net_value = estimated_annual_value - annual_fee

            # 4. status
            if net_value > 0:
                if annual_fee > 0 and net_value < annual_fee * 0.5:
                    status = "underperforming"
                else:
                    status = "good"
            else:
                status = "costing_money"

            explanation = (
                f"{user_card.get('name', 'Card')}: estimated annual value "
                f"${estimated_annual_value:,.2f}, annual fee ${annual_fee:,.2f}, "
                f"net value ${net_value:,.2f} → {status}."
            )

            # 5. Alternatives for non-good cards
            alternatives: List[dict] = []
            if status != "good":
                for alt in available_cards:
                    alt_key = self._card_key(alt.get("name", ""), alt.get("issuer", ""))
                    if alt_key == key:
                        continue
                    alt_fee = float(alt.get("annualFee", 0))
                    if alt_fee > annual_fee:
                        continue
                    alt_cashback = float(alt.get("universalCashbackPercent", 0))
                    alt_credit = self._credit_value(alt)
                    alt_annual_value = avg_monthly_spend * 12 * alt_cashback / 100.0 + alt_credit
                    alt_net = alt_annual_value - alt_fee
                    if alt_net > net_value:
                        alternatives.append(
                            {
                                "card": alt,
                                "net_value": alt_net,
                                "explanation": (
                                    f"{alt.get('name', 'Card')} offers net value "
                                    f"${alt_net:,.2f} vs your current ${net_value:,.2f}."
                                ),
                            }
                        )
                alternatives.sort(key=lambda a: a["net_value"], reverse=True)

            output.append(
                {
                    "user_card": user_card,
                    "matched_card": matched,
                    "estimated_annual_value": estimated_annual_value,
                    "net_value": net_value,
                    "status": status,
                    "explanation": explanation,
                    "alternatives": alternatives,
                }
            )

        return output
