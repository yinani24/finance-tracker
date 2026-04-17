from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.api.insights import fire_insights_event
from app.database import get_db
from app.repositories.goal import GoalRepository
from app.schemas.goal import GoalCreate, GoalRead, GoalUpdate
from app.services.insight_types import EngineEvent

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalRead])
def list_goals(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[GoalRead]:
    repo = GoalRepository(db)
    return repo.list_by_user(user_id)


@router.post("", response_model=GoalRead, status_code=201)
def create_goal(
    data: GoalCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> GoalRead:
    repo = GoalRepository(db)
    result = repo.create(user_id, data)
    fire_insights_event(db, EngineEvent.GOAL_MUTATED, user_id)
    return result


@router.patch("/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: int,
    data: GoalUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> GoalRead:
    repo = GoalRepository(db)
    goal = repo.get(goal_id, user_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    result = repo.update(goal, data)
    fire_insights_event(db, EngineEvent.GOAL_MUTATED, user_id)
    return result
