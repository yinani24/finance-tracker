from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate, TransactionUpdate


class TransactionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(
        self,
        user_id: int,
        category: Optional[str] = None,
        account_id: Optional[int] = None,
    ) -> list[Transaction]:
        stmt = select(Transaction).where(Transaction.user_id == user_id)
        if category:
            stmt = stmt.where(Transaction.category == category)
        if account_id:
            stmt = stmt.where(Transaction.account_id == account_id)
        stmt = stmt.order_by(Transaction.occurred_on.desc())
        return list(self.db.scalars(stmt).all())

    def get(self, txn_id: int, user_id: int) -> Transaction | None:
        stmt = select(Transaction).where(
            Transaction.id == txn_id, Transaction.user_id == user_id
        )
        return self.db.scalars(stmt).first()

    def create(self, user_id: int, data: TransactionCreate) -> Transaction:
        txn = Transaction(user_id=user_id, **data.model_dump())
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def update(self, txn: Transaction, data: TransactionUpdate) -> Transaction:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(txn, field, value)
        self.db.commit()
        self.db.refresh(txn)
        return txn
