from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.api.insights import fire_insights_event
from app.database import get_db
from app.repositories.transaction import TransactionRepository
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate
from app.services.insight_types import EngineEvent

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionRead])
def list_transactions(
    category: Optional[str] = None,
    account_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[TransactionRead]:
    repo = TransactionRepository(db)
    return repo.list_by_user(user_id, category=category, account_id=account_id)


@router.post("", response_model=TransactionRead, status_code=201)
def create_transaction(
    data: TransactionCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> TransactionRead:
    repo = TransactionRepository(db)
    result = repo.create(user_id, data)
    fire_insights_event(db, EngineEvent.TRANSACTION_MUTATED, user_id)
    return result


@router.patch("/{transaction_id}", response_model=TransactionRead)
def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> TransactionRead:
    repo = TransactionRepository(db)
    txn = repo.get(transaction_id, user_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    result = repo.update(txn, data)
    fire_insights_event(db, EngineEvent.TRANSACTION_MUTATED, user_id)
    return result
