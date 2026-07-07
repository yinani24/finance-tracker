from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://localhost:5432/finance_tracker"
    test_database_url: str = "postgresql://localhost:5432/finance_tracker_test"
    debug: bool = False
    supabase_jwt_secret: str = ""
    auth_disabled: bool = False
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"
    anthropic_api_key: str = ""

    model_config = {"env_prefix": "FT_"}


settings = Settings()
