from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    import_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ImportFile(Base):
    __tablename__ = "import_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("imports.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
