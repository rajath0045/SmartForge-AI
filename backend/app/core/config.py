from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _boolean_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    value = raw_value.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(
        f"{name} must be one of: {', '.join(sorted(_TRUE_VALUES | _FALSE_VALUES))}"
    )


def _api_prefix() -> str:
    value = os.getenv("API_PREFIX", "/api").strip()
    if not value or value == "/":
        raise ValueError("API_PREFIX must contain a non-root URL path")
    return f"/{value.strip('/')}"


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        database_path = (
            Path("/tmp/smartforge.db")
            if os.getenv("VERCEL")
            else BACKEND_DIR / "smartforge.db"
        )
        return f"sqlite:///{database_path}"

    # Hosted providers commonly expose either legacy postgres:// URLs or the
    # SQLAlchemy postgresql:// form. Use the bundled psycopg 3 driver for both.
    if value.startswith("postgres://"):
        return f"postgresql+psycopg://{value.removeprefix('postgres://')}"
    if value.startswith("postgresql://"):
        return f"postgresql+psycopg://{value.removeprefix('postgresql://')}"
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "SmartForge AI"
    app_version: str = "1.0.0"
    api_prefix: str = _api_prefix()
    database_url: str = _database_url()
    auto_seed: bool = _boolean_env("AUTO_SEED", True)
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    )


settings = Settings()
