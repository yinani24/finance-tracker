from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plaid_item import PlaidItem


class PlaidItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(self, user_id: int) -> list[PlaidItem]:
        stmt = select(PlaidItem).where(PlaidItem.user_id == user_id)
        return list(self.db.scalars(stmt).all())

    def get(self, item_id: int, user_id: int) -> PlaidItem | None:
        stmt = select(PlaidItem).where(PlaidItem.id == item_id, PlaidItem.user_id == user_id)
        return self.db.scalars(stmt).first()

    def get_by_plaid_item_id(self, plaid_item_id: str) -> PlaidItem | None:
        stmt = select(PlaidItem).where(PlaidItem.item_id == plaid_item_id)
        return self.db.scalars(stmt).first()

    def create(
        self,
        user_id: int,
        item_id: str,
        access_token: str,
        institution_id: str | None = None,
        institution_name: str | None = None,
    ) -> PlaidItem:
        plaid_item = PlaidItem(
            user_id=user_id,
            item_id=item_id,
            access_token=access_token,
            institution_id=institution_id,
            institution_name=institution_name,
        )
        self.db.add(plaid_item)
        self.db.commit()
        self.db.refresh(plaid_item)
        return plaid_item

    def update_cursor(self, plaid_item: PlaidItem, cursor: str) -> None:
        plaid_item.cursor = cursor
        self.db.commit()

    def delete(self, plaid_item: PlaidItem) -> None:
        self.db.delete(plaid_item)
        self.db.commit()
