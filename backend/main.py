"""TraceGuard FastAPI Application Entrypoint."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from backend.api.tasks import router as tasks_router
from backend.api.traces import router as traces_router
from backend.api.experiments import router as experiments_router
from backend.api.benchmarks import router as benchmarks_router
from backend.api.diagnostics import (
    router as diagnostics_router,
    task_diag_router,
    exp_diag_router,
)
from backend.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("traceguard")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting TraceGuard API (Milestone 3: Trajectory Failure Detector)...")
    logger.info(f"Model Adapter: {settings.MODEL_ADAPTER}")
    logger.info(f"Default Max Steps: {settings.DEFAULT_MAX_STEPS}")
    yield
    logger.info("Shutting down TraceGuard API...")

app = FastAPI(
    title="TraceGuard: AI Agent Reliability & Recovery Platform",
    description=(
        "An Evidence-Driven Reliability and Recovery Platform for Tool-Using AI Agents. "
        "Milestone 3: Trajectory-Based Failure Detection Engine."
    ),
    version="0.3.0",
    lifespan=lifespan
)

# Enable CORS for future dashboard and cross-origin access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(tasks_router)
app.include_router(traces_router)
app.include_router(experiments_router)
app.include_router(benchmarks_router)
app.include_router(diagnostics_router)
app.include_router(task_diag_router)
app.include_router(exp_diag_router)

@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirect root to OpenAPI docs."""
    return RedirectResponse(url="/docs")

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
def health_check():
    """Returns the API health status and configuration info."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "service": "traceguard-baseline-agent",
        "model_adapter": settings.MODEL_ADAPTER,
        "default_max_steps": settings.DEFAULT_MAX_STEPS,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
