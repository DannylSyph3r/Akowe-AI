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
    readonly_database_url: str = ""

    # WhatsApp / Meta
    meta_phone_number_id: str
    meta_access_token: str
    meta_verify_token: str

    # Interswitch
    interswitch_merchant_code: str = ""
    interswitch_pay_item_id: str = ""
    interswitch_secret_key: str = ""
    interswitch_base_url: str = "https://newwebpay.qa.interswitchng.com"

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

    @property
    def async_database_url(self) -> str:
        """Return asyncpg-compatible URL for the async engine."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            # Railway sometimes emits postgres:// shorthand
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Return psycopg2-compatible URL for Alembic migrations."""
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql://", 1)
        # Strip +asyncpg if someone stored the async URL directly
        return url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()