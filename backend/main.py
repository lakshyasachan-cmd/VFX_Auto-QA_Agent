"""
FastAPI application entry point for the VFX Event Ingestion Subsystem.
"""

import sys
from pathlib import Path

# Ensure project root is always on sys.path regardless of where uvicorn is launched from
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Load .env file from project root with override=True to reload updated variables
from dotenv import load_dotenv
load_dotenv(dotenv_path=ROOT_DIR / ".env", override=True)



from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.events.api import router as events_router
from backend.events.redis_client import create_redis_client
from backend.events.service import EventIngestionService
from backend.governance.api import router as governance_router
from backend.incidents.api import router as incidents_router
from backend.mcp.api import router as mcp_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("vfx.events.main")




@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: test database connection and log status
    from sqlalchemy import text
    from backend.database.session import engine
    try:
        with engine.connect() as conn:
            db_name = conn.execute(text("SELECT current_database();")).scalar()
            db_user = conn.execute(text("SELECT current_user;")).scalar()
            logger.info("Connected to database '%s' as user '%s' (%s).", db_name, db_user, engine.url.drivername)
    except Exception as exc:
        logger.error("Database connection failed: %s", exc)

    # Startup: attempt Redis connection with graceful fallback to in-memory mode
    redis_client = None
    try:
        redis_client = await create_redis_client()
        # Verify connection
        await redis_client.ping()
        logger.info("Connected to Redis event bus.")
    except Exception as exc:
        logger.warning("Could not connect to Redis (%s). Initializing service with in-memory store.", exc)
        redis_client = None

    service = EventIngestionService(redis_client=redis_client)

    app.state.event_service = service
    app.state.redis_client = redis_client

    yield

    # Shutdown
    if redis_client is not None:
        try:
            await redis_client.aclose()
            logger.info("Closed Redis connection.")
        except Exception as exc:
            logger.warning("Error closing Redis connection: %s", exc)


import uuid
from fastapi import Request, Response
from backend.common.logging import (
    configure_logging,
    correlation_id_ctx,
    incident_id_ctx,
    get_logger,
)
from backend.common.rate_limit import global_rate_limiter

# Initialize structured logging
configure_logging(level="INFO", json_format=True)
logger = get_logger("vfx.events.main")

app = FastAPI(
    title="VFX Event Ingestion & Normalization API",
    description="Event-driven ingestion platform for VFX production incidents (Deadline, Tractor, OpenCue, ShotGrid, Asset Storage).",
    version="1.0.0",
    lifespan=lifespan,
)

import os
cors_env = os.getenv("CORS_ORIGINS", "").strip()
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://dashboard:3000",
    "http://localhost",
    "http://localhost:80",
]
if cors_env and cors_env != "*":
    allowed_origins.extend([orig.strip() for orig in cors_env.split(",") if orig.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if cors_env == "*" else allowed_origins,
    allow_origin_regex=r"https://.*" if cors_env == "*" else r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.middleware("http")
async def correlation_and_security_middleware(request: Request, call_next):
    """
    Middleware establishing correlation tracking and rate limiting across HTTP requests.
    Extracts or generates X-Correlation-ID and populates context variables.
    """
    corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    inc_id = request.headers.get("X-Incident-ID")
    correlation_id_ctx.set(corr_id)
    if inc_id:
        incident_id_ctx.set(inc_id)

    # Apply rate limiting
    client_key = request.headers.get("X-API-Key") or (request.client.host if request.client else "unknown")
    allowed, remaining, reset_after = global_rate_limiter.is_allowed(client_key)
    if not allowed:
        return Response(
            content='{"error": "Rate limit exceeded", "retry_after": ' + str(int(reset_after) + 1) + "}",
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": str(int(reset_after) + 1), "X-Correlation-ID": corr_id},
        )

    response: Response = await call_next(request)
    response.headers["X-Correlation-ID"] = corr_id
    if inc_id:
        response.headers["X-Incident-ID"] = inc_id
    return response

app.include_router(events_router)
app.include_router(governance_router)
app.include_router(governance_router, prefix="/api/v1/governance/approvals")
app.include_router(mcp_router)
app.include_router(incidents_router)


@app.get("/", summary="Root index")
async def root():
    return {
        "service": "VFX Mission Control API",
        "status": "online",
        "documentation": "/docs",
        "health_check": "/api/v1/health",
        "mcp_tools": "/api/v1/mcp/tools",
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=True)

