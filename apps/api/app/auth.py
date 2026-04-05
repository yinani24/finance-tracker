from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.repositories.user import UserRepository


def decode_supabase_jwt(token: str, secret: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    except jwt.PyJWTError:
        return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> int:
    if settings.auth_disabled:
        return 1

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")

    token = auth_header.removeprefix("Bearer ")
    payload = decode_supabase_jwt(token, settings.supabase_jwt_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    sub = payload.get("sub")
    email = payload.get("email", "")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    repo = UserRepository(db)
    user = repo.find_by_subject(sub)
    if not user:
        user = repo.create_from_token(sub, email)

    return user.id
