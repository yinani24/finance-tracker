from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ImportSummary(BaseModel):
    """Result of a single statement-import run (the POST /imports response).

    ``duplicates`` and ``skipped`` are ephemeral per-run counts (not persisted
    on the ``Import`` row) so the caller sees exactly what one upload did.
    """

    import_id: int
    account_id: int
    provider: str
    import_type: str
    status: str
    total_rows: int
    added: int
    duplicates: int
    skipped: int
    error_message: Optional[str] = None


class ImportRead(BaseModel):
    """Persisted status of an import (GET /imports and GET /imports/{id}).

    ``transaction_count`` is derived at read time from the transactions that
    reference this import, so no count columns are needed on the model.
    """

    id: int
    account_id: int
    provider: str
    import_type: str
    status: str
    error_message: Optional[str] = None
    transaction_count: int
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
