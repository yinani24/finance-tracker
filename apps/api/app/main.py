from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.services.plaid_errors import PlaidError


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

    # Local development plus anything served from the project's own Vercel
    # domains. The regex covers preview deployments, whose hostname changes on
    # every build and so cannot be enumerated ahead of time.
    #
    # `allow_credentials` is False: the stateless recommendation endpoints take
    # everything they need in the request body and read no cookie or auth
    # header, so permitting credentials across origins would grant access this
    # API never needs.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"https://[a-z0-9-]+\.vercel\.app$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(PlaidError)
    async def _plaid_error_handler(request: Request, exc: PlaidError) -> JSONResponse:
        # Only the whitelisted error_code and derived action are surfaced —
        # never the raw Plaid body, access token, or request internals.
        body: dict[str, str] = {"error_code": exc.error_code}
        if exc.action:
            body["action"] = exc.action
        return JSONResponse(status_code=exc.http_status, content=body)

    app.include_router(api_router)

    return app


app = create_app()
