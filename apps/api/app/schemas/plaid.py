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


class PlaidWebhookPayload(BaseModel):
    """A Plaid webhook body.

    All fields are optional and unknown keys are tolerated so that any webhook
    shape Plaid sends (or a malformed body) parses into a no-op rather than a
    422 — the handler decides what to act on.
    """

    webhook_type: Optional[str] = None
    webhook_code: Optional[str] = None
    item_id: Optional[str] = None

    model_config = {"extra": "allow"}
