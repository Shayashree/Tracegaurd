"""Benchmark Dataset Loader and Validator for TraceGuard."""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import ValidationError
from backend.config import settings
from backend.evaluation.schemas import BenchmarkTask

logger = logging.getLogger(__name__)

class BenchmarkDatasetError(Exception):
    """Raised when benchmark dataset loading or validation fails."""
    pass

class BenchmarkDatasetLoader:
    """Loads and validates versioned benchmark JSONL task datasets."""

    def __init__(self, benchmarks_dir: Optional[Path] = None):
        self.benchmarks_dir = benchmarks_dir or Path(settings.DATA_DIR) / "benchmarks"

    def _resolve_file(self, version: str) -> Path:
        # Standard naming: benchmark_v1.jsonl or benchmark_{version}.jsonl
        clean_v = version.lower().replace(".", "_")
        filename = f"benchmark_{clean_v}.jsonl"
        filepath = self.benchmarks_dir / filename
        if not filepath.exists():
            # Check direct version name
            alt_path = self.benchmarks_dir / f"benchmark_{version}.jsonl"
            if alt_path.exists():
                return alt_path
            # Check v1 fallback
            v1_path = self.benchmarks_dir / "benchmark_v1.jsonl"
            if v1_path.exists() and version in ("v1.0", "v1"):
                return v1_path
            raise BenchmarkDatasetError(
                f"Benchmark dataset for version '{version}' not found at {filepath}."
            )
        return filepath

    def load_tasks(
        self,
        version: str = "v1.0",
        task_ids: Optional[List[str]] = None,
        category: Optional[str] = None
    ) -> List[BenchmarkTask]:
        """
        Loads and validates tasks from benchmark JSONL file.
        Enforces unique task IDs and schema conformance.
        """
        filepath = self._resolve_file(version)
        tasks: List[BenchmarkTask] = []
        seen_ids = set()

        with open(filepath, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                clean_line = line.strip()
                if not clean_line or clean_line.startswith("#"):
                    continue

                try:
                    data = json.loads(clean_line)
                except json.JSONDecodeError as e:
                    raise BenchmarkDatasetError(
                        f"Malformed JSON on line {line_no} in {filepath.name}: {e}"
                    )

                try:
                    task = BenchmarkTask.model_validate(data)
                except ValidationError as e:
                    raise BenchmarkDatasetError(
                        f"Validation error for task on line {line_no} in {filepath.name}: {e.errors()}"
                    )

                if task.task_id in seen_ids:
                    raise BenchmarkDatasetError(
                        f"Duplicate task ID '{task.task_id}' detected on line {line_no} in {filepath.name}."
                    )
                seen_ids.add(task.task_id)

                # Filter by task_ids if specified
                if task_ids is not None and task.task_id not in task_ids:
                    continue

                # Filter by category if specified
                if category is not None and task.category != category:
                    continue

                tasks.append(task)

        logger.info(f"Loaded {len(tasks)} benchmark tasks (version: {version}, category filter: {category})")
        return tasks

    def list_available_benchmarks(self) -> List[Dict[str, Any]]:
        """List available benchmark files, versions, and category task counts."""
        if not self.benchmarks_dir.exists():
            return []

        results = []
        for file in sorted(self.benchmarks_dir.glob("benchmark_*.jsonl")):
            version = file.stem.replace("benchmark_", "").replace("_", ".")
            try:
                tasks = self.load_tasks(version=version)
                counts: Dict[str, int] = {}
                for t in tasks:
                    counts[t.category] = counts.get(t.category, 0) + 1
                results.append({
                    "benchmark_version": version,
                    "filename": file.name,
                    "total_tasks": len(tasks),
                    "categories": counts
                })
            except Exception as e:
                logger.warning(f"Failed to inspect benchmark {file.name}: {e}")
                continue

        return results
