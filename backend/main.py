"""TraceGuard FastAPI Application Entrypoint (Milestone 7 Production Ready)."""
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from backend.api.benchmarks import router as benchmarks_router
from backend.api.diagnostics import (
    exp_diag_router,
    router as diagnostics_router,
    task_diag_router,
)
from backend.api.experiments import router as experiments_router
from backend.api.recovery import router as recovery_router
from backend.api.tasks import router as tasks_router
from backend.api.traces import router as traces_router
from backend.config import settings
from backend.tracing.storage import TraceStorage

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("traceguard")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing TraceGuard Platform (Milestone 7: Production Ready)...")
    logger.info(f"Environment: {settings.TRACEGUARD_ENV}")
    logger.info(f"Model Adapter: {settings.MODEL_ADAPTER}")
    logger.info(f"Database Path: {settings.DATABASE_PATH}")

    # Validate configuration on startup
    warnings = settings.validate_configuration()
    for w in warnings:
        logger.warning(f"Configuration advisory: {w}")

    # Warm up SQLite database and WAL mode
    try:
        storage = TraceStorage()
        health = storage.check_health()
        logger.info(f"SQLite Persistence verified: status={health['status']}, journal_mode={health.get('journal_mode')}")
    except Exception as e:
        logger.warning(f"Advisory during initial database health check: {e}")

    yield
    logger.info("TraceGuard platform gracefully shut down.")

app = FastAPI(
    title="TraceGuard: AI Agent Reliability & Recovery Platform",
    description=(
        "An Evidence-Driven Reliability and Recovery Platform for Tool-Using AI Agents. "
        "Milestones 1–7: Full-Stack Verification, Experimentation, Failure Diagnosis, and Recovery."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Request Correlation ID and Structured Logging Middleware
@app.middleware("http")
async def correlation_id_and_logging_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    t_start = time.perf_counter()

    # Pass request ID in request state
    request.state.request_id = req_id

    try:
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - t_start) * 1000
        response.headers["X-Request-ID"] = req_id

        # Log request at appropriate level
        if request.url.path != "/health":
            logger.info(
                f"[{req_id}] {request.method} {request.url.path} -> "
                f"{response.status_code} ({duration_ms:.1f}ms)"
            )
        return response
    except Exception as exc:
        duration_ms = (time.perf_counter() - t_start) * 1000
        logger.exception(f"[{req_id}] Unhandled error during {request.method} {request.url.path}: {exc}")

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": f"Internal server error: {str(exc)}",
                "request_id": req_id
            },
            headers={"X-Request-ID": req_id}
        )

# Enable CORS for local dev, Docker, and Vercel domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers (support both direct and /api prefixed routes for Vercel)
for r in [
    tasks_router,
    traces_router,
    experiments_router,
    benchmarks_router,
    diagnostics_router,
    task_diag_router,
    exp_diag_router,
    recovery_router,
]:
    app.include_router(r)
    app.include_router(r, prefix="/api")

@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirect root to OpenAPI docs."""
    return RedirectResponse(url="/docs")

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
@app.get("/api/health", status_code=status.HTTP_200_OK, tags=["Health"])
def health_check() -> Dict[str, Any]:
    """Returns the API health status, database connectivity, and configuration info."""
    db_status = "unknown"
    db_info = {}
    try:
        storage = TraceStorage()
        db_info = storage.check_health()
        db_status = db_info.get("status", "error")
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "service": "traceguard-baseline-agent",
        "environment": settings.TRACEGUARD_ENV,
        "model_adapter": settings.MODEL_ADAPTER,
        "default_max_steps": settings.DEFAULT_MAX_STEPS,
        "database_status": db_status,
        "database_counts": db_info.get("counts", {}),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=not settings.is_production)
