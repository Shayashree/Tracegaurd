"""Reproducibility manifest creation and export for TraceGuard Milestone 5."""
import platform
import subprocess
import sys
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.evaluation.experiment_config import ExperimentConfig, sanitize_dict_for_hashing
from backend.tracing.event_schema import current_utc_timestamp

def get_git_revision() -> Optional[str]:
    """Retrieves current Git commit SHA if git repository is available."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2.0
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None

class EnvironmentInfo(BaseModel):
    """Execution environment details for reproducibility audit."""
    python_version: str = Field(default_factory=lambda: sys.version.split()[0])
    os_platform: str = Field(default_factory=lambda: f"{platform.system()} {platform.release()}")
    processor: str = Field(default_factory=lambda: platform.processor() or "Unknown")
    git_commit: Optional[str] = Field(default_factory=get_git_revision)

class ReproducibilityManifest(BaseModel):
    """Immutable reproducibility manifest documenting experiment conditions."""
    experiment_id: str
    configuration_hash: str
    experiment_version: str = "v1.0"
    benchmark_version: str = "v1.0"
    dataset_split: str = "all"
    experiment_type: str = "standard"
    agent_modes: List[str] = Field(default_factory=list)
    model_configuration: Dict[str, Any] = Field(default_factory=dict)
    tool_configuration: Dict[str, Any] = Field(default_factory=dict)
    failure_injection_configuration: Dict[str, Any] = Field(default_factory=dict)
    execution_limits: Dict[str, Any] = Field(default_factory=dict)
    random_seed: Optional[int] = None
    environment: EnvironmentInfo = Field(default_factory=EnvironmentInfo)
    package_versions: Dict[str, str] = Field(default_factory=dict)
    artifact_references: Dict[str, str] = Field(default_factory=dict)
    created_at: str = Field(default_factory=current_utc_timestamp)

def create_reproducibility_manifest(
    config: ExperimentConfig,
    artifact_references: Optional[Dict[str, str]] = None
) -> ReproducibilityManifest:
    """Generates an audit-grade reproducibility manifest with strictly sanitized credentials."""
    model_cfg = sanitize_dict_for_hashing(config.model_configuration)
    tool_cfg = sanitize_dict_for_hashing(config.tool_configuration)
    fail_cfg = sanitize_dict_for_hashing(config.failure_injection_configuration)

    packages = {}
    for pkg in ["fastapi", "pydantic", "pytest", "httpx", "sqlite3"]:
        try:
            mod = __import__(pkg)
            packages[pkg] = getattr(mod, "__version__", "builtin")
        except Exception:
            packages[pkg] = "not_installed"

    exec_limits = {
        "step_limit": config.step_limit,
        "task_timeout_seconds": config.task_timeout,
        "recovery_budget": config.recovery_budget
    }

    return ReproducibilityManifest(
        experiment_id=config.experiment_id,
        configuration_hash=config.configuration_hash or "unhashed",
        experiment_version=config.experiment_version,
        benchmark_version=config.benchmark_version,
        dataset_split=config.dataset_split,
        experiment_type=config.experiment_type,
        agent_modes=config.agent_modes,
        model_configuration=model_cfg,
        tool_configuration=tool_cfg,
        failure_injection_configuration=fail_cfg,
        execution_limits=exec_limits,
        random_seed=config.random_seed,
        environment=EnvironmentInfo(),
        package_versions=packages,
        artifact_references=artifact_references or {},
        created_at=current_utc_timestamp()
    )
