"""Benchmark dataset query and metadata endpoints."""
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from backend.evaluation.dataset import BenchmarkDatasetError, BenchmarkDatasetLoader
from backend.evaluation.schemas import BenchmarkTask

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/benchmarks", tags=["Benchmarks"])
_loader = BenchmarkDatasetLoader()

@router.get("", response_model=List[Dict[str, Any]])
def list_benchmarks() -> List[Dict[str, Any]]:
    """List available benchmark versions and task counts broken down by category."""
    return _loader.list_available_benchmarks()

@router.get("/{benchmark_version}/tasks", response_model=List[BenchmarkTask])
def get_benchmark_tasks(
    benchmark_version: str,
    category: Optional[str] = Query(None, description="Optional category filter"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
) -> List[BenchmarkTask]:
    """Retrieve benchmark tasks for the specified version with optional filtering and pagination."""
    try:
        tasks = _loader.load_tasks(version=benchmark_version, category=category)
        return tasks[offset : offset + limit]
    except BenchmarkDatasetError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
