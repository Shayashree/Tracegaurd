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

    SPLIT_MAPPINGS: Dict[str, str] = {
        # Train / Dev (Development tasks for rule tuning)
        "ARITH-001": "train", "ARITH-002": "train", "ARITH-003": "train", "ARITH-004": "train", "ARITH-005": "train",
        "DATA-001": "train", "DATA-002": "train", "DATA-003": "train", "DATA-004": "train", "DATA-005": "train",
        "DOC-001": "train", "DOC-002": "train", "DOC-003": "train", "DOC-004": "train", "DOC-005": "train",
        "MULTI-001": "train", "MULTI-002": "train", "MULTI-003": "train", "MULTI-004": "train", "MULTI-005": "train",
        "FAIL-001": "train", "FAIL-002": "train", "FAIL-003": "train", "FAIL-004": "train",

        # Validation (Threshold tuning)
        "ARITH-006": "val", "ARITH-007": "val",
        "DATA-006": "val", "DATA-007": "val",
        "DOC-006": "val", "DOC-007": "val",
        "MULTI-006": "val", "MULTI-007": "val",
        "FAIL-005": "val", "FAIL-006": "val",

        # Held-out Test (Final evaluation)
        "ARITH-008": "test", "ARITH-009": "test",
        "DATA-008": "test", "DATA-009": "test",
        "DOC-008": "test", "DOC-009": "test",
        "MULTI-008": "test", "MULTI-009": "test",
        "FAIL-007": "test", "FAIL-008": "test",
    }

    @classmethod
    def get_task_split(cls, task_id: str) -> str:
        """Returns the dataset split for a given task ID ('train', 'val', or 'test')."""
        return cls.SPLIT_MAPPINGS.get(task_id, "train")

    def load_tasks(
        self,
        version: str = "v1.0",
        task_ids: Optional[List[str]] = None,
        category: Optional[str] = None,
        split: Optional[str] = None
    ) -> List[BenchmarkTask]:
        """
        Loads and validates tasks from benchmark JSONL file.
        Enforces unique task IDs, schema conformance, and optional split filtering.
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

                # Filter by split if specified
                if split is not None and self.get_task_split(task.task_id) != split:
                    continue

                tasks.append(task)

        logger.info(f"Loaded {len(tasks)} benchmark tasks (version: {version}, category: {category}, split: {split})")
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
