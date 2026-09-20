# VFX Mission Control — Deployment Guide

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (v24+, with Compose v2)
- `.env` file at project root (copy from `.env.example` and fill in your keys)

> **No other local software is required.** PostgreSQL, Redis, the Python backend, and the Next.js dashboard all run inside Docker containers.

---

## Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env and fill in your GEMINI_API_KEY and studio credentials.
# Deadline, ShotGrid, and watsonx credentials are optional — the system
# runs in demo/simulation mode without them.

# 2. Build and launch all five services
docker compose up --build -d

# 3. Verify all services are healthy
docker compose ps
# Expected output — all services should show "healthy":
# NAME              STATUS
# vfx_postgres      Up X seconds (healthy)
# vfx_redis         Up X seconds (healthy)
# vfx_backend       Up X seconds (healthy)
# vfx_dashboard     Up X seconds (healthy)
# vfx_nginx         Up X seconds

# 4. Open the platform
#    Mission Control Dashboard:   http://localhost
#    Backend REST API:            http://localhost/api/v1
#    Interactive API Docs:        http://localhost/docs
```

---

## Service Architecture

```
Browser
  │
  ▼
┌─────────────────────┐   port 80
│   Nginx (Reverse    │◄──────────────── http://localhost
│   Proxy + SSE Gate) │
└──────┬──────────────┘
       │ /api/*              /*
       ▼                     ▼
┌────────────┐        ┌─────────────┐
│  FastAPI   │        │  Next.js    │
│  Backend   │        │  Dashboard  │
│  :8001     │        │  :3000      │
└─────┬──────┘        └─────────────┘
      │
      ├──► PostgreSQL :5432  (vfx_postgres_data volume)
      └──► Redis      :6379  (vfx_redis_data volume)
```

---

## Port Mapping

| Service | Container Port | Host Port | Notes |
|:---|:---:|:---:|:---|
| Nginx | 80 | **80** | Primary access point for all traffic |
| FastAPI Backend | 8001 | 8001 | Direct access (optional) |
| Next.js Dashboard | 3000 | 3000 | Direct access (optional) |
| PostgreSQL | 5432 | **5433** | Offset to avoid clash with local Postgres |
| Redis | 6379 | **6380** | Offset to avoid clash with local Redis |

---

## Common Operations

```bash
# View real-time logs for any service
docker compose logs -f backend
docker compose logs -f dashboard
docker compose logs -f nginx
docker compose logs -f postgres

# Restart a single service
docker compose restart backend

# Rebuild and restart after code changes
docker compose up --build -d backend
docker compose up --build -d dashboard

# Run backend tests (local, not in Docker)
python -m pytest tests/

# Open a shell inside the backend container
docker compose exec backend sh

# Run Alembic migrations manually inside the container
docker compose exec backend alembic upgrade head

# Verify database connectivity
docker compose exec postgres psql -U vfx_user -d vfx_mission_control -c "\dt"
```

---

## Data Persistence

PostgreSQL and Redis data are stored in named Docker volumes:

| Volume | Service | Purpose |
|:---|:---|:---|
| `vfx_postgres_data` | postgres | All incident records, agent findings, audit logs |
| `vfx_redis_data` | redis | Event streams and idempotency keys (AOF persistent) |

```bash
# Stop without losing data
docker compose down

# Stop AND delete all data volumes (full reset)
docker compose down -v
```

---

## Environment Variables Reference

See [`.env.example`](./.env.example) for the full list. Key variables:

| Variable | Required | Description |
|:---|:---:|:---|
| `GEMINI_API_KEY` | ✅ | Google Gemini API key for live AI reasoning |
| `POSTGRES_USER` | ✅ | PostgreSQL username |
| `POSTGRES_PASSWORD` | ✅ | PostgreSQL password |
| `POSTGRES_DB` | ✅ | PostgreSQL database name |
| `VFX_ADMIN_API_KEY` | ✅ | Admin RBAC API key |
| `VFX_LEAD_TD_API_KEY` | ✅ | Lead TD RBAC API key |
| `VFX_TD_API_KEY` | ✅ | TD RBAC API key |
| `VFX_SYSTEM_API_KEY` | ✅ | System automation RBAC key |
| `DEADLINE_REST_URL` | ⚙️ | Thinkbox Deadline Web Service URL (optional) |
| `SHOTGRID_URL` | ⚙️ | Autodesk ShotGrid URL (optional) |
| `SHOTGRID_API_KEY` | ⚙️ | ShotGrid script key (optional) |
| `WATSONX_MOCK` | — | Set `true` to run Watson in demo mode (default) |

---

## Troubleshooting

**Backend fails to start (`Connection refused` on Postgres):**
```bash
# Wait for postgres to be healthy, then try:
docker compose restart backend
```

**Dashboard shows "Backend Offline" banner:**
```bash
# Check if backend is healthy:
docker compose ps
curl http://localhost/api/v1/health
```

**Port 80 already in use:**
```bash
# Edit docker-compose.yml: change "80:80" to "8080:80" under nginx ports
# Then access via http://localhost:8080
```

**Full reset:**
```bash
docker compose down -v --remove-orphans
docker compose up --build -d
```
