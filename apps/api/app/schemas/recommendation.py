from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class CategorySpend(BaseModel):
    category: str
    monthly_avg: float


class TopMerchant(BaseModel):
    name: str
    monthly_avg: float


class SpendingProfileRead(BaseModel):
    user_id: int
    period_start: date
    period_end: date
    avg_monthly_spend: float
    categories: List[CategorySpend]
    top_merchants: List[TopMerchant]
    computed_at: datetime


class BonusInfo(BaseModel):
    amount: int
    min_spend: float
    days: int
    months_to_hit: float
    achievable: bool


class AlternativeCard(BaseModel):
    card_id: str
    name: str
    issuer: str
    annual_fee: float
    estimated_annual_value: float
    net_value: float
    url: str


class NextCardRecommendation(BaseModel):
    card_id: str
    name: str
    issuer: str
    network: str
    annual_fee: float
    is_annual_fee_waived: bool
    universal_cashback_percent: float
    currency: str
    url: str
    image_url: str
    bonus: Optional[BonusInfo]
    score: float
    explanation: str


class NextCardResponse(BaseModel):
    recommendations: List[NextCardRecommendation]
    spending_profile: SpendingProfileRead


class CardAnalysis(BaseModel):
    card_name: str
    card_network: str
    annual_fee: float
    estimated_annual_value: float
    net_value: float
    status: str
    explanation: str
    alternatives: List[AlternativeCard]


class BestHeldCard(BaseModel):
    name: str
    issuer: str


class CategoryAssignment(BaseModel):
    """Which held card to reach for in a given spending category (PRD User
    Story 2). ``rate`` is the winning card's per-category earn as a
    percent-equivalent."""

    category: str
    best_card: BestHeldCard
    rate: float
    rationale: str


class PortfolioResponse(BaseModel):
    cards: List[CardAnalysis]
    # Additive: per-category "best held card" assignments. Defaults to [] so the
    # response stays back-compatible for any consumer that reads only `cards`.
    category_assignments: List[CategoryAssignment] = []
    spending_profile: SpendingProfileRead


class RoutedCategory(BaseModel):
    """A spending category routed to its best card across the combined wallet
    (held + any recommended-new). ``is_new`` flags a routing that lands on a
    recommended card the user doesn't yet hold; ``rate`` is that card's
    per-category earn as a percent-equivalent."""

    category: str
    card: BestHeldCard
    is_new: bool
    rate: float


class RecommendedNewCard(BaseModel):
    """A new card the combination recommends applying for. ``marginal_value`` is
    its first-year value delta (extra earn it wins + sign-up bonus + credits −
    first-year fee); ``categories_won`` are the spend categories it becomes the
    best card for."""

    name: str
    issuer: str
    marginal_value: float
    categories_won: List[str]
    rationale: str


class CombinationResponse(BaseModel):
    """Optimal SET of cards (held + new) maximizing total first-year value
    (recommendation-engine slice 5, PRD Decision #1)."""

    recommended_new_cards: List[RecommendedNewCard]
    per_category_routing: List[RoutedCategory]
    baseline_first_year_value: float
    projected_first_year_value: float
    spending_profile: SpendingProfileRead
