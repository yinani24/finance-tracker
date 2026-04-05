from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.config import settings
from app.database import SessionLocal
from app.models.user import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auth_disabled:
        db = SessionLocal()
        try:
            if not db.get(User, 1):
                db.add(User(id=1, auth_provider="dev", auth_subject="dev-user", email="dev@local"))
                db.commit()
        finally:
            db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Finance Tracker API", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)

    return app
