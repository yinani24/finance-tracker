from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CardCreate(BaseModel):
    name: str
    network: str
    annual_fee: float = 0.0
    rewards_config_json: str = "{}"
    issuer: Optional[str] = None


class CardUpdate(BaseModel):
    name: Optional[str] = None
    network: Optional[str] = None
    annual_fee: Optional[float] = None
    rewards_config_json: Optional[str] = None
    issuer: Optional[str] = None


class CardRead(BaseModel):
    id: int
    user_id: int
    name: str
    network: str
    annual_fee: float
    rewards_config_json: str
    issuer: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
