from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.models.import_record import Import
from app.repositories.account import AccountRepository
from app.repositories.import_record import ImportRepository
from app.schemas.import_record import ImportRead, ImportSummary
from app.services.statement_import import StatementParseError, run_import

router = APIRouter(prefix="/imports", tags=["imports"])


def _to_read(record: Import, transaction_count: int) -> ImportRead:
    return ImportRead(
        id=record.id,
        account_id=record.account_id,
        provider=record.provider,
        import_type=record.import_type,
        status=record.status,
        error_message=record.error_message,
        transaction_count=transaction_count,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


@router.post("", response_model=ImportSummary, status_code=201)
async def create_import(
    file: UploadFile = File(...),
    account_id: int = Form(...),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ImportSummary:
    account = AccountRepository(db).get(account_id, user_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    content = await file.read()
    try:
        record, result = run_import(
            db=db,
            user_id=user_id,
            account_id=account_id,
            file_bytes=content,
            filename=file.filename or "upload.csv",
            mime_type=file.content_type or "text/csv",
        )
    except StatementParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    return ImportSummary(
        import_id=record.id,
        account_id=record.account_id,
        provider=record.provider,
        import_type=record.import_type,
        status=record.status,
        total_rows=result.total_rows,
        added=result.added,
        duplicates=result.duplicates,
        skipped=result.skipped,
        error_message=record.error_message,
    )


@router.get("", response_model=list[ImportRead])
def list_imports(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[ImportRead]:
    repo = ImportRepository(db)
    records = repo.list_by_user(user_id)
    return [_to_read(r, repo.transaction_count(r.id)) for r in records]


@router.get("/{import_id}", response_model=ImportRead)
def get_import(
    import_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ImportRead:
    repo = ImportRepository(db)
    record = repo.get(import_id, user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Import not found")
    return _to_read(record, repo.transaction_count(record.id))
