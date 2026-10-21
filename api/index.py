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
    err_trace = traceback.format_exc()
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse

        app = FastAPI(title="TraceGuard Diagnostic")

        @app.api_route("/", methods=["GET", "POST", "PUT", "DELETE"])
        @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
        async def catch_all(path_name: str = ""):
            return JSONResponse(
                status_code=500,
                content={
                    "detail": f"TraceGuard startup error on Vercel: {str(e)}",
                    "traceback": err_trace,
                    "sys_path": sys.path,
                }
            )
    except Exception as inner_e:
        # Fallback pure ASGI handler in case FastAPI is missing from Python environment
        async def app(scope, receive, send):
            if scope["type"] == "http":
                body = (
                    f'{{"detail": "FastAPI failed to import: {str(inner_e)}", '
                    f'"original_error": "{str(e)}"}}\n'
                ).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"content-length", str(len(body)).encode("utf-8")],
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": body,
                })

# Vercel WSGI/ASGI handler export
__all__ = ["app"]
