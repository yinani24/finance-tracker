from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.schemas.account import AccountCreate, AccountUpdate


class AccountRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(self, user_id: int) -> list[Account]:
        stmt = select(Account).where(Account.user_id == user_id)
        return list(self.db.scalars(stmt).all())

    def get(self, account_id: int, user_id: int) -> Account | None:
        stmt = select(Account).where(Account.id == account_id, Account.user_id == user_id)
        return self.db.scalars(stmt).first()

    def create(self, user_id: int, data: AccountCreate) -> Account:
        account = Account(user_id=user_id, **data.model_dump())
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def update(self, account: Account, data: AccountUpdate) -> Account:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(account, field, value)
        self.db.commit()
        self.db.refresh(account)
        return account
