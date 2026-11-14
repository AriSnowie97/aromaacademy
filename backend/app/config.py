from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Аромакадемія"
    app_env: str = "development"
    database_url: str = f"sqlite:///{(BASE_DIR / 'aromaacademy.db').as_posix()}"
    secret_key: str = "dev-change-this-secret-key-in-production"
    webhook_secret: str = "dev-webhook-hmac-secret"
    token_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 days
    aroma_service_mode: str = "local"  # "local" or "remote"
    aroma_service_url: str = ""
    media_dir: Path = BASE_DIR / "media"
    frontend_dir: Path = BASE_DIR / "frontend"
    consent_version: str = "2026-11-v1"
    disclaimer_text: str = (
        "Це навчальний матеріал, а не медична консультація. "
        "У разі сумнівів зверніться до лікаря."
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    (settings.media_dir / "videos").mkdir(parents=True, exist_ok=True)
    return settings

