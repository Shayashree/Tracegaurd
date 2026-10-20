# TraceGuard Deployment Guide

## 1. Overview

TraceGuard supports two deployment configurations:
1. **Local Bare-Metal Development / Evaluation** (Windows, macOS, Linux with Python 3.11+ and Node.js 20+)
2. **Containerized Production Deployment** (Docker & Docker Compose with persistent named volumes and Nginx reverse proxy)

---

## 2. Local Bare-Metal Setup

### Prerequisites
- Python 3.11 or 3.12 (Python 3.14 compatible)
- Node.js 20+ and npm 10+
- Git

### Backend Setup
```bash
# 1. Clone repository and navigate to root
cd "d:/1C Project"

# 2. (Optional) Create virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment configuration
cp .env.example .env

# 5. Start FastAPI backend (development reload mode)
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Backend API will be accessible at `http://127.0.0.1:8000`. Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

### Frontend Setup
```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies cleanly
npm ci

# 3. Copy frontend environment template
cp .env.example .env

# 4. Start Vite development server
npm run dev
```
The interactive React dashboard will be accessible at `http://localhost:5173`.

---

## 3. Containerized Deployment (Docker Compose)

The multi-container Docker Compose configuration coordinates:
- `traceguard-backend`: Python 3.11-slim container running Uvicorn with a non-root system user (`appuser:10001`), database healthchecks, and SQLite WAL volume persistence.
- `traceguard-frontend`: Multi-stage build producing an Alpine Nginx container serving static SPA assets and reverse-proxying API routes.
- `traceguard_data`: Named persistent volume mounted to `/app/data` to ensure experiment runs and traces survive container recreation.

### Starting Services
```bash
docker compose up --build -d
```
- Web Application: `http://localhost:3000`
- Direct Backend API: `http://localhost:8000`
- Backend Health Check: `http://localhost:8000/health`

### Stopping Services
```bash
# Stop containers while preserving database volume
docker compose down

# Stop containers and remove volumes (CAUTION: deletes SQLite database)
docker compose down -v
```

---

## 4. Production Configuration & Environment Variables

| Variable | Default Value | Description |
|---|---|---|
| `TRACEGUARD_ENV` | `production` | Environment mode (`development`, `testing`, `production`). In production, strict CORS and secret masking are enforced. |
| `API_HOST` | `0.0.0.0` | IP binding for backend ASGI server. |
| `API_PORT` | `8000` | Port for backend ASGI server. |
| `DATABASE_PATH` | `/app/data/traceguard.db` | Absolute or relative path to SQLite database file. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowlist of permitted origins. Wildcards are rejected in production. |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `MODEL_ADAPTER` | `mock` | Selected model provider (`mock` for offline evaluation, `openai` for live LLM). |
| `OPENAI_API_KEY` | *(None)* | OpenAI secret key (required only if `MODEL_ADAPTER=openai`). |
| `OPENAI_MODEL_NAME` | `gpt-4o-mini` | Target OpenAI model identifier. |

---

## 5. Database Persistence, Backup, and Recovery

### SQLite WAL Mode
TraceGuard enables Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) and a busy timeout of 15,000 ms to provide reliable multi-reader/single-writer concurrent access without database locked errors.

### Creating an Online Hot Backup
TraceGuard provides an online atomic backup mechanism that does not disrupt active tasks:
```python
from backend.tracing.storage import TraceStorage

storage = TraceStorage("traceguard.db")
backup_path = storage.backup_database("traceguard_backup.db")
print(f"Backup created at: {backup_path}")
```

### Restoring from Backup
```python
from backend.tracing.storage import TraceStorage

storage = TraceStorage("traceguard.db")
storage.restore_database("traceguard_backup.db")
print("Database restored successfully.")
```
