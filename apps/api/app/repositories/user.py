from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, UserPreference
from app.schemas.user import PreferenceUpdate


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_subject(self, auth_subject: str) -> User | None:
        stmt = select(User).where(User.auth_subject == auth_subject)
        return self.db.scalars(stmt).first()

    def find_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def create_from_token(self, auth_subject: str, email: str) -> User:
        user = User(auth_provider="supabase", auth_subject=auth_subject, email=email)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_preferences(self, user_id: int) -> UserPreference:
        pref = self.db.get(UserPreference, user_id)
        if not pref:
            pref = UserPreference(user_id=user_id)
            self.db.add(pref)
            self.db.commit()
            self.db.refresh(pref)
        return pref

    def update_preferences(self, user_id: int, data: PreferenceUpdate) -> UserPreference:
        pref = self.get_preferences(user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(pref, field, value)
        self.db.commit()
        self.db.refresh(pref)
        return pref
