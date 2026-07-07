from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.repositories.user import UserRepository
from app.schemas.user import PreferenceRead, PreferenceUpdate, UserRead

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserRead)
def get_me(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> UserRead:
    repo = UserRepository(db)
    return repo.find_by_id(user_id)


@router.get("/me/preferences", response_model=PreferenceRead)
def get_preferences(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> PreferenceRead:
    repo = UserRepository(db)
    return repo.get_preferences(user_id)


@router.patch("/me/preferences", response_model=PreferenceRead)
def update_preferences(
    data: PreferenceUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> PreferenceRead:
    repo = UserRepository(db)
    return repo.update_preferences(user_id, data)
