"""Vercel serverless entrypoint for TraceGuard FastAPI backend."""
import sys
from pathlib import Path

# Ensure root directory is in sys.path so backend modules are importable in Vercel runtime
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.main import app

# Vercel WSGI/ASGI handler export
__all__ = ["app"]
