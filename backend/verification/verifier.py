"""Outcome Verification Framework for Task Results."""
import logging
import re
from typing import Any, List, Optional
from backend.models.schemas import VerificationResult, VerificationRule

logger = logging.getLogger(__name__)

class OutcomeVerifier:
    """Verifies agent task outcomes against deterministic expectations."""

    @staticmethod
    def verify(
        final_answer: Optional[str],
        rule: Optional[VerificationRule],
        context: Optional[dict] = None
    ) -> VerificationResult:
        """Evaluate task completion against rule."""
        if not rule:
            return VerificationResult(
                verified=False,
                status="not_applicable",
                verification_method="none",
                expected_result=None,
                observed_result=final_answer,
                verification_message="No verification rule configured for this task."
            )

        if final_answer is None:
            return VerificationResult(
                verified=False,
                status="failed",
                verification_method=rule.type,
                expected_result=rule.expected_value,
                observed_result=None,
                verification_message="Task produced no final answer to verify."
            )

        if rule.type == "numerical_tolerance":
            return OutcomeVerifier._verify_numerical(final_answer, rule)
        elif rule.type == "field_presence":
            return OutcomeVerifier._verify_fields(final_answer, rule)
        elif rule.type == "evidence_reference":
            return OutcomeVerifier._verify_evidence(final_answer, rule)
        elif rule.type == "exact_match":
            return OutcomeVerifier._verify_exact_match(final_answer, rule)
        else:
            return VerificationResult(
                verified=False,
                status="unverified",
                verification_method=rule.type,
                expected_result=rule.expected_value,
                observed_result=final_answer,
                verification_message=f"Unknown verification rule type: '{rule.type}'"
            )

    @staticmethod
    def _verify_numerical(final_answer: str, rule: VerificationRule) -> VerificationResult:
        if rule.expected_value is None:
            return VerificationResult(
                verified=False,
                status="failed",
                verification_method="numerical_tolerance",
                expected_result=None,
                observed_result=final_answer,
                verification_message="Expected numerical value not supplied in rule."
            )

        try:
            expected_num = float(rule.expected_value)
        except (ValueError, TypeError):
            return VerificationResult(
                verified=False,
                status="failed",
                verification_method="numerical_tolerance",
                expected_result=rule.expected_value,
                observed_result=final_answer,
                verification_message=f"Invalid expected number: {rule.expected_value}"
            )

        tolerance = rule.tolerance if rule.tolerance is not None else 1e-4

        # Extract all numbers from the text (supporting negatives, floats, scientific notation)
        matches = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", final_answer)
        observed_numbers: List[float] = []
        for m in matches:
            try:
                observed_numbers.append(float(m))
            except ValueError:
                continue

        if not observed_numbers:
            return VerificationResult(
                verified=False,
                status="failed",
                verification_method="numerical_tolerance",
                expected_result=expected_num,
                observed_result=final_answer,
                verification_message="No numerical values found in agent answer."
            )

        # Check if any extracted number matches within tolerance
        matched_num: Optional[float] = None
        for num in observed_numbers:
            if abs(num - expected_num) <= tolerance:
                matched_num = num
                break

        if matched_num is not None:
            return VerificationResult(
                verified=True,
                status="verified",
                verification_method="numerical_tolerance",
                expected_result=expected_num,
                observed_result=matched_num,
                verification_message=f"Observed number {matched_num} matches expected {expected_num} (tolerance {tolerance})."
            )
        else:
            return VerificationResult(
                verified=False,
                status="failed",
                verification_method="numerical_tolerance",
                expected_result=expected_num,
                observed_result=observed_numbers,
                verification_message=f"None of observed numbers {observed_numbers} matched expected {expected_num} within tolerance {tolerance}."
            )

    @staticmethod
    def _verify_fields(final_answer: str, rule: VerificationRule) -> VerificationResult:
        required = rule.required_fields or []
        if rule.expected_value and isinstance(rule.expected_value, list):
            required = list(set(required + [str(x) for x in rule.expected_value]))
        elif rule.expected_value and isinstance(rule.expected_value, str):
            required = list(set(required + [rule.expected_value]))

        if not required:
            return VerificationResult(
                verified=False,
                status="failed",
                verification_method="field_presence",
                expected_result=required,
                observed_result=final_answer,
                verification_message="No required fields or values specified."
            )

        missing = [req for req in required if req.lower() not in final_answer.lower()]
        if not missing:
            return VerificationResult(
                verified=True,
                status="verified",
                verification_method="field_presence",
                expected_result=required,
                observed_result=final_answer,
                verification_message=f"All required fields/items present: {required}."
            )
        else:
            return VerificationResult(
                verified=False,
                status="failed",
                verification_method="field_presence",
                expected_result=required,
                observed_result=final_answer,
                verification_message=f"Missing required fields/items: {missing}."
            )

    @staticmethod
    def _verify_evidence(final_answer: str, rule: VerificationRule) -> VerificationResult:
        snippets = rule.required_snippets or []
        if rule.expected_value:
            if isinstance(rule.expected_value, list):
                snippets = list(set(snippets + [str(x) for x in rule.expected_value]))
            elif isinstance(rule.expected_value, str):
                snippets = list(set(snippets + [rule.expected_value]))

        if not snippets:
            return VerificationResult(
                verified=False,
                status="failed",
                verification_method="evidence_reference",
                expected_result=snippets,
                observed_result=final_answer,
                verification_message="No required evidence snippets or references specified."
            )

        missing = [snip for snip in snippets if snip.lower() not in final_answer.lower()]
        if not missing:
            return VerificationResult(
                verified=True,
                status="verified",
                verification_method="evidence_reference",
                expected_result=snippets,
                observed_result=final_answer,
                verification_message=f"All required evidence snippets found: {snippets}."
            )
        else:
            return VerificationResult(
                verified=False,
                status="failed",
                verification_method="evidence_reference",
                expected_result=snippets,
                observed_result=final_answer,
                verification_message=f"Missing required evidence references: {missing}."
            )

    @staticmethod
    def _verify_exact_match(final_answer: str, rule: VerificationRule) -> VerificationResult:
        expected = str(rule.expected_value).strip() if rule.expected_value is not None else ""
        observed = final_answer.strip()
        if expected == observed:
            return VerificationResult(
                verified=True,
                status="verified",
                verification_method="exact_match",
                expected_result=expected,
                observed_result=observed,
                verification_message="Answer matches expected output exactly."
            )
        else:
            return VerificationResult(
                verified=False,
                status="failed",
                verification_method="exact_match",
                expected_result=expected,
                observed_result=observed,
                verification_message=f"Answer does not match expected output. Expected: '{expected}', got: '{observed}'."
            )
