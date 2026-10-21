"""Vercel serverless entrypoint for TraceGuard FastAPI backend."""
import sys
import os
import traceback
import urllib.parse
from pathlib import Path

# Ensure root directory and backend directory are in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

try:
    from backend.main import app as fastapi_app

    # Ensure /api, /api/index, and /api/index.py respond gracefully
    @fastapi_app.get("/api", include_in_schema=False)
    @fastapi_app.get("/api/index", include_in_schema=False)
    @fastapi_app.get("/api/index.py", include_in_schema=False)
    def api_root():
        return {
            "status": "ok",
            "service": "TraceGuard Platform API",
            "health": "/health",
            "docs": "/docs",
        }

    # Wrap in ASGI adapter to correct scope["path"] when routed via Vercel rewrites
    async def app(scope, receive, send):
        if scope.get("type") == "http":
            headers = dict(scope.get("headers", []))
            # Vercel supplies x-forwarded-uri with the original requested URL
            fwd_uri = headers.get(b"x-forwarded-uri")
            if fwd_uri:
                orig_path = urllib.parse.urlparse(fwd_uri.decode("utf-8", "ignore")).path
                if orig_path:
                    scope = dict(scope)
                    scope["path"] = orig_path
            elif b"x-matched-path" in headers:
                matched = headers[b"x-matched-path"].decode("utf-8", "ignore")
                if matched and not matched.startswith("/api/index"):
                    scope = dict(scope)
                    scope["path"] = matched

        await fastapi_app(scope, receive, send)

except Exception as e:
    err_trace = traceback.format_exc()
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse

        diagnostic_app = FastAPI(title="TraceGuard Diagnostic")

        @diagnostic_app.api_route("/", methods=["GET", "POST", "PUT", "DELETE"])
        @diagnostic_app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
        async def catch_all(path_name: str = ""):
            return JSONResponse(
                status_code=500,
                content={
                    "detail": f"TraceGuard startup error on Vercel: {str(e)}",
                    "traceback": err_trace,
                    "sys_path": sys.path,
                }
            )

        async def app(scope, receive, send):
            await diagnostic_app(scope, receive, send)

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
