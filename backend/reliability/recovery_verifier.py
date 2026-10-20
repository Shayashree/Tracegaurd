"""Independent post-recovery outcome verifier and terminal status mapping."""
import logging
from typing import Optional
from backend.models.schemas import VerificationResult, VerificationRule
from backend.reliability.recovery_budget import RecoveryBudgetTracker
from backend.reliability.recovery_report import RecoveryTerminalStatus
from backend.verification.verifier import OutcomeVerifier

logger = logging.getLogger(__name__)

class RecoveryVerifier:
    """Independently verifies post-recovery outcomes and determines terminal task status."""

    @staticmethod
    def verify_recovery_result(
        final_answer: Optional[str],
        rule: Optional[VerificationRule],
    ) -> VerificationResult:
        """Run independent verification on the post-recovery proposed final answer."""
        return OutcomeVerifier.verify(final_answer=final_answer or "", rule=rule)

    @classmethod
    def determine_terminal_status(
        cls,
        original_status: str,
        original_verification: Optional[VerificationResult],
        recovery_attempted: bool,
        final_verification: Optional[VerificationResult],
        budget_tracker: RecoveryBudgetTracker,
        error_info: Optional[str] = None,
        final_answer: Optional[str] = None,
    ) -> RecoveryTerminalStatus:
        """Map execution history, recovery attempts, verification results, and budgets to terminal status."""
        # 1. Unassisted success
        if not recovery_attempted:
            if original_status == "completed" and original_verification and original_verification.verified:
                return RecoveryTerminalStatus.SUCCESS_WITHOUT_RECOVERY
            if original_status == "timed_out":
                return RecoveryTerminalStatus.TIMEOUT
            if original_verification and original_verification.status == "unverified":
                return RecoveryTerminalStatus.UNVERIFIED
            return RecoveryTerminalStatus.UNRESOLVED

        # 2. Recovery was attempted
        # Check if budget was exhausted during recovery
        if budget_tracker.is_exhausted:
            return RecoveryTerminalStatus.BUDGET_EXHAUSTED

        if error_info and "timeout" in error_info.lower():
            return RecoveryTerminalStatus.TIMEOUT

        # Check for explicit abstention
        if final_answer and ("unable to answer" in final_answer.lower() or "abstained" in final_answer.lower()):
            return RecoveryTerminalStatus.ABSTAINED

        # Independent verification check:
        # A task counts as recovered ONLY if its final applicable verification rule passes!
        if final_verification:
            if final_verification.verified:
                return RecoveryTerminalStatus.RECOVERED_SUCCESSFULLY
            elif final_verification.status == "failed":
                return RecoveryTerminalStatus.FAILED_AFTER_RECOVERY
            elif final_verification.status in ("unverified", "not_applicable"):
                return RecoveryTerminalStatus.UNVERIFIED

        if final_answer:
            return RecoveryTerminalStatus.UNVERIFIED

        return RecoveryTerminalStatus.UNRESOLVED
