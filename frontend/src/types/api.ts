/**
 * Typed API interfaces matching TraceGuard backend schemas.
 */

export type CategoryType =
  | "arithmetic"
  | "data_lookup"
  | "document_qa"
  | "multi_step"
  | "failure_scenario";

export type AgentModeType =
  | "baseline"
  | "fixed_retry"
  | "traceguard"
  | "traceguard_recovery";

export type TerminalStatusType =
  | "successful_completion"
  | "incorrect_answer"
  | "tool_error"
  | "step_limit_exhaustion"
  | "timeout"
  | "unverified_completion"
  | "internal_error";

export type VerificationStatusType =
  | "verified"
  | "failed"
  | "not_applicable"
  | "unverified";

export type FailureCategoryType =
  | "repeated_tool_calls"
  | "invalid_tool_arguments"
  | "tool_execution_failure"
  | "lack_of_progress"
  | "missing_evidence"
  | "incorrect_final_answer"
  | "step_limit_exhaustion"
  | "invalid_model_output"
  | "unverified_completion";

export type SeverityLevelType =
  | "info"
  | "low"
  | "medium"
  | "high"
  | "critical";

export type ConfirmationStatusType =
  | "confirmed"
  | "suspected"
  | "unverified";

export type RecoveryTerminalStatusType =
  | "success_without_recovery"
  | "recovered_successfully"
  | "failed_after_recovery"
  | "unresolved"
  | "abstained"
  | "unverified"
  | "timeout"
  | "budget_exhausted";

export interface HealthResponse {
  status: string;
  version: string;
  service: string;
  model_adapter: string;
  default_max_steps: number;
}

export interface VerificationRule {
  type: "numerical_tolerance" | "field_presence" | "evidence_reference" | "exact_match";
  expected_value?: unknown;
  tolerance?: number;
  required_fields?: string[];
  required_snippets?: string[];
}

export interface VerificationResult {
  verified: boolean;
  status: VerificationStatusType;
  verification_method: string;
  expected_result?: unknown;
  observed_result?: unknown;
  verification_message: string;
}

export interface BenchmarkTask {
  task_id: string;
  benchmark_version: string;
  category: CategoryType;
  task_description: string;
  allowed_tools: string[];
  expected_answer?: unknown;
  verification_rule?: VerificationRule;
  expected_tool_sequence?: string[];
  difficulty: "easy" | "medium" | "hard";
  tags: string[];
  failure_scenario?: {
    scenario_id: string;
    failure_type: string;
    expected_observation: string;
    expected_terminal_status: string;
  };
}

export interface TraceEvent {
  id?: number;
  task_id: string;
  run_id: string;
  step_index: number;
  event_type: string;
  tool_name?: string | null;
  status: string;
  timestamp: string;
  duration_ms?: number | null;
  input_summary?: string | null;
  output_summary?: string | null;
  error_type?: string | null;
  model_tokens?: Record<string, number> | null;
  recovery_attempt_id?: string | null;
  policy_id?: string | null;
  action_type?: string | null;
  finding_ids?: string[] | null;
  remaining_budget?: Record<string, unknown> | null;
}

export interface TaskExecutionResult {
  experiment_id: string;
  task_id: string;
  run_id: string;
  benchmark_version: string;
  agent_mode: string;
  started_at: string;
  completed_at: string;
  terminal_status: TerminalStatusType;
  expected_answer?: unknown;
  observed_answer?: string | null;
  verification_status: VerificationStatusType;
  verification_message: string;
  step_count: number;
  tool_call_count: number;
  tool_error_count: number;
  total_duration_ms: number;
  model_tokens?: Record<string, number> | null;
  estimated_cost?: number | null;
  trace_reference: Record<string, string>;
  failure_scenario_id?: string | null;
}

export interface ConfidenceInterval {
  point_estimate: number;
  lower_bound: number;
  upper_bound: number;
  confidence_level: number;
  method: string;
  sample_size: number;
  warning?: string | null;
}

export interface EfficiencyMetrics {
  mean_duration_ms: number;
  median_duration_ms: number;
  p95_duration_ms?: number | null;
  p95_sample_note?: string | null;
  mean_tool_calls_per_task: number;
  mean_steps_per_task: number;
  total_tokens?: number | null;
  mean_tokens_per_task?: number | null;
  cost_per_task?: number | null;
  cost_per_successful_task?: number | null;
}

export interface FailureDistribution {
  incorrect_answers: number;
  tool_errors: number;
  timeouts: number;
  step_limit_exhaustion: number;
  missing_evidence: number;
  other_errors: number;
  total_failures: number;
  failure_percentages: Record<string, float_alias>;
}
type float_alias = number;

export interface EvaluationMetrics {
  experiment_id: string;
  benchmark_version: string;
  agent_mode: string;
  total_attempted: number;
  successful_tasks: number;
  unverified_tasks: number;
  failed_tasks: number;
  success_rate: number;
  success_rate_ci?: ConfidenceInterval | null;
  verification_accuracy: number;
  verification_denominator: number;
  tool_error_rate: number;
  total_tool_calls: number;
  failed_tool_calls: number;
  failure_distribution: FailureDistribution;
  efficiency: EfficiencyMetrics;
}

export interface ExperimentSummary {
  experiment_id: string;
  benchmark_version: string;
  agent_mode: string;
  status: "running" | "completed" | "failed";
  total_tasks: number;
  completed_tasks: number;
  created_at: string;
  completed_at?: string | null;
  config: Record<string, unknown>;
  metrics?: EvaluationMetrics | null;
}

export interface OverviewStats {
  total_experiments: number;
  total_runs_evaluated: number;
  verified_task_success_rate: number;
  recovery_success_rate: number;
  total_recovery_interventions: number;
  median_latency_ms: number;
  mean_latency_ms: number;
  average_tool_calls_per_task: number;
  total_measured_cost: number;
  mode_breakdown: Array<{
    mode: string;
    total_runs: number;
    verified_runs: number;
    success_rate: number;
    mean_latency_ms: number;
    avg_tool_calls: number;
  }>;
  failure_distribution: Array<{
    category: string;
    count: number;
  }>;
}

export interface TrajectoryFeatures {
  total_steps: number;
  total_tool_calls: number;
  unique_tools_used: number;
  tool_call_repetition_ratio: number;
  distinct_argument_patterns: number;
  max_consecutive_identical_tool_calls: number;
  tool_execution_failures: number;
  persistent_tool_failures: number;
  validation_failures: number;
  empty_tool_results: number;
  successful_tool_results: number;
  final_answer_attempts: number;
  step_limit_reached: boolean;
  final_answer_produced: boolean;
  terminal_status?: string | null;
  verification_status?: string | null;
  evidence_retrieval_occurred: boolean;
  evidence_policy_satisfied?: boolean | null;
  mean_step_duration_ms: number;
  total_duration_ms: number;
  observable_progress_stalled: boolean;
  tool_names_sequence: string[];
}

export interface DiagnosticFinding {
  finding_id: string;
  rule_id: string;
  failure_category: FailureCategoryType;
  severity: SeverityLevelType;
  confirmation_status: ConfirmationStatusType;
  confidence?: number | null;
  evidence_event_ids: string[];
  explanation: string;
  recommended_next_action: string;
}

export interface DiagnosticReport {
  diagnostic_id: string;
  experiment_id?: string | null;
  task_id: string;
  run_id: string;
  detector_version: string;
  diagnostic_status: "healthy" | "warning" | "failure_detected" | "insufficient_data";
  features: TrajectoryFeatures;
  findings: DiagnosticFinding[];
  primary_failure_category?: FailureCategoryType | null;
  severity: SeverityLevelType;
  evidence_event_ids: string[];
  explanation: string;
  confirmation_status: ConfirmationStatusType;
  analysis_duration_ms: number;
  created_at: string;
}

export interface DetectorMetrics {
  detector_version: string;
  precision: number;
  recall: number;
  f1_score: number;
  false_positive_rate: number;
  coverage_rate: number;
  mean_detection_latency_ms: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  true_negatives: number;
  total_evaluated: number;
  category_metrics?: Record<string, {
    precision: number;
    recall: number;
    f1: number;
    support: number;
  }>;
}

export interface RecoveryActionRecord {
  action_id: string;
  attempt_index: number;
  policy_id: string;
  action_type: string;
  status: string;
  duration_ms: number;
  description: string;
  input_context?: Record<string, unknown> | null;
  output_result?: Record<string, unknown> | null;
  error?: string | null;
  timestamp: string;
}

export interface RecoveryAttemptReport {
  attempt_id: string;
  attempt_index: number;
  policy_id: string;
  action_type: string;
  status: string;
  duration_ms: number;
  actions: RecoveryActionRecord[];
  intermediate_answer?: string | null;
  verification_result?: VerificationResult | null;
  error_message?: string | null;
}

export interface RecoveryBudgetUsage {
  attempts: number;
  steps: number;
  tool_calls: number;
  model_calls: number;
  duration_ms: number;
  estimated_cost?: number | null;
  exhausted_limit?: string | null;
}

export interface RecoveryReport {
  recovery_id: string;
  task_id: string;
  run_id: string;
  recovery_attempt_id: string;
  experiment_id?: string | null;
  recovery_attempted: boolean;
  policy_id: string;
  policy_version: string;
  initial_failure_category?: string | null;
  diagnostic_finding_ids: string[];
  preconditions: string[];
  selection_reason: string;
  terminal_status: RecoveryTerminalStatusType;
  original_status: string;
  original_verification_status?: string | null;
  final_verification_status?: string | null;
  final_answer?: string | null;
  attempts: RecoveryAttemptReport[];
  total_recovery_duration_ms: number;
  total_execution_duration_ms: number;
  additional_tool_calls: number;
  additional_model_calls: number;
  budget_usage: RecoveryBudgetUsage;
  created_at: string;
}

export interface StatisticalComparison {
  comparison_id: string;
  baseline_mode: string;
  treatment_mode: string;
  sample_size: number;
  paired_pairs: number;
  baseline_successes: number;
  treatment_successes: number;
  baseline_success_rate: number;
  treatment_success_rate: number;
  absolute_gain: number;
  relative_gain: number;
  b_treatment_only: number;
  c_baseline_only: number;
  concordant_pairs: number;
  test_type_used: string;
  statistic: number;
  p_value: number;
  is_significant: boolean;
  significance_threshold: number;
  confidence_interval_95?: [number, number];
  warning?: string | null;
  sample_size_valid: boolean;
}

export interface AblationConfiguration {
  config_id: string;
  name: string;
  description: string;
  has_detector: boolean;
  has_policy_selection: boolean;
  has_targeted_recovery: boolean;
  verified_success_rate: number;
  sample_size: number;
  recovery_success_rate?: number | null;
  median_duration_ms: number;
  mean_tool_calls: number;
}

export interface AblationAnalysis {
  experiment_id: string;
  configurations: AblationConfiguration[];
  detector_contribution: number;
  policy_selection_contribution: number;
  targeted_recovery_contribution: number;
  interpretation?: string;
}

export interface FailureAnalysis {
  experiment_id: string;
  total_runs: number;
  categories: Record<string, {
    category: string;
    total: number;
    verified: number;
    failed: number;
    recovery_attempted: number;
    recovered: number;
    recovery_rate: number;
  }>;
}

export interface DetectorConfig {
  detector_version: string;
  max_repetition_threshold: number;
  repetition_ratio_threshold: number;
  stagnation_step_threshold: number;
  max_allowed_tool_failures: number;
  evidence_required_categories: string[];
}
