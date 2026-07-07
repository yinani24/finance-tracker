from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class GoalCreate(BaseModel):
    name: str
    goal_type: str
    target_amount: float
    current_amount: float = 0.0
    deadline: Optional[date] = None
    is_monthly: bool = False


class GoalUpdate(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[float] = None
    current_amount: Optional[float] = None
    deadline: Optional[date] = None


class GoalRead(BaseModel):
    id: int
    user_id: int
    name: str
    goal_type: str
    target_amount: float
    current_amount: float
    deadline: Optional[date]
    is_monthly: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
