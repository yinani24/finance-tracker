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
    plaid_webhook_url: str = ""
    # OAuth redirect URI. REQUIRED to link OAuth institutions (Chase, Bank of
    # America, Wells Fargo, Capital One, …); without it Link errors out when
    # such a bank is selected. Must EXACTLY match an "Allowed redirect URI"
    # registered in the Plaid Dashboard and the page hosting Plaid Link. Leave
    # blank for sandbox non-OAuth test banks. See docs/prd/plaid-integration.md.
    plaid_redirect_uri: str = ""
    # Verify the Plaid-Verification JWT on inbound webhooks. Defaults on; set
    # FT_PLAID_WEBHOOK_VERIFY=false only for local/sandbox testing without a
    # publicly reachable URL (see docs/prd/plaid-integration.md Q3).
    plaid_webhook_verify: bool = True
    anthropic_api_key: str = ""
    card_bonuses_url: str = ""

    model_config = {"env_prefix": "FT_"}


settings = Settings()
