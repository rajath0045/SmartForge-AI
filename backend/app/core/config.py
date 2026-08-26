from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "SmartForge AI"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'smartforge.db'}"
    )
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    )


settings = Settings()
