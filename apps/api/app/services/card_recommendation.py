from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from app.services.approval_odds import (
    ApprovalProfile,
    estimate_approval_odds,
    odds_label,
)

# Curated per-category ongoing-earn rates, keyed by upstream ``cardId`` (see
# ``app/data/card_category_rates.json`` and its README). Loaded once at import,
# DB-free, mirroring how ``card_bonuses`` stays a pure fetch/query layer. Keys
# beginning with ``_`` (e.g. ``_meta``) are documentation and skipped. Any load
# failure degrades gracefully to an empty table → the engine falls back to the
# flat model everywhere, exactly as before this slice.
_CATEGORY_RATES_PATH = Path(__file__).resolve().parent.parent / "data" / "card_category_rates.json"


def _load_category_rates() -> Dict[str, Dict[str, float]]:
    try:
        raw = json.loads(_CATEGORY_RATES_PATH.read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        card_id: rates
        for card_id, rates in raw.items()
        if not card_id.startswith("_") and isinstance(rates, dict)
    }


_CATEGORY_RATES: Dict[str, Dict[str, float]] = _load_category_rates()


class CardRecommendationService:
    """Pure-function recommendation engine. No DB dependency."""

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _card_key(name: str, issuer: str) -> str:
        return f"{name.lower()}|{issuer.upper()}"

    @staticmethod
    def _category_rate(card: dict, category: str) -> float:
        """Per-category ongoing-earn rate for ``card`` in ``category``, as a
        percent-equivalent.

        The single source of truth for the category earn lookup, shared by
        ``_ongoing_value`` (first-year earn) and ``best_card_per_category``
        (per-category "which card to use") so the two can never drift. Reads the
        curated rate from ``_CATEGORY_RATES`` (keyed by ``cardId``) and falls
        back to the card's flat ``universalCashbackPercent`` for any category the
        card doesn't curate — and for any card absent from the table (including a
        bare owned-card dict with no ``cardId``, which resolves to its flat rate,
        defaulting to 0 when unknown).
        """
        flat_pct = float(card.get("universalCashbackPercent", 0))
        card_id = card.get("cardId")
        rates = _CATEGORY_RATES.get(card_id, {}) if card_id else {}
        return float(rates.get(category, flat_pct))

    @staticmethod
    def _best_achievable_offer(
        card: dict,
        avg_monthly_spend: float,
        points_value_cents: float = 1.0,
    ) -> Optional[tuple[dict, float]]:
        """Return ``(offer, months_to_hit)`` for the highest-value offer the
        user can actually earn, or ``None`` if none is achievable.

        A card may list several **concurrent** offers — commonly a
        high-spend/high-bonus tier alongside a lower-spend/lower-bonus tier
        (27 of the 179 dataset cards do this, e.g. Delta SkyMiles Gold:
        90k pts @ $5,000/180d *or* 50k pts @ $2,000/180d). Picking the
        max-bonus offer *before* the achievability check wrongly drops the
        whole card for a lower-spend user who could still hit the smaller
        tier. So filter to the offers the user can reach first, then take the
        best-valued of those.

        Achievable means ``min_spend / avg_monthly_spend <= days / 30``. All
        other score terms (ongoing earn, fee, credits) are per-card constants,
        so among achievable offers the USD bonus value is the only
        differentiator — hence "best achievable" == "highest-value achievable".
        Requires ``avg_monthly_spend > 0`` (guarded by the caller).
        """
        best: Optional[tuple[dict, float]] = None
        best_val: Optional[float] = None
        for offer in card.get("offers", []):
            min_spend = float(offer.get("spend", 0))
            bonus_days = int(offer.get("days", 30))
            months_to_hit = min_spend / avg_monthly_spend
            if months_to_hit > bonus_days / 30:
                continue
            val = CardRecommendationService._bonus_value_usd(
                offer, points_value_cents, card.get("currency")
            )
            if best_val is None or val > best_val:
                best = (offer, months_to_hit)
                best_val = val
        return best

    @staticmethod
    def _amount_is_dollars(amount_currency: Optional[str], card_currency: Optional[str]) -> bool:
        """Decide whether a bonus ``amount`` entry is denominated in dollars.

        The upstream dataset denominates a bonus ``amount`` by the **card's**
        top-level ``currency`` (cash cards → ``"USD"``; points/miles cards → a
        program like ``"CHASE"``/``"AMEX_MR"``). The per-amount ``currency``
        field is present on only ~11 of 179 cards, so a field-less amount must
        inherit the card's denomination — otherwise a genuine dollar bonus on a
        ``currency: "USD"`` cashback card is mis-read as points and valued ~100×
        too low (issue #201; the bonus-path sibling of the #192 credit fix).

        Rule: an explicit ``"USD"`` tag is dollars; any explicit non-USD tag is
        points; a field-less amount inherits ``card_currency`` (dollars only
        when the card itself is ``"USD"``). ``card_currency=None`` is
        "unknown" — a field-less amount then falls back to the legacy points
        treatment so bare unit calls without card context are unaffected.
        """
        if amount_currency == "USD":
            return True
        if amount_currency is not None:
            return False
        return card_currency == "USD"

    @staticmethod
    def _bonus_value_usd(
        offer: dict,
        points_value_cents: float = 1.0,
        card_currency: Optional[str] = None,
    ) -> float:
        """Value a sign-up bonus in **dollars**.

        Each entry in ``offer["amount"]`` is either a cashback bonus (dollars,
        taken at face value) or a points/miles bonus (valued at
        ``points_value_cents`` per point). Denomination follows
        ``_amount_is_dollars``: an explicit ``currency`` on the amount wins,
        otherwise a field-less amount inherits ``card_currency`` (so a
        field-less amount on a ``currency: "USD"`` card is dollars, not points).
        """
        total = 0.0
        for a in offer.get("amount", []):
            amount = a.get("amount", 0)
            if CardRecommendationService._amount_is_dollars(
                a.get("currency"), card_currency
            ):
                total += float(amount)
            else:
                total += float(amount) * points_value_cents / 100.0
        return total

    @staticmethod
    def _bonus_points(offer: dict, card_currency: Optional[str] = None) -> float:
        """Sum of raw point/mile amounts for display.

        Excludes any amount that ``_amount_is_dollars`` classifies as dollars,
        so a field-less amount on a ``currency: "USD"`` card is **not** counted
        as points (which otherwise renders bogus "(250 pts @ 1.0¢)" copy for a
        "$250 back" bonus — issue #201).
        """
        return float(
            sum(
                a.get("amount", 0)
                for a in offer.get("amount", [])
                if not CardRecommendationService._amount_is_dollars(
                    a.get("currency"), card_currency
                )
            )
        )

    @staticmethod
    def _credit_entries_value(
        credits: list, points_value_cents: float = 1.0
    ) -> float:
        """Value a list of credit entries in **dollars**.

        An explicit non-USD ``currency`` marks a points/miles credit (valued at
        ``points_value_cents``); everything else — including a credit with no
        ``currency`` field at all — is dollars. Field-less credits in this
        dataset are statement credits, fee waivers and vouchers, which are
        dollar-denominated, so they must NOT inherit the card's points currency.
        """
        total = 0.0
        for c in credits or []:
            value = float(c.get("value", 0)) * float(c.get("weight", 1.0))
            currency = c.get("currency")
            if currency and currency != "USD":
                total += value * points_value_cents / 100.0
            else:
                total += value
        return total

    @staticmethod
    def _offer_credit_value(offer: dict, points_value_cents: float = 1.0) -> float:
        """Value credits attached to a specific sign-up offer (#202).

        These are first-year sweeteners — statement credits, waived annual fees,
        companion vouchers — and were previously dropped entirely from the
        ranking even though the objective is first-year value.
        """
        return CardRecommendationService._credit_entries_value(
            offer.get("credits"), points_value_cents
        )

    @staticmethod
    def _credit_value(card: dict, points_value_cents: float = 1.0) -> float:
        """Value recurring/anniversary credits in **dollars**.

        Like ``_bonus_value_usd``: a USD credit is taken at face value, while a
        credit denominated in points/miles (any non-USD ``currency``) is valued
        at ``points_value_cents`` per point. Without this, a 15,000-point
        anniversary credit was counted as $15,000 (not ~$150), which dominated
        the first-year-value ranking.
        """
        return CardRecommendationService._credit_entries_value(
            card.get("credits"), points_value_cents
        )

    @staticmethod
    def _first_year_fee(card: dict) -> float:
        """Annual fee actually paid in the **first year**, in dollars.

        The owner-confirmed objective ranks by *first-year* value, so a card
        whose annual fee is waived the first year (``isAnnualFeeWaived``) costs
        $0 in year one even though it lists a nonzero ``annualFee``. Applied in
        ``recommend_next_card`` (the apply-for-new first-year-value ranking).
        ``analyze_portfolio`` intentionally keeps the full recurring
        ``annualFee`` — it judges whether a *held* card is worth keeping in
        steady state, where the fee is paid every year, not just year one.
        """
        if card.get("isAnnualFeeWaived"):
            return 0.0
        return float(card.get("annualFee", 0))

    @staticmethod
    def _ongoing_value(
        card: dict,
        avg_monthly_spend: float,
        category_breakdown: Optional[Dict[str, float]] = None,
    ) -> float:
        """First-year ongoing rewards, in **dollars** — category-aware.

        Single source of truth for the earn model shared by
        ``recommend_next_card`` (apply-for-new) and ``analyze_portfolio``
        (held cards), so the two modes can't drift.

        Earn is driven by ``category_breakdown`` (monthly-average dollars per
        internal spending category, as built by ``spending_profile``): for each
        category the card's curated per-category rate is used
        (``app/data/card_category_rates.json``, keyed by ``cardId``), falling
        back to the card's flat ``universalCashbackPercent`` for any category
        the card doesn't curate.

        **Additive / non-regressive by construction.** A card with no curated
        rates — and any call without a ``category_breakdown`` — evaluates to
        exactly the old flat number ``avg_monthly_spend × 12 ×
        universalCashbackPercent / 100``, because ``sum(category_breakdown
        .values()) == avg_monthly_spend`` (both are total spend ÷ months) and
        every category then earns at the flat rate.
        """
        flat_pct: float = float(card.get("universalCashbackPercent", 0))
        card_id = card.get("cardId")
        rates = _CATEGORY_RATES.get(card_id, {}) if card_id else {}

        # No curated rates or no per-category breakdown → exact flat behavior.
        if not rates or not category_breakdown:
            return avg_monthly_spend * 12 * flat_pct / 100.0

        total = 0.0
        covered = 0.0
        for category, monthly in category_breakdown.items():
            rate = CardRecommendationService._category_rate(card, category)
            total += monthly * 12 * float(rate) / 100.0
            covered += monthly

        # Any spend not represented in the breakdown (shouldn't occur when the
        # profile is consistent, but guard against a truncated/rounded one)
        # earns at the flat rate so the total never silently under-counts.
        remainder = avg_monthly_spend - covered
        if remainder > 0:
            total += remainder * 12 * flat_pct / 100.0
        return total

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def recommend_next_card(
        self,
        profile: dict,
        user_cards: List[dict],
        available_cards: List[dict],
        max_results: int = 10,
        points_value_cents: float = 1.0,
        approval_profile: ApprovalProfile | None = None,
    ) -> List[dict]:
        """
        Rank available cards by sign-up bonus achievability.

        profile: {"avg_monthly_spend": float, "category_breakdown": dict, "top_merchants": list}
        user_cards: [{"name": str, "issuer": str, "network": str, "annual_fee": float}]
        available_cards: list of cards from the free API

        Logic:
        1. Skip discontinued cards, cards user already owns
           (matched by name.lower() + issuer.upper())
        2. Pick the best *achievable* offer per card (``_best_achievable_offer``):
           among the card's offers the user can hit
           (months_to_hit <= bonus_days/30), take the highest dollar-valued one.
           A card with multiple offer tiers is kept if *any* tier is achievable —
           not dropped just because its top tier is out of reach.
        3. Skip cards with no achievable offer
        4. bonus_value = dollar value of the chosen offer (USD entries at face
           value, points/miles at ``points_value_cents`` per point)
        5. months_to_hit = min_spend / avg_monthly_spend (for the chosen offer)
        6. ongoing_value = avg_monthly_spend * 12 * universalCashbackPercent/100
           (flat first-year earn, shared with analyze_portfolio)
        7. score = bonus_value + ongoing_value - first_year_fee + credit_value
           (all dollar-denominated; credits = sum(value * weight))
        8. Sort by score desc, return top max_results
        9. Each result includes an explanation string
        """
        avg_monthly_spend: float = profile.get("avg_monthly_spend", 0.0)
        category_breakdown: Dict[str, float] = profile.get("category_breakdown", {}) or {}

        owned_keys = {
            self._card_key(c.get("name", ""), c.get("issuer", ""))
            for c in user_cards
        }

        results: List[dict] = []

        # Without spend history no bonus is achievable — nothing to rank.
        if avg_monthly_spend <= 0:
            return results

        for card in available_cards:
            # 1a. Skip discontinued
            if card.get("discontinued", False):
                continue

            # 1b. Skip already-owned
            key = self._card_key(card.get("name", ""), card.get("issuer", ""))
            if key in owned_keys:
                continue

            # 2. Pick the best offer the user can actually hit. Cards with no
            #    offers — and cards whose every tier is out of reach at this
            #    spend — are skipped. A multi-tier card is kept whenever any
            #    tier is achievable (e.g. the smaller tier for a lower spender),
            #    not dropped because only its top tier is unachievable.
            selected = self._best_achievable_offer(
                card, avg_monthly_spend, points_value_cents
            )
            if selected is None:
                continue
            offer, months_to_hit = selected

            # 4. Bonus value (in dollars) and 5. spend terms of the chosen offer
            card_currency = card.get("currency")
            bonus_val = self._bonus_value_usd(offer, points_value_cents, card_currency)
            bonus_points = self._bonus_points(offer, card_currency)
            min_spend: float = float(offer.get("spend", 0))
            bonus_days: int = int(offer.get("days", 30))

            # 6. Ongoing rewards (category-aware first-year earn), shared with
            #    analyze_portfolio so the two modes can't drift.
            ongoing_val = self._ongoing_value(
                card, avg_monthly_spend, category_breakdown
            )

            # 7. Score. First-year fee is $0 when the card waives its annual
            #    fee the first year (isAnnualFeeWaived) — the objective is
            #    first-year value, so a waived fee must not be subtracted.
            annual_fee: float = float(card.get("annualFee", 0))
            first_year_fee = self._first_year_fee(card)
            credit_val = self._credit_value(card, points_value_cents)
            # Offer-attached credits are first-year value too (#202): statement
            # credits, waived fees and vouchers that only apply to this offer.
            offer_credit_val = self._offer_credit_value(offer, points_value_cents)
            credit_val += offer_credit_val
            score = bonus_val + ongoing_val - first_year_fee + credit_val

            # 8. Explanation (dollar-denominated; show the points conversion
            #    only when the bonus is actually in points)
            if bonus_points > 0:
                bonus_phrase = (
                    f"Earn ~${bonus_val:,.0f} in value "
                    f"({bonus_points:,.0f} pts @ {points_value_cents:.1f}¢)"
                )
            else:
                bonus_phrase = f"Earn ~${bonus_val:,.0f} in bonus value"
            annual_spend = avg_monthly_spend * 12
            if first_year_fee == 0 and annual_fee > 0:
                fee_clause = f"- fee $0 (${annual_fee:,.0f} waived year 1)"
            else:
                fee_clause = f"- fee ${first_year_fee:,.0f}"
            # Effective (blended) earn rate: identical to the flat cashback for
            # uncurated cards, and the true category-weighted rate for curated
            # ones — so the rationale never overstates a flat-rate card.
            effective_pct = (ongoing_val / annual_spend * 100) if annual_spend > 0 else 0.0
            explanation = (
                f"{bonus_phrase} by spending "
                f"${min_spend:,.0f} in {bonus_days} days. "
                f"Estimated first-year value: ${score:,.0f} "
                f"(bonus ${bonus_val:,.0f} + ongoing ${ongoing_val:,.0f} "
                f"({effective_pct:,.1f}% blended on ${annual_spend:,.0f}) "
                f"{fee_clause} + credits ${credit_val:,.0f})."
            )

            results.append(
                {
                    "card": card,
                    "score": score,
                    "bonus_value": bonus_val,
                    "ongoing_value": ongoing_val,
                    "months_to_hit": months_to_hit,
                    "achievable": True,
                    "explanation": explanation,
                }
            )

        # 7. Sort by score descending, return top N
        # Rank by EXPECTED value: headline first-year value discounted by the
        # estimated chance of approval. With no credit profile every card scores
        # odds 1.0, so this reduces exactly to the previous ranking.
        for r in results:
            odds, reason = estimate_approval_odds(r["card"], approval_profile)
            r["approval_odds"] = odds
            r["approval_label"] = odds_label(odds) if reason else None
            r["approval_reason"] = reason
            r["expected_value"] = round(r["score"] * odds, 2)
        results.sort(key=lambda r: r["expected_value"], reverse=True)
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
        category_breakdown: Dict[str, float] = profile.get("category_breakdown", {}) or {}

        # Cards the user already holds — alternatives must never suggest one of
        # these (you can't "switch to" a card you already own). Mirrors the
        # owned-card exclusion in recommend_next_card.
        owned_keys = {
            self._card_key(c.get("name", ""), c.get("issuer", ""))
            for c in user_cards
        }

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
                annual_fee: float = float(matched.get("annualFee", 0))
                credit_val = self._credit_value(matched)
                ongoing_val = self._ongoing_value(
                    matched, avg_monthly_spend, category_breakdown
                )
            else:
                annual_fee = float(user_card.get("annual_fee", 0))
                credit_val = 0.0
                ongoing_val = 0.0

            # 2. estimated_annual_value
            estimated_annual_value = ongoing_val + credit_val

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
                    # Only suggest cards the user can actually act on: skip
                    # discontinued cards (can't be applied for) and any card the
                    # user already owns (subsumes skipping the analyzed card,
                    # which is itself owned). Mirrors recommend_next_card.
                    if alt.get("discontinued", False):
                        continue
                    alt_key = self._card_key(alt.get("name", ""), alt.get("issuer", ""))
                    if alt_key in owned_keys:
                        continue
                    alt_fee = float(alt.get("annualFee", 0))
                    if alt_fee > annual_fee:
                        continue
                    alt_credit = self._credit_value(alt)
                    alt_annual_value = (
                        self._ongoing_value(alt, avg_monthly_spend, category_breakdown)
                        + alt_credit
                    )
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

    def best_card_per_category(
        self,
        profile: dict,
        user_cards: List[dict],
        available_cards: List[dict],
    ) -> List[dict]:
        """For each category the user actually spends in, pick the held card
        that earns the most there — the "use THIS card for dining, THAT one for
        groceries" guidance of PRD User Story 2.

        Pure function (no DB), so it stays inside the engine's cache-determinism
        contract. Reuses the exact same ``_card_key`` match + per-category rate
        lookup (``_category_rate``) that ``analyze_portfolio`` / ``_ongoing_value``
        use, so the "which card to use" answer can't diverge from the earn model.

        Returns ``[{category, best_card: {name, issuer}, rate, rationale}]`` for
        every internal category with positive spend in ``category_breakdown``,
        emitted in deterministic (sorted-category) order.

        Tie-break (documented, stable for the inputs-hash cache): highest
        per-category rate, then lowest annual fee, then case-insensitive name.
        """
        category_breakdown: Dict[str, float] = profile.get("category_breakdown", {}) or {}

        # Same available-card lookup analyze_portfolio builds.
        available_by_key: Dict[str, dict] = {}
        for ac in available_cards:
            k = self._card_key(ac.get("name", ""), ac.get("issuer", ""))
            available_by_key[k] = ac

        # Resolve each held card to the dict used for the rate lookup: the
        # matched dataset entry (carries ``cardId`` + curated rates) when known,
        # else the bare owned-card dict (flat ``universalCashbackPercent`` only,
        # i.e. 0 when the user stored no rate). Carry display name/issuer/fee
        # from the user's own record so output is stable regardless of match.
        resolved: List[dict] = []
        for uc in user_cards:
            key = self._card_key(uc.get("name", ""), uc.get("issuer", ""))
            matched = available_by_key.get(key)
            rate_card = matched if matched is not None else uc
            name = uc.get("name") or (matched or {}).get("name", "Card")
            issuer = uc.get("issuer") or (matched or {}).get("issuer", "")
            annual_fee = float(
                (matched or {}).get("annualFee", uc.get("annual_fee", 0)) or 0
            )
            resolved.append(
                {"rate_card": rate_card, "name": name, "issuer": issuer, "annual_fee": annual_fee}
            )

        if not resolved:
            return []

        assignments: List[dict] = []
        for category in sorted(category_breakdown):
            if category_breakdown.get(category, 0) <= 0:
                continue

            ranked = sorted(
                resolved,
                key=lambda r: (
                    -self._category_rate(r["rate_card"], category),
                    r["annual_fee"],
                    r["name"].lower(),
                ),
            )
            winner = ranked[0]
            winner_rate = self._category_rate(winner["rate_card"], category)
            next_rate = (
                self._category_rate(ranked[1]["rate_card"], category)
                if len(ranked) > 1
                else winner_rate
            )

            if len(ranked) == 1:
                rationale = (
                    f"Use {winner['name']} for {category} — {winner_rate:g}% "
                    f"(your only card)."
                )
            elif next_rate < winner_rate:
                rationale = (
                    f"Use {winner['name']} for {category} — {winner_rate:g}% "
                    f"vs {next_rate:g}% on your other cards."
                )
            else:
                rationale = (
                    f"Use {winner['name']} for {category} — {winner_rate:g}% "
                    f"(ties your other cards; lowest-fee card wins)."
                )

            assignments.append(
                {
                    "category": category,
                    "best_card": {"name": winner["name"], "issuer": winner["issuer"]},
                    "rate": winner_rate,
                    "rationale": rationale,
                }
            )

        return assignments
