# ─── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies only (not shipped to runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies into an isolated prefix
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system deps only (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Runtime env flags — no secrets baked in
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create non-root user for security
RUN groupadd -r vfx_app && useradd -r -g vfx_app vfx_app

# Copy only application source — no tests, no .env, no dev tooling
COPY backend/ ./backend/
COPY simulations/ ./simulations/
COPY migrations/ ./migrations/
COPY alembic.ini .
COPY entrypoint.sh .

# Lock down file ownership and make entrypoint executable
RUN chmod +x entrypoint.sh && chown -R vfx_app:vfx_app /app

USER vfx_app

EXPOSE 8001

ENTRYPOINT ["./entrypoint.sh"]
