from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "СУУПР Backend"
    app_env: str = "local"
    app_debug: bool = True
    api_v1_prefix: str = "/api/v1"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "promouters"
    postgres_user: str = "promouters"
    postgres_password: str = "promouters"

    log_level: str = "INFO"
    log_json: bool = False
    log_config_path: str = "config/logging.yaml"
    cors_allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    jwt_secret: str = "change-me-access-secret"
    jwt_expiration_time: int = 3600
    jwt_algorithm: str = "HS256"
    jwt_refresh_secret: str = "change-me-refresh-secret"
    jwt_refresh_expiration_time: int = 86_400
    jwt_refresh_algorithm: str = "HS256"

    auth_sms_enabled: bool = False
    auth_sms_code_ttl_seconds: int = 300
    auth_sms_code_length: int = 6
    auth_sms_max_attempts: int = 5

    sms_ru_api_id: str | None = None
    sms_ru_from: str | None = None
    sms_ru_test: bool = True

    media_root: str = "media"
    media_url: str = "http://127.0.0.1:8000/media"
    photo_report_reminder_minutes: int = 30
    photo_report_reminder_min_minutes: int = 15
    photo_report_reminder_max_minutes: int = 30
    photo_report_reminders_enabled: bool = True

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            "postgresql+psycopg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
