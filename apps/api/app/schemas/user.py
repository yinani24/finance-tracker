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

    model_config = {"from_attributes": True}


class PreferenceUpdate(BaseModel):
    theme: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
