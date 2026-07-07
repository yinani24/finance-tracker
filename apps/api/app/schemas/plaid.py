from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LinkTokenRequest(BaseModel):
    """Request to create a Plaid Link token."""


class LinkTokenResponse(BaseModel):
    link_token: str
    expiration: str


class ExchangeTokenRequest(BaseModel):
    public_token: str
    institution_id: Optional[str] = None
    institution_name: Optional[str] = None


class PlaidItemRead(BaseModel):
    id: int
    user_id: int
    item_id: str
    institution_id: Optional[str]
    institution_name: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SyncResult(BaseModel):
    accounts_synced: int
    transactions_added: int
    transactions_modified: int
    transactions_removed: int
