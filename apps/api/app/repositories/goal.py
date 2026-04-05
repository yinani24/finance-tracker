from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.schemas.goal import GoalCreate, GoalUpdate


class GoalRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(self, user_id: int) -> list[Goal]:
        stmt = select(Goal).where(Goal.user_id == user_id)
        return list(self.db.scalars(stmt).all())

    def get(self, goal_id: int, user_id: int) -> Goal | None:
        stmt = select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
        return self.db.scalars(stmt).first()

    def create(self, user_id: int, data: GoalCreate) -> Goal:
        goal = Goal(user_id=user_id, **data.model_dump())
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def update(self, goal: Goal, data: GoalUpdate) -> Goal:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(goal, field, value)
        self.db.commit()
        self.db.refresh(goal)
        return goal
