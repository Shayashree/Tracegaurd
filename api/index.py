"""Vercel serverless entrypoint for TraceGuard FastAPI backend."""
import sys
import os
import traceback
from pathlib import Path

# Ensure root directory and backend directory are in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

try:
    from backend.main import app
except Exception as e:
    traceback.print_exc(file=sys.stderr)
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title="TraceGuard Fallback")

    @app.api_route("/", methods=["GET", "POST", "PUT", "DELETE"])
    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catch_all(path_name: str = ""):
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"TraceGuard startup error on Vercel: {str(e)}",
                "traceback": traceback.format_exc(),
            }
        )

# Vercel WSGI/ASGI handler export
__all__ = ["app"]
