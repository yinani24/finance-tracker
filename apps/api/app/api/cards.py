from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.api.insights import fire_insights_event
from app.database import get_db
from app.repositories.card import CardRepository
from app.schemas.card import CardCreate, CardRead, CardUpdate
from app.services.insight_types import EngineEvent

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("", response_model=list[CardRead])
def list_cards(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[CardRead]:
    repo = CardRepository(db)
    return repo.list_by_user(user_id)


@router.post("", response_model=CardRead, status_code=201)
def create_card(
    data: CardCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> CardRead:
    repo = CardRepository(db)
    result = repo.create(user_id, data)
    fire_insights_event(db, EngineEvent.CARD_MUTATED, user_id)
    return result


@router.patch("/{card_id}", response_model=CardRead)
def update_card(
    card_id: int,
    data: CardUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> CardRead:
    repo = CardRepository(db)
    card = repo.get(card_id, user_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    result = repo.update(card, data)
    fire_insights_event(db, EngineEvent.CARD_MUTATED, user_id)
    return result


@router.delete("/{card_id}", status_code=204)
def delete_card(
    card_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> None:
    repo = CardRepository(db)
    card = repo.get(card_id, user_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    repo.delete(card)
    fire_insights_event(db, EngineEvent.CARD_MUTATED, user_id)
