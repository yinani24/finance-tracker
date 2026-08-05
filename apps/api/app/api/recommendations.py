from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.config import settings
from app.database import get_db
from app.services.approval_odds import ApprovalProfile
from app.services.card_recommendation import CardRecommendationService
from app.services.recommendation_snapshot import (
    RecommendationSnapshotService,
    _fetch_cards,
)
from app.services.spending_profile import _months_spanned, get_or_refresh

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/next-card")
def get_next_card(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    service = RecommendationSnapshotService(db)
    return service.get_recommendations(user_id, "next_card")


@router.get("/portfolio")
def get_portfolio(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    service = RecommendationSnapshotService(db)
    return service.get_recommendations(user_id, "portfolio_gap")


@router.get("/combination")
def get_combination(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """Optimal SET of cards (held + new) that maximizes total first-year value
    (recommendation-engine slice 5, #185). Routes each spending category to its
    best card across held + candidate-new cards and recommends the new card(s)
    whose marginal first-year value is positive."""
    service = RecommendationSnapshotService(db)
    return service.get_recommendations(user_id, "combination")


@router.get("/spending-profile")
def get_spending_profile(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    profile = get_or_refresh(db, user_id)

    breakdown = json.loads(profile.category_breakdown_json)
    counts = json.loads(profile.category_counts_json)
    # Reuse the exact divisor compute_profile used, so monthly-avg-count and
    # avg-per-txn stay consistent with the stored monthly-avg dollars.
    months = _months_spanned(profile.period_start, profile.period_end)

    categories = []
    for cat, monthly_avg in breakdown.items():
        cnt = counts.get(cat, 0)
        # Reconstruct total $ from the stored monthly average to derive avg ticket.
        monthly_total = monthly_avg * months
        categories.append(
            {
                "category": cat,
                "monthly_avg": monthly_avg,  # unchanged key
                "count": cnt,
                "monthly_avg_count": round(cnt / months, 2),
                "avg_per_txn": round(monthly_total / cnt, 2) if cnt else 0.0,
            }
        )

    dining = next((c for c in categories if c["category"] == "dining"), None)

    return {
        "user_id": profile.user_id,
        "period_start": str(profile.period_start),
        "period_end": str(profile.period_end),
        "avg_monthly_spend": profile.avg_monthly_spend,
        "categories": categories,
        "dining": dining,
        "top_merchants": json.loads(profile.top_merchants_json),
        "computed_at": str(profile.computed_at),
    }


@router.post("/refresh")
def refresh_recommendations(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    service = RecommendationSnapshotService(db)
    service.invalidate(user_id)
    service.get_recommendations(user_id, "next_card")
    service.get_recommendations(user_id, "portfolio_gap")
    service.get_recommendations(user_id, "combination")
    return {"status": "refreshed"}


class StatelessCard(BaseModel):
    """A card the user holds, as read out of their own statement."""

    name: str
    issuer: str | None = None
    annual_fee: float = 0.0


class StatelessProfileRequest(BaseModel):
    """Aggregates the browser derived from statements it parsed locally.

    Deliberately aggregate-only: monthly spend and a category breakdown are
    enough for the ranking engine, so no merchant names, dates, amounts or
    account numbers ever leave the user's device. Nothing here is written to the
    database — the request is computed and discarded.
    """

    avg_monthly_spend: float = 0.0
    category_breakdown: dict[str, float] = Field(default_factory=dict)
    held_cards: list[StatelessCard] = Field(default_factory=list)
    credit_score_band: str | None = None
    recent_card_applications: int | None = None
    max_results: int = 10


@router.post("/next-card/stateless")
def post_next_card_stateless(payload: StatelessProfileRequest) -> dict:
    """Rank cards from a profile supplied in the request.

    The GET counterpart reads the caller's stored transactions, which is wrong
    for the client-only flow: statements are parsed in the browser and never
    reach the database, so the stored profile is either empty or stale test
    data. This endpoint takes the profile as input instead. It touches no
    session, no user row and no table.
    """
    service = CardRecommendationService()
    approval_profile = ApprovalProfile(
        score_band=payload.credit_score_band,
        recent_applications=payload.recent_card_applications,
    )

    recommendations = service.recommend_next_card(
        {
            "avg_monthly_spend": payload.avg_monthly_spend,
            "category_breakdown": payload.category_breakdown,
            "top_merchants": [],
        },
        [
            {
                "name": c.name,
                "issuer": c.issuer or "",
                "network": "",
                "annual_fee": c.annual_fee,
            }
            for c in payload.held_cards
        ],
        _fetch_cards(),
        max_results=payload.max_results,
        points_value_cents=settings.points_value_cents,
        approval_profile=approval_profile,
    )
    return {"recommendations": recommendations}


@router.post("/portfolio/stateless")
def post_portfolio_stateless(payload: StatelessProfileRequest) -> dict:
    """Analyse the cards the user holds, from a profile supplied in the request.

    Same contract as ``post_next_card_stateless``: aggregates in, analysis out,
    nothing persisted. Returns both the per-card value analysis and the
    per-category "use this card here" assignments, which are computed from the
    same profile so the two can't disagree.
    """
    service = CardRecommendationService()
    profile = {
        "avg_monthly_spend": payload.avg_monthly_spend,
        "category_breakdown": payload.category_breakdown,
        "top_merchants": [],
    }
    user_cards = [
        {
            "name": c.name,
            "issuer": c.issuer or "",
            "network": "",
            "annual_fee": c.annual_fee,
        }
        for c in payload.held_cards
    ]
    available = _fetch_cards()
    return {
        "analyses": service.analyze_portfolio(profile, user_cards, available),
        "best_per_category": service.best_card_per_category(
            profile, user_cards, available
        ),
        "best_available_per_category": _best_available_per_category(
            service, payload.category_breakdown, available
        ),
    }


@router.post("/combination/stateless")
def post_combination_stateless(payload: StatelessProfileRequest) -> dict:
    """The optimal SET of cards (held + new) from a profile supplied in the request.

    The stateless mirror of ``GET /recommendations/combination`` (#185, the
    headline "recommend across BOTH existing + new cards" capability). Same
    contract as the other two stateless endpoints — aggregates in, analysis out,
    nothing persisted — so the client-only flow (statements parsed in the
    browser, never written to the DB) can reach the combination engine the same
    way it reaches next-card and portfolio.

    Returns the combination dict verbatim (``recommended_new_cards``,
    ``per_category_routing``, ``baseline_first_year_value``,
    ``projected_first_year_value``). ``spending_profile`` is deliberately omitted,
    matching ``next-card``/``portfolio`` stateless: the caller already holds the
    profile it just posted.
    """
    service = CardRecommendationService()
    profile = {
        "avg_monthly_spend": payload.avg_monthly_spend,
        "category_breakdown": payload.category_breakdown,
        "top_merchants": [],
    }
    user_cards = [
        {
            "name": c.name,
            "issuer": c.issuer or "",
            "network": "",
            "annual_fee": c.annual_fee,
        }
        for c in payload.held_cards
    ]
    return service.optimal_card_combination(
        profile,
        user_cards,
        _fetch_cards(),
        points_value_cents=settings.points_value_cents,
    )


# What a point is worth, in cents, by the currency the card earns.
#
# The engine values every point at ``points_value_cents`` (1.0 by default),
# which makes a hotel card earning 5x look strictly better than a 3% cash-back
# card. It isn't: Hilton points are worth roughly half a cent, so 5x Hilton is
# about 2.5% — less than the 3% card. Comparing categories across cards is
# meaningless without this, so the comparison below converts every rate to
# cash-equivalent first.
#
# These are conservative, widely-published baseline redemption values, not
# aspirational sweet-spot valuations.
_POINT_VALUE_CENTS = {
    "HILTON": 0.5,
    "MARRIOTT": 0.7,
    "IHG": 0.5,
    "WYNDHAM": 0.9,
    "CHOICE": 0.6,
    "AMERICAN_EXPRESS": 1.0,
    "CHASE": 1.25,
    "CAPITAL_ONE": 1.0,
    "CITI": 1.0,
    "BILT": 1.25,
    "DELTA": 1.1,
    "UNITED": 1.2,
    "AMERICAN": 1.4,
    "SOUTHWEST": 1.3,
    "ALASKA": 1.4,
    "JETBLUE": 1.3,
    "USD": 1.0,
    "CASH": 1.0,
}


def _cash_equivalent_rate(service: CardRecommendationService, card: dict, category: str) -> float:
    """A card's earn rate in this category, expressed as cents back per dollar.

    Without this, 5x in a currency worth half a cent outranks 3% cash.
    """
    rate = service._category_rate(card, category)
    currency = (card.get("currency") or "USD").upper()
    return rate * _POINT_VALUE_CENTS.get(currency, 1.0)


# Retail-finance issuers whose cards are usually closed-loop.
_STORE_ISSUERS = {"SYNCHRONY", "COMENITY", "BREAD", "ALLIANCE DATA"}


def _is_store_card(card: dict) -> bool:
    """Is this a store card, usable only at one retailer?

    The dataset records the Amazon Prime Store Card as
    ``universalCashbackPercent: 5``, but that 5% applies at Amazon and nowhere
    else. Since ``_category_rate`` falls back to the flat rate for any category
    a card doesn't curate, such a card looks like the best card on the market
    for dining, travel and everything else — advice that would cost the user
    money if followed.

    Fixing the flat rate itself belongs upstream in the card dataset. Excluding
    closed-loop cards from general-purpose comparison is the correct scope
    here: they are never the answer to "which card should I use for dining".
    """
    name = (card.get("name") or "").lower()
    issuer = (card.get("issuer") or "").upper()
    return "store card" in name or issuer in _STORE_ISSUERS


def _best_available_per_category(
    service: CardRecommendationService,
    category_breakdown: dict[str, float],
    available: list[dict],
) -> list[dict]:
    """The highest-earning card on the market for each category the user spends in.

    ``best_card_per_category`` only ranks cards the user already holds, which
    answers nothing when they hold one card: it names that card for every
    category. This says what the ceiling is, so the gap between the two can be
    priced and the user can see which categories are worth a new card at all.

    Discontinued cards are skipped — recommending something no longer offered
    is worse than recommending nothing.
    """
    live = [
        c
        for c in available
        if not c.get("discontinued") and not _is_store_card(c)
    ]
    results: list[dict] = []

    for category, monthly in sorted(category_breakdown.items()):
        if monthly <= 0:
            continue

        ranked = sorted(
            live,
            key=lambda c: (
                -_cash_equivalent_rate(service, c, category),
                float(c.get("annualFee") or 0),
                (c.get("name") or "").lower(),
            ),
        )
        if not ranked:
            continue
        winner = ranked[0]
        rate = _cash_equivalent_rate(service, winner, category)
        if rate <= 0:
            continue

        results.append(
            {
                "category": category,
                "card": {
                    "cardId": winner.get("cardId"),
                    "name": winner.get("name"),
                    "issuer": winner.get("issuer"),
                    "annualFee": float(winner.get("annualFee") or 0),
                    "url": winner.get("url"),
                },
                # Cash-equivalent percent, so it can be compared with a
                # cash-back card and turned into dollars directly.
                "rate": round(rate, 2),
                "raw_rate": service._category_rate(winner, category),
                "currency": winner.get("currency"),
            }
        )

    return results
