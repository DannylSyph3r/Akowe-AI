from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str
    readonly_database_url: str = ""  # Phase 11 — not used yet

    # WhatsApp / Meta
    meta_phone_number_id: str
    meta_access_token: str
    meta_verify_token: str
    meta_app_secret: str  # X-Hub-Signature-256 webhook verification

    # Interswitch
    interswitch_merchant_code: str = ""
    interswitch_pay_item_id: str = ""
    interswitch_secret_key: str = ""  # OAuth2 client secret AND webhook HMAC key
    interswitch_client_id: str = ""
    interswitch_auth_url: str = "https://passport.k8.isw.la/passport/oauth/token"
    interswitch_base_url: str = "https://newwebpay.qa.interswitchng.com"
    interswitch_query_url: str = "https://qa.interswitchng.com/collections/api/v2/gettransaction.json"

    # AI
    gemini_api_key: str = ""

    # Auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Internal
    internal_cron_secret: str
    frontend_url: str = ""
    prod_url: str = ""

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql://", 1)
        return url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()