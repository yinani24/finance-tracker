from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://localhost:5432/finance_tracker"
    test_database_url: str = "postgresql://localhost:5432/finance_tracker_test"
    debug: bool = False

    model_config = {"env_prefix": "FT_"}


settings = Settings()
