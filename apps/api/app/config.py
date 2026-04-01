from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./finance.db"
    debug: bool = False

    model_config = {"env_prefix": "FT_"}


settings = Settings()
