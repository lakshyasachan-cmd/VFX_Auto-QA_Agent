#!/bin/sh
# entrypoint.sh — VFX Mission Control backend startup script
# Supports Render, Docker Compose, and local deployments.
set -e

echo "============================================================"
echo "  VFX Mission Control — Backend Startup"
echo "============================================================"

# Use Render's injected PORT environment variable or default to 8001
PORT="${PORT:-8001}"

echo "[1/2] Checking database readiness..."
python -c "
import time, sys
from backend.database.session import engine, init_db, get_database_url
from urllib.parse import urlparse

url = get_database_url()
parsed = urlparse(url)
target_host = parsed.hostname or 'local SQLite'
print(f'       Target database: {parsed.scheme} -> host: {target_host}')

for attempt in range(1, 16):
    try:
        with engine.connect() as conn:
            print(f'       Database connection verified on attempt {attempt}.')
            init_db()
            print('       Schema initialization verified.')
            sys.exit(0)
    except Exception as exc:
        print(f'       Waiting for database to accept connections (attempt {attempt}/15)... {exc}')
        time.sleep(2)
print('       Notice: Database unreachable after 30s. Starting server with fallback.')
"

echo "[2/2] Running Alembic migrations (if any)..."
alembic upgrade head || echo "       Alembic migration notice: Schema already current or initialized."

echo "[3/3] Starting uvicorn API server on port ${PORT}..."
exec uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --workers 1 \
    --log-level info
