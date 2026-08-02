from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class TransactionCreate(BaseModel):
    account_id: int
    external_id: Optional[str] = None
    occurred_on: date
    amount: float
    merchant: str
    normalized_merchant: Optional[str] = None
    category: Optional[str] = None
    is_income: bool = False
    is_savings: bool = False
    source: Optional[str] = None
    dedupe_hash: str
    notes: Optional[str] = None


class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    is_income: Optional[bool] = None
    is_savings: Optional[bool] = None
    notes: Optional[str] = None


class TransactionRead(BaseModel):
    id: int
    user_id: int
    account_id: int
    external_id: Optional[str]
    occurred_on: date
    posted_at: Optional[datetime]
    amount: float
    merchant: str
    normalized_merchant: Optional[str]
    category: Optional[str]
    category_confidence: Optional[float]
    enriched_at: Optional[datetime]
    is_income: bool
    is_savings: bool
    source: Optional[str]
    source_import_id: Optional[int]
    dedupe_hash: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
