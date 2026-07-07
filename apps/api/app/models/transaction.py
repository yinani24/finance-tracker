from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    occurred_on: Mapped[date] = mapped_column(Date)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    merchant: Mapped[str] = mapped_column(String(255))
    normalized_merchant: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_income: Mapped[bool] = mapped_column(Boolean, default=False)
    is_savings: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_import_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("imports.id"), nullable=True
    )
    dedupe_hash: Mapped[str] = mapped_column(String(64), index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
