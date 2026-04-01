from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Finance Tracker API", version="0.1.0")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app
