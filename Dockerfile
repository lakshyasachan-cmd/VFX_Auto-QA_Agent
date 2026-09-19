FROM python:3.11-slim

WORKDIR /app

# Python runtime flags only — no application secrets baked in
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source only (no tests in production image)
COPY backend/ ./backend/
COPY simulations/ ./simulations/
COPY migrations/ ./migrations/
COPY alembic.ini .

EXPOSE 8001

# Run DB migrations then start the API server
CMD alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8001

