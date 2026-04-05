from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AccountCreate(BaseModel):
    name: str
    type: str
    institution_name: Optional[str] = None
    external_account_id: Optional[str] = None
    balance: float = 0.0
    currency: str = "USD"


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    institution_name: Optional[str] = None
    external_account_id: Optional[str] = None
    balance: Optional[float] = None
    currency: Optional[str] = None


class AccountRead(BaseModel):
    id: int
    user_id: int
    name: str
    type: str
    institution_name: Optional[str]
    external_account_id: Optional[str]
    balance: float
    currency: str
    last_synced_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
