"""FastAPI application entry point with middleware, CORS, and structured logging."""

import logging
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.engine import make_url
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.database import engine, ensure_schema

# ── Structured Logging ─────────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.log_format != "json"
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.getLevelName(settings.log_level)
    ),
)

logger = structlog.get_logger()


def _safe_db_target(url: str) -> dict:
    """Return non-sensitive DB connection target details for startup diagnostics."""
    try:
        parsed = make_url(url)
        return {
            "driver": parsed.drivername,
            "host": parsed.host,
            "port": parsed.port,
            "database": parsed.database,
        }
    except Exception:
        return {"driver": "unknown", "host": "unknown", "port": None, "database": "unknown"}


# ── Lifespan ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    await ensure_schema()
    logger.info("avelon_startup", env=settings.app_env)
    os.makedirs(settings.upload_dir, exist_ok=True)
    yield
    await engine.dispose()
    logger.info("avelon_shutdown")


# ── Rate Limiter ───────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=[
    f"{settings.rate_limit_requests}/{settings.rate_limit_window_seconds}seconds"
])

# ── App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Avelon",
    description="AI Red-Team Platform for Code Model Reliability",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ───────────────────────────────────────────────────────────────

cors_origins = settings.cors_origins
logger.info(
    "cors_configuration",
    allow_origins=cors_origins,
    allow_origin_regex=settings.cors_allow_origin_regex,
)
logger.info("database_configuration", **_safe_db_target(settings.database_url))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=settings.cors_allow_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handler ──────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ── Routers ────────────────────────────────────────────────────────────

from app.auth.router import router as auth_router
from app.routers.contracts import router as contracts_router
from app.routers.evaluations import router as evaluations_router
from app.routers.benchmarks import router as benchmarks_router
from app.routers.comparisons import router as comparisons_router
from app.routers.datasets import router as datasets_router
from app.routers.failures import router as failures_router
from app.routers.leaderboard import router as leaderboard_router
from app.routers.reports import router as reports_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(contracts_router, prefix="/api/v1")
app.include_router(evaluations_router, prefix="/api/v1")
app.include_router(benchmarks_router, prefix="/api/v1")
app.include_router(comparisons_router, prefix="/api/v1")
app.include_router(datasets_router, prefix="/api/v1")
app.include_router(failures_router, prefix="/api/v1")
app.include_router(leaderboard_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")


# ── Health Check ───────────────────────────────────────────────────────

@app.get("/api/v1/live")
async def liveness_check():
    """Lightweight liveness endpoint (no external dependency checks)."""
    return {"status": "alive", "version": "1.0.0"}


@app.get("/api/v1/health")
async def health_check():
    """Readiness health endpoint with dependency checks."""
    db_status = "ok"
    redis_status = "ok"
    try:
        from sqlalchemy import text
        from app.database import async_session_factory
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = "error"
        logger.warning("health_database_error", error=str(exc))

    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.redis_url, socket_timeout=2)
        r.ping()
    except Exception as exc:
        redis_status = "error"
        logger.warning("health_redis_error", error=str(exc))

    overall = "healthy" if db_status == "ok" and redis_status == "ok" else "degraded"
    return {"status": overall, "version": "1.0.0", "database": db_status, "redis": redis_status}
