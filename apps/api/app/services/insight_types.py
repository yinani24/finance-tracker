from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Optional, Protocol

from app.models.account import Account
from app.models.card import Card
from app.models.goal import Goal
from app.models.insight import Insight
from app.models.plaid_item import PlaidItem
from app.models.spending_profile import SpendingProfile
from app.models.transaction import Transaction


class EngineEvent(StrEnum):
    TRANSACTIONS_SYNCED = "transactions_synced"
    TRANSACTION_MUTATED = "transaction_mutated"
    ACCOUNT_BALANCE_CHANGED = "account_balance_changed"
    GOAL_MUTATED = "goal_mutated"
    CARD_MUTATED = "card_mutated"
    USER_ONBOARDED = "user_onboarded"


@dataclass
class EngineContext:
    spending_profile: Optional[SpendingProfile] = None
    accounts: list[Account] = field(default_factory=list)
    transactions_recent: list[Transaction] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    cards: list[Card] = field(default_factory=list)
    plaid_items: list[PlaidItem] = field(default_factory=list)


@dataclass
class InsightDraft:
    kind: str
    title: str
    body: str
    impact_one_time_cents: int
    impact_annual_cents: int
    effort: Literal["low", "medium", "high"]
    evidence: dict
    action: Optional[dict]
    related_goal_id: Optional[int]
    inputs_hash: str


class InsightEngine(Protocol):
    name: str

    def relevant_events(self) -> set[EngineEvent]: ...

    def generate(self, user_id: int, ctx: EngineContext) -> list[InsightDraft]: ...

    def detect_resolution(
        self, old_insight: Insight, ctx: EngineContext
    ) -> Literal["acted_on", "expired", "still_active"]:
        return "expired"
