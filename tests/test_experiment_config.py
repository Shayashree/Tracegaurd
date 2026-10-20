"""Tests for ExperimentConfig, validation rules, and canonical configuration hashing."""
import pytest
from backend.evaluation.experiment_config import (
    ExperimentConfig,
    compute_configuration_hash,
    sanitize_dict_for_hashing,
)

def test_experiment_config_defaults():
    """Verify default fields and automatic canonical hash computation."""
    cfg = ExperimentConfig()
    assert cfg.experiment_id.startswith("exp_")
    assert cfg.benchmark_version == "v1.0"
    assert cfg.dataset_split == "all"
    assert cfg.experiment_type == "standard"
    assert set(cfg.agent_modes) == {"baseline", "fixed_retry", "traceguard_recovery"}
    assert cfg.configuration_hash is not None
    assert len(cfg.configuration_hash) == 64  # SHA-256 hex string

def test_canonical_hash_stability():
    """Identical configurations must produce the exact same SHA-256 hash regardless of key order or experiment ID."""
    cfg1 = ExperimentConfig(
        experiment_id="exp_test111",
        benchmark_version="v1.0",
        dataset_split="train",
        agent_modes=["baseline", "fixed_retry"],
        step_limit=10,
    )
    cfg2 = ExperimentConfig(
        experiment_id="exp_test222",
        benchmark_version="v1.0",
        dataset_split="train",
        agent_modes=["baseline", "fixed_retry"],
        step_limit=10,
    )
    assert cfg1.configuration_hash == cfg2.configuration_hash

def test_canonical_hash_differs_on_configuration_change():
    """Modifying configuration limits or modes must change the configuration hash."""
    cfg1 = ExperimentConfig(step_limit=8)
    cfg2 = ExperimentConfig(step_limit=12)
    assert cfg1.configuration_hash != cfg2.configuration_hash

def test_secret_redaction_in_hash():
    """Sensitive credential keys must be redacted prior to hashing."""
    raw_dict = {
        "model_configuration": {
            "api_key": "sk-secret123456",
            "token": "tok-9999",
            "temperature": 0.0,
        },
        "step_limit": 8,
    }
    sanitized = sanitize_dict_for_hashing(raw_dict)
    assert sanitized["model_configuration"]["api_key"] == "[REDACTED]"
    assert sanitized["model_configuration"]["token"] == "[REDACTED]"
    assert sanitized["model_configuration"]["temperature"] == 0.0

def test_invalid_agent_mode_rejection():
    """Unsupported agent modes must be rejected with ValueError."""
    with pytest.raises(ValueError, match="Unsupported agent mode 'unsupported_mode'"):
        ExperimentConfig(agent_modes=["baseline", "unsupported_mode"])

def test_empty_agent_modes_rejection():
    """Empty agent mode lists must be rejected."""
    with pytest.raises(ValueError, match="At least one agent mode must be specified"):
        ExperimentConfig(agent_modes=[])

def test_experiment_type_automatic_adjustments():
    """Controlled failure experiments must enable failure injection automatically."""
    cfg = ExperimentConfig(experiment_type="controlled_failure")
    assert cfg.failure_injection_configuration.get("enable_failure_injection") is True

    cfg_held = ExperimentConfig(experiment_type="held_out")
    assert cfg_held.dataset_split == "held_out"
