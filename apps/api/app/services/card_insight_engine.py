from __future__ import annotations

import hashlib
import json
import time
from typing import Dict, List, Literal

import httpx

from app.models.insight import Insight
from app.services.card_recommendation import CardRecommendationService
from app.services.insight_types import (
    EngineContext,
    EngineEvent,
    InsightDraft,
)

DATA_URL = "https://raw.githubusercontent.com/andenacitelli/credit-card-bonuses-api/main/exports/data.json"
CACHE_TTL_SECONDS = 3600

_cache: Dict[str, object] = {"data": None, "fetched_at": 0.0}


def fetch_card_bonuses() -> List[dict]:
    now = time.time()
    if _cache["data"] is not None and now - _cache["fetched_at"] < CACHE_TTL_SECONDS:
        return _cache["data"]
    resp = httpx.get(DATA_URL, timeout=15)
    resp.raise_for_status()
    cards = resp.json()
    _cache["data"] = cards
    _cache["fetched_at"] = now
    return cards


def _hash_inputs(profile_json: str, cards_json: str, kind: str) -> str:
    raw = f"{kind}|{profile_json}|{cards_json}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class CardInsightEngine:
    name = "card"

    def relevant_events(self) -> set[EngineEvent]:
        return {
            EngineEvent.TRANSACTIONS_SYNCED,
            EngineEvent.TRANSACTION_MUTATED,
            EngineEvent.CARD_MUTATED,
            EngineEvent.USER_ONBOARDED,
        }

    def generate(self, user_id: int, ctx: EngineContext) -> list[InsightDraft]:
        if not ctx.spending_profile:
            return []

        profile_dict = {
            "avg_monthly_spend": ctx.spending_profile.avg_monthly_spend,
            "category_breakdown": json.loads(ctx.spending_profile.category_breakdown_json),
            "top_merchants": json.loads(ctx.spending_profile.top_merchants_json),
        }
        user_cards = [
            {
                "name": c.name,
                "issuer": c.issuer or "",
                "network": c.network,
                "annual_fee": c.annual_fee,
            }
            for c in ctx.cards
        ]

        available_cards = fetch_card_bonuses()
        svc = CardRecommendationService()
        drafts: list[InsightDraft] = []

        profile_json = json.dumps(profile_dict, sort_keys=True)
        cards_json = json.dumps(user_cards, sort_keys=True)

        next_cards = svc.recommend_next_card(profile_dict, user_cards, available_cards, max_results=5)
        for rec in next_cards:
            card = rec["card"]
            bonus_val = rec["bonus_value"]
            drafts.append(InsightDraft(
                kind="next_card",
                title=f"Apply for {card.get('name', 'card')}",
                body=rec["explanation"],
                impact_one_time_cents=int(bonus_val * 100),
                impact_annual_cents=0,
                effort="medium",
                evidence={
                    "summary": rec["explanation"],
                    "data_points": [
                        {"label": "Sign-up bonus", "value": f"{bonus_val:,.0f} pts"},
                        {"label": "Score", "value": f"{rec['score']:,.0f}"},
                        {"label": "Months to hit", "value": f"{rec['months_to_hit']:.1f}"},
                    ],
                },
                action={
                    "label": "View card",
                    "kind": "external",
                    "target": card.get("url", ""),
                } if card.get("url") else None,
                related_goal_id=None,
                inputs_hash=_hash_inputs(profile_json, cards_json, f"next_card_{card.get('name', '')}"),
            ))

        portfolio = svc.analyze_portfolio(profile_dict, user_cards, available_cards)
        for analysis in portfolio:
            if analysis["status"] in ("underperforming", "costing_money"):
                card_name = analysis["user_card"].get("name", "Card")
                kind = f"portfolio_{analysis['status']}"
                drafts.append(InsightDraft(
                    kind=kind,
                    title=f"{card_name} is {analysis['status'].replace('_', ' ')}",
                    body=analysis["explanation"],
                    impact_one_time_cents=0,
                    impact_annual_cents=int(abs(analysis["net_value"]) * 100),
                    effort="high",
                    evidence={
                        "summary": analysis["explanation"],
                        "data_points": [
                            {"label": "Annual value", "value": f"${analysis['estimated_annual_value']:,.2f}"},
                            {"label": "Annual fee", "value": f"${analysis['user_card'].get('annual_fee', 0):,.2f}"},
                            {"label": "Net value", "value": f"${analysis['net_value']:,.2f}"},
                        ],
                    },
                    action=None,
                    related_goal_id=None,
                    inputs_hash=_hash_inputs(profile_json, cards_json, f"portfolio_{card_name}"),
                ))

        return drafts

    def detect_resolution(
        self, old_insight: Insight, ctx: EngineContext
    ) -> Literal["acted_on", "expired", "still_active"]:
        return "expired"
