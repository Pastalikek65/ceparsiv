import os
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    secret_key: str = field(
        default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-key-for-development-only")
    )
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///data/app.db")
    )
    debug: bool = field(default_factory=lambda: _env_bool("DEBUG", False))
    session_hours: int = field(default_factory=lambda: int(os.getenv("SESSION_HOURS", "24")))


settings = Settings()
