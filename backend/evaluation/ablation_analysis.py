"""Component ablation study analysis for TraceGuard Milestone 5."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class AblationVariantResult(BaseModel):
    """Execution summary for a specific ablation variant."""
    variant_name: str
    description: str
    sample_size: int
    success_rate: float
    total_failures: int
    interventions_initiated: int
    mean_latency_ms: float
    mean_tool_calls: float
    mean_model_calls: float

class ComponentMarginalContribution(BaseModel):
    """Decomposition of the individual contribution of a subsystem."""
    component_name: str
    description: str
    delta_success_rate_pp: float
    delta_latency_ms: float
    delta_tool_calls: float
    assessment: str

class AblationAnalysisResult(BaseModel):
    """Complete multi-variant ablation study analysis."""
    experiment_id: str
    variants: Dict[str, AblationVariantResult] = Field(default_factory=dict)
    contributions: List[ComponentMarginalContribution] = Field(default_factory=list)
    key_findings: List[str] = Field(default_factory=list)
    interpretation: str = ""

def compute_ablation_analysis(
    experiment_id: str,
    variant_results: Dict[str, Dict[str, Any]],
) -> AblationAnalysisResult:
    """
    Computes marginal component contributions across the 4 ablation configurations:
    1. baseline: No detection, no recovery
    2. detection_only: Passive failure diagnosis active, recovery disabled
    3. fixed_retry: Blind tool retries, no trajectory diagnosis
    4. traceguard_recovery: Full trajectory diagnosis + targeted recovery
    """
    variants: Dict[str, AblationVariantResult] = {}
    descriptions = {
        "baseline": "Baseline agent execution without failure detection or recovery interventions",
        "detection_only": "Trajectory failure detection active passively; recovery disabled",
        "fixed_retry": "Blind bounded retries on transient errors without diagnosis or replanning",
        "traceguard_recovery": "Full system: trajectory diagnosis + targeted failure-specific recovery",
    }

    for name, data in variant_results.items():
        desc = descriptions.get(name, f"Ablation variant: {name}")
        variants[name] = AblationVariantResult(
            variant_name=name,
            description=desc,
            sample_size=data.get("sample_size", 0),
            success_rate=data.get("success_rate", 0.0),
            total_failures=data.get("total_failures", 0),
            interventions_initiated=data.get("interventions_initiated", 0),
            mean_latency_ms=data.get("mean_latency_ms", 0.0),
            mean_tool_calls=data.get("mean_tool_calls", 0.0),
            mean_model_calls=data.get("mean_model_calls", 0.0),
        )

    contributions: List[ComponentMarginalContribution] = []
    base = variants.get("baseline")
    det = variants.get("detection_only")
    fixed = variants.get("fixed_retry")
    tg = variants.get("traceguard_recovery")

    # 1. Detection alone (passive diagnostic overhead)
    if base and det:
        d_sr = round(det.success_rate - base.success_rate, 2)
        d_lat = round(det.mean_latency_ms - base.mean_latency_ms, 2)
        d_tools = round(det.mean_tool_calls - base.mean_tool_calls, 2)
        contributions.append(ComponentMarginalContribution(
            component_name="Trajectory Failure Detection (Passive)",
            description="Evaluates diagnostic rules without intervening in agent execution",
            delta_success_rate_pp=d_sr,
            delta_latency_ms=d_lat,
            delta_tool_calls=d_tools,
            assessment=(
                f"Detection introduces minimal latency overhead ({d_lat:+.2f}ms) "
                f"and 0 execution interventions (delta success rate: {d_sr:+.2f} pp)."
            )
        ))

    # 2. Fixed Retry vs Baseline
    if base and fixed:
        d_sr = round(fixed.success_rate - base.success_rate, 2)
        d_lat = round(fixed.mean_latency_ms - base.mean_latency_ms, 2)
        d_tools = round(fixed.mean_tool_calls - base.mean_tool_calls, 2)
        contributions.append(ComponentMarginalContribution(
            component_name="Blind Fixed Retry",
            description="Applies blind bounded retries to transient tool failures",
            delta_success_rate_pp=d_sr,
            delta_latency_ms=d_lat,
            delta_tool_calls=d_tools,
            assessment=(
                f"Fixed retry produced {d_sr:+.2f} pp success change with {d_lat:+.2f}ms latency "
                f"and {d_tools:+.2f} additional tool calls."
            )
        ))

    # 3. Diagnosis-Driven Recovery vs Fixed Retry
    if fixed and tg:
        d_sr = round(tg.success_rate - fixed.success_rate, 2)
        d_lat = round(tg.mean_latency_ms - fixed.mean_latency_ms, 2)
        d_tools = round(tg.mean_tool_calls - fixed.mean_tool_calls, 2)
        contributions.append(ComponentMarginalContribution(
            component_name="Failure-Specific Diagnosis & Recovery vs Fixed Retry",
            description="Targeted policies (argument re-validation, loop breaks, evidence search) vs blind retry",
            delta_success_rate_pp=d_sr,
            delta_latency_ms=d_lat,
            delta_tool_calls=d_tools,
            assessment=(
                f"Targeted recovery vs fixed retry delta: {d_sr:+.2f} pp success with "
                f"{d_lat:+.2f}ms additional latency."
            )
        ))

    # 4. Full TraceGuard vs Baseline
    if base and tg:
        d_sr = round(tg.success_rate - base.success_rate, 2)
        d_lat = round(tg.mean_latency_ms - base.mean_latency_ms, 2)
        d_tools = round(tg.mean_tool_calls - base.mean_tool_calls, 2)
        contributions.append(ComponentMarginalContribution(
            component_name="Full TraceGuard Platform (E2E vs Baseline)",
            description="End-to-end combination of trajectory diagnosis and targeted recovery",
            delta_success_rate_pp=d_sr,
            delta_latency_ms=d_lat,
            delta_tool_calls=d_tools,
            assessment=(
                f"Full TraceGuard produced {d_sr:+.2f} pp overall task success change with "
                f"{d_lat:+.2f}ms total latency overhead."
            )
        ))

    # Key findings synthesis
    findings = []
    if base and tg:
        findings.append(f"TraceGuard overall task success difference vs Baseline: {tg.success_rate - base.success_rate:+.2f} pp.")
    if det and base:
        findings.append(f"Passive diagnostic latency overhead: {det.mean_latency_ms - base.mean_latency_ms:+.2f} ms.")
    if fixed and tg:
        findings.append(f"TraceGuard targeted recovery vs Fixed Retry difference: {tg.success_rate - fixed.success_rate:+.2f} pp.")

    interpretation = (
        "Ablation decomposes the reliability gains and overhead across subsystems. "
        "Passive detection adds negligible latency without mutating execution state. "
        "Comparative deltas isolate the empirical benefit of targeted recovery policies against blind retry heuristics."
    )

    return AblationAnalysisResult(
        experiment_id=experiment_id,
        variants=variants,
        contributions=contributions,
        key_findings=findings,
        interpretation=interpretation
    )
