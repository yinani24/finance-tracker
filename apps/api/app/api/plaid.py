from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.api.insights import fire_insights_event
from app.database import get_db
from app.repositories.plaid_item import PlaidItemRepository
from app.schemas.plaid import (
    ExchangeTokenRequest,
    LinkTokenResponse,
    PlaidItemRead,
    SyncResult,
)
from app.services.insight_types import EngineEvent
from app.services.plaid_service import (
    create_link_token,
    exchange_public_token,
    get_plaid_client,
    sync_transactions,
)

router = APIRouter(prefix="/plaid", tags=["plaid"])


@router.post("/link-token", response_model=LinkTokenResponse)
def create_link(
    user_id: int = Depends(get_current_user_id),
) -> LinkTokenResponse:
    client = get_plaid_client()
    result = create_link_token(client, user_id)
    return LinkTokenResponse(**result)


@router.post("/exchange-token", response_model=PlaidItemRead, status_code=201)
def exchange_token(
    data: ExchangeTokenRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> PlaidItemRead:
    client = get_plaid_client()
    result = exchange_public_token(client, data.public_token)

    repo = PlaidItemRepository(db)
    existing = repo.get_by_plaid_item_id(result["item_id"])
    if existing:
        raise HTTPException(status_code=409, detail="Item already linked")

    plaid_item = repo.create(
        user_id=user_id,
        item_id=result["item_id"],
        access_token=result["access_token"],
        institution_id=data.institution_id,
        institution_name=data.institution_name,
    )
    return plaid_item


@router.get("/items", response_model=list[PlaidItemRead])
def list_items(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[PlaidItemRead]:
    repo = PlaidItemRepository(db)
    return repo.list_by_user(user_id)


@router.post("/items/{item_id}/sync", response_model=SyncResult)
def sync_item(
    item_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> SyncResult:
    repo = PlaidItemRepository(db)
    plaid_item = repo.get(item_id, user_id)
    if not plaid_item:
        raise HTTPException(status_code=404, detail="Plaid item not found")

    client = get_plaid_client()
    result = sync_transactions(client, db, plaid_item, user_id)
    fire_insights_event(db, EngineEvent.TRANSACTIONS_SYNCED, user_id)
    return SyncResult(**result)


@router.delete("/items/{item_id}", status_code=204)
def remove_item(
    item_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> None:
    repo = PlaidItemRepository(db)
    plaid_item = repo.get(item_id, user_id)
    if not plaid_item:
        raise HTTPException(status_code=404, detail="Plaid item not found")
    repo.delete(plaid_item)
