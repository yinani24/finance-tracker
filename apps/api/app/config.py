from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://localhost:5432/finance_tracker"
    # Comma-separated browser origins allowed to call this API.
    cors_origins_raw: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]
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
    # Model used to parse PDF statements (blank → a sensible current default).
    pdf_import_model: str = ""
    card_bonuses_url: str = ""
    # Transaction-enrichment provider (see app/services/enrichment). Defaults to
    # the keyless "noop" provider so tests/CI stay hermetic; set to a real
    # provider (e.g. "ntropy", slice 2) once a key is provisioned.
    enrichment_provider: str = "rules"
    # Blended cents-per-point used to value sign-up-bonus points/miles in
    # dollars so points cards and cashback cards rank on one scale (the
    # owner-confirmed "total first-year value" objective; see
    # docs/prd/recommendation-engine.md). The dataset carries no point-program
    # identifier, so a single flat rate is the only v1 option. 1.0¢ is a
    # conservative floor; raise via FT_POINTS_VALUE_CENTS.
    points_value_cents: float = 1.0
    # Local directory where uploaded bank statements are stored (the manual,
    # Plaid-free import path). Dev default; a later slice swaps this for real
    # object storage (S3 / Supabase Storage) behind the same file-storage
    # interface. These are sensitive documents — keep the dir out of any
    # web-served path. Override with FT_IMPORT_STORAGE_DIR.
    import_storage_dir: str = "./var/imports"

    model_config = {"env_prefix": "FT_"}


settings = Settings()
