from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.card import Card
from app.schemas.card import CardCreate, CardUpdate


class CardRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(self, user_id: int) -> list[Card]:
        stmt = select(Card).where(Card.user_id == user_id)
        return list(self.db.scalars(stmt).all())

    def get(self, card_id: int, user_id: int) -> Card | None:
        stmt = select(Card).where(Card.id == card_id, Card.user_id == user_id)
        return self.db.scalars(stmt).first()

    def create(self, user_id: int, data: CardCreate) -> Card:
        card = Card(user_id=user_id, **data.model_dump())
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        return card

    def update(self, card: Card, data: CardUpdate) -> Card:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(card, field, value)
        self.db.commit()
        self.db.refresh(card)
        return card
