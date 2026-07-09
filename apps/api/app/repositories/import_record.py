from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.import_record import Import, ImportFile
from app.models.transaction import Transaction


class ImportRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, user_id: int, account_id: int, provider: str, import_type: str
    ) -> Import:
        record = Import(
            user_id=user_id,
            account_id=account_id,
            provider=provider,
            import_type=import_type,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def add_file(
        self,
        import_id: int,
        storage_key: str,
        original_filename: str,
        mime_type: str,
        size_bytes: int,
    ) -> ImportFile:
        record = ImportFile(
            import_id=import_id,
            storage_key=storage_key,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get(self, import_id: int, user_id: int) -> Import | None:
        stmt = select(Import).where(
            Import.id == import_id, Import.user_id == user_id
        )
        return self.db.scalars(stmt).first()

    def list_by_user(self, user_id: int) -> list[Import]:
        stmt = (
            select(Import)
            .where(Import.user_id == user_id)
            .order_by(Import.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def transaction_count(self, import_id: int) -> int:
        stmt = select(func.count(Transaction.id)).where(
            Transaction.source_import_id == import_id
        )
        return int(self.db.scalar(stmt) or 0)

    def mark_done(self, record: Import) -> Import:
        record.status = "done"
        record.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return record

    def mark_failed(self, record: Import, error_message: str) -> Import:
        record.status = "failed"
        record.error_message = error_message[:500]
        record.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return record
