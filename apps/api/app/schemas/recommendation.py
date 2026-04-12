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


class PortfolioResponse(BaseModel):
    cards: List[CardAnalysis]
    spending_profile: SpendingProfileRead
