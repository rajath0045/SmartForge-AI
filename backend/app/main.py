from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.seed import seed_database


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if settings.auto_seed:
        seed_database()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    description=(
        "Finite-capacity manufacturing planning and decision-support API for "
        "Sridhar Precision Works."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


def _health_payload() -> dict:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "database": "connected",
    }


@app.get("/health", tags=["health"])
def health() -> dict:
    return _health_payload()


@app.get(f"{settings.api_prefix}/health", tags=["health"], include_in_schema=False)
def api_health() -> dict:
    return _health_payload()
