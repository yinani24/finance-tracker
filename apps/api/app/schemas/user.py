from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserRead(BaseModel):
    id: int
    email: str
    auth_provider: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PreferenceRead(BaseModel):
    theme: str
    timezone: str
    currency: str
    credit_score_band: Optional[str] = None
    recent_card_applications: Optional[int] = None

    model_config = {"from_attributes": True}


class PreferenceUpdate(BaseModel):
    theme: Optional[str] = None
    timezone: Optional[str] = None
    credit_score_band: Optional[str] = None
    recent_card_applications: Optional[int] = None
    currency: Optional[str] = None
