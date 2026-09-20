#!/bin/sh
# entrypoint.sh — VFX Mission Control backend startup script
# Runs Alembic migrations then launches the uvicorn API server.
set -e

echo "============================================================"
echo "  VFX Mission Control — Backend Startup"
echo "============================================================"

echo "[1/2] Running Alembic database migrations..."
alembic upgrade head
echo "       Migrations complete."

echo "[2/2] Starting uvicorn API server on port 8001..."
exec uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8001 \
    --workers 2 \
    --log-level info
