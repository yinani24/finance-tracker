from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.repositories.account import AccountRepository
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountRead])
def list_accounts(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[AccountRead]:
    repo = AccountRepository(db)
    return repo.list_by_user(user_id)


@router.post("", response_model=AccountRead, status_code=201)
def create_account(
    data: AccountCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> AccountRead:
    repo = AccountRepository(db)
    return repo.create(user_id, data)


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    account_id: int,
    data: AccountUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> AccountRead:
    repo = AccountRepository(db)
    account = repo.get(account_id, user_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return repo.update(account, data)
