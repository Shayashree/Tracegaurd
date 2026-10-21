"""Vercel serverless entrypoint for TraceGuard FastAPI backend."""
import sys
import os
from pathlib import Path

# Ensure root directory and backend directory are in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from backend.main import app

# Explicit top-level handler assignments for @vercel/python AST scanner
handler = app

__all__ = ["app", "handler"]
