"""KAIJU gates and Core Value Alignment verification.

Replaces the previous stub where ``CVAVerifier`` always returned
``(True, "passed stub")`` and bare ``except: pass`` blocks silently
swallowed gate failures.

Every gate stage now raises ``KAIJUDenied`` or ``CVAVerificationFailed``
on failure so callers can react, log, and audit the denial.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexus_os.exceptions import (
    CVAVerificationFailed,
    GovernorError,
    KAIJUDenied,
    ProofChainError,
    TrustBelowThreshold,
)

logger = logging.getLogger(__name__)


class GateDecision(Enum):
    APPROVE = "APPROVE"
    DENY = "DENY"
    REQUIRE_REVIEW = "REQUIRE_REVIEW"
    HARD_STOP = "HARD_STOP"


@dataclass(frozen=True)
class GateResult:
    decision: GateDecision
    reason: str
    stage: int
    evidence: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core Value Alignment Verifier
# ---------------------------------------------------------------------------

# Canonical core values that every action is checked against.
CORE_VALUES = [
    "evidence_grounded",
    "proposal_bound",
    "test_gated",
    "auditable",
    "safety_first",
]


def verify_core_value_alignment(
    action: str,
    context: dict[str, Any],
    *,
    required_values: list[str] | None = None,
) -> tuple[bool, str]:
    """Check whether *action* aligns with the project's core values.

    Unlike the previous stub that always returned ``(True, "passed stub")``,
    this implementation checks that the required evidence fields are present
    in *context* for each core value.

    Returns
    -------
    tuple[bool, str]
        ``(passed, reason)`` — if *passed* is ``False``, *reason* describes
        which value was violated.

    Raises
    ------
    CVAVerificationFailed
        When a critical safety value is violated (hard-fail, not soft).
    """
    values_to_check = required_values or CORE_VALUES

    for value in values_to_check:
        checker = _VALUE_CHECKERS.get(value)
        if checker is None:
            logger.warning("No checker registered for core value %r", value)
            continue

        try:
            passed, reason = checker(action, context)
        except Exception as exc:
            raise CVAVerificationFailed(
                f"CVA checker for {value!r} raised an unexpected error: {exc}",
                details={"value": value, "action": action},
                cause=exc,
            ) from exc

        if not passed:
            if value == "safety_first":
                raise CVAVerificationFailed(
                    f"Critical safety value violated: {reason}",
                    details={"value": value, "action": action},
                )
            return False, reason

    return True, "all core values satisfied"


def _check_evidence_grounded(action: str, ctx: dict[str, Any]) -> tuple[bool, str]:
    evidence = ctx.get("evidence")
    if not evidence:
        return False, "action has no supporting evidence"
    return True, "evidence present"


def _check_proposal_bound(action: str, ctx: dict[str, Any]) -> tuple[bool, str]:
    proposal_id = ctx.get("proposal_id")
    if not proposal_id:
        return False, "action is not linked to an approved proposal"
    return True, f"bound to proposal {proposal_id}"


def _check_test_gated(action: str, ctx: dict[str, Any]) -> tuple[bool, str]:
    tests_passed = ctx.get("tests_passed")
    if tests_passed is None:
        return False, "no test results provided"
    if not tests_passed:
        return False, "tests did not pass"
    return True, "tests passed"


def _check_auditable(action: str, ctx: dict[str, Any]) -> tuple[bool, str]:
    audit_trail = ctx.get("audit_trail")
    if not audit_trail:
        return False, "no audit trail attached"
    return True, "audit trail present"


def _check_safety_first(action: str, ctx: dict[str, Any]) -> tuple[bool, str]:
    safety_review = ctx.get("safety_review")
    if safety_review is None:
        return False, "safety review not performed"
    if safety_review.get("passed") is not True:
        return False, f"safety review failed: {safety_review.get('reason', 'unknown')}"
    return True, "safety review passed"


_VALUE_CHECKERS: dict[str, Any] = {
    "evidence_grounded": _check_evidence_grounded,
    "proposal_bound": _check_proposal_bound,
    "test_gated": _check_test_gated,
    "auditable": _check_auditable,
    "safety_first": _check_safety_first,
}


# ---------------------------------------------------------------------------
# KAIJU 5-Stage Authorization Gate
# ---------------------------------------------------------------------------

class KAIJUGate:
    """5-stage authorization barrier for agent actions.

    Stages
    ------
    1. Schema validation + injection check
    2. Trust score evaluation
    3. Core Value Alignment check
    4. Budget / TokenGuard check
    5. Sandbox assignment + capability token issuance

    All stages propagate errors instead of swallowing them.
    """

    def __init__(
        self,
        trust_engine: Any | None = None,
        token_guard: Any | None = None,
    ) -> None:
        self._trust_engine = trust_engine
        self._token_guard = token_guard

    def evaluate(
        self,
        agent_id: str,
        action: str,
        context: dict[str, Any],
    ) -> GateResult:
        """Run all 5 KAIJU stages.  Raises on hard failures."""
        for stage, evaluator in enumerate(self._stages, start=1):
            result = evaluator(agent_id, action, context, stage)
            if result.decision in (GateDecision.DENY, GateDecision.HARD_STOP):
                logger.warning(
                    "KAIJU stage %d DENIED agent=%s action=%s reason=%s",
                    stage, agent_id, action, result.reason,
                )
                if result.decision == GateDecision.HARD_STOP:
                    raise KAIJUDenied(
                        result.reason,
                        gate_stage=stage,
                        agent_id=agent_id,
                        details=result.evidence,
                    )
                return result
            if result.decision == GateDecision.REQUIRE_REVIEW:
                return result

        return GateResult(
            decision=GateDecision.APPROVE,
            reason="all gates passed",
            stage=5,
        )

    # -- Stage implementations ------------------------------------------------

    def _stage_schema_validation(
        self,
        agent_id: str,
        action: str,
        context: dict[str, Any],
        stage: int,
    ) -> GateResult:
        if not action or not isinstance(action, str):
            return GateResult(
                decision=GateDecision.DENY,
                reason="action must be a non-empty string",
                stage=stage,
            )
        if not isinstance(context, dict):
            return GateResult(
                decision=GateDecision.DENY,
                reason="context must be a dict",
                stage=stage,
            )
        # Check for injection patterns
        dangerous_patterns = ["__import__", "eval(", "exec(", "os.system"]
        for pattern in dangerous_patterns:
            if pattern in action:
                return GateResult(
                    decision=GateDecision.HARD_STOP,
                    reason=f"injection pattern detected: {pattern!r}",
                    stage=stage,
                    evidence={"pattern": pattern},
                )
        return GateResult(
            decision=GateDecision.APPROVE, reason="schema valid", stage=stage,
        )

    def _stage_trust_evaluation(
        self,
        agent_id: str,
        action: str,
        context: dict[str, Any],
        stage: int,
    ) -> GateResult:
        if self._trust_engine is None:
            logger.debug("No trust engine configured; skipping trust check")
            return GateResult(
                decision=GateDecision.APPROVE,
                reason="trust engine not configured",
                stage=stage,
            )
        try:
            score = self._trust_engine.get_score(agent_id)
        except Exception as exc:
            logger.error("Trust engine lookup failed for %s: %s", agent_id, exc)
            return GateResult(
                decision=GateDecision.DENY,
                reason=f"trust lookup failed: {exc}",
                stage=stage,
                evidence={"error": str(exc)},
            )
        threshold = context.get("trust_threshold", 25.0)
        if score < threshold:
            return GateResult(
                decision=GateDecision.DENY,
                reason=f"trust {score:.1f} < threshold {threshold:.1f}",
                stage=stage,
                evidence={"score": score, "threshold": threshold},
            )
        return GateResult(
            decision=GateDecision.APPROVE,
            reason=f"trust {score:.1f} >= {threshold:.1f}",
            stage=stage,
        )

    def _stage_cva_check(
        self,
        agent_id: str,
        action: str,
        context: dict[str, Any],
        stage: int,
    ) -> GateResult:
        try:
            passed, reason = verify_core_value_alignment(action, context)
        except CVAVerificationFailed:
            raise
        except Exception as exc:
            logger.error("CVA check raised unexpected error: %s", exc)
            return GateResult(
                decision=GateDecision.DENY,
                reason=f"CVA check error: {exc}",
                stage=stage,
                evidence={"error": str(exc)},
            )
        if not passed:
            return GateResult(
                decision=GateDecision.DENY, reason=reason, stage=stage,
            )
        return GateResult(
            decision=GateDecision.APPROVE, reason=reason, stage=stage,
        )

    def _stage_budget_check(
        self,
        agent_id: str,
        action: str,
        context: dict[str, Any],
        stage: int,
    ) -> GateResult:
        if self._token_guard is None:
            return GateResult(
                decision=GateDecision.APPROVE,
                reason="token guard not configured",
                stage=stage,
            )
        try:
            allowed = self._token_guard.check_budget(agent_id, context)
        except Exception as exc:
            logger.error("TokenGuard check failed for %s: %s", agent_id, exc)
            return GateResult(
                decision=GateDecision.DENY,
                reason=f"budget check error: {exc}",
                stage=stage,
                evidence={"error": str(exc)},
            )
        if not allowed:
            return GateResult(
                decision=GateDecision.DENY,
                reason="token budget exceeded",
                stage=stage,
            )
        return GateResult(
            decision=GateDecision.APPROVE, reason="budget available", stage=stage,
        )

    def _stage_sandbox_assignment(
        self,
        agent_id: str,
        action: str,
        context: dict[str, Any],
        stage: int,
    ) -> GateResult:
        # Sandbox assignment is deferred to the engine layer; gate approves
        # if prior stages passed.
        return GateResult(
            decision=GateDecision.APPROVE,
            reason="sandbox assignment deferred to engine",
            stage=stage,
        )

    @property
    def _stages(self) -> list[Any]:
        return [
            self._stage_schema_validation,
            self._stage_trust_evaluation,
            self._stage_cva_check,
            self._stage_budget_check,
            self._stage_sandbox_assignment,
        ]


# ---------------------------------------------------------------------------
# VAP Proof Chain
# ---------------------------------------------------------------------------

@dataclass
class VAPEntry:
    """Single entry in the Verifiable Action Protocol chain."""
    sequence: int
    timestamp: float
    agent_id: str
    action: str
    result_hash: str
    prev_hash: str
    entry_hash: str


class VAPChain:
    """Immutable SHA-256 audit trail for agent actions.

    Each entry links to the previous via a hash chain.  Breaks in the chain
    raise ``ProofChainError`` instead of being silently ignored.
    """

    def __init__(self) -> None:
        self._entries: list[VAPEntry] = []

    def append(
        self,
        agent_id: str,
        action: str,
        result_hash: str,
    ) -> VAPEntry:
        prev_hash = self._entries[-1].entry_hash if self._entries else "0" * 64
        seq = len(self._entries)
        ts = time.time()

        payload = f"{seq}:{ts}:{agent_id}:{action}:{result_hash}:{prev_hash}"
        entry_hash = hashlib.sha256(payload.encode()).hexdigest()

        entry = VAPEntry(
            sequence=seq,
            timestamp=ts,
            agent_id=agent_id,
            action=action,
            result_hash=result_hash,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        self._entries.append(entry)
        return entry

    def verify_integrity(self) -> None:
        """Walk the chain and raise on any break."""
        for i, entry in enumerate(self._entries):
            expected_prev = self._entries[i - 1].entry_hash if i > 0 else "0" * 64
            if entry.prev_hash != expected_prev:
                raise ProofChainError(
                    f"Chain broken at sequence {entry.sequence}: "
                    f"expected prev_hash {expected_prev!r}, got {entry.prev_hash!r}",
                    details={
                        "sequence": entry.sequence,
                        "expected": expected_prev,
                        "actual": entry.prev_hash,
                    },
                )

            payload = (
                f"{entry.sequence}:{entry.timestamp}:{entry.agent_id}:"
                f"{entry.action}:{entry.result_hash}:{entry.prev_hash}"
            )
            recomputed = hashlib.sha256(payload.encode()).hexdigest()
            if recomputed != entry.entry_hash:
                raise ProofChainError(
                    f"Hash mismatch at sequence {entry.sequence}: "
                    f"recomputed {recomputed!r} != stored {entry.entry_hash!r}",
                    details={
                        "sequence": entry.sequence,
                        "recomputed": recomputed,
                        "stored": entry.entry_hash,
                    },
                )

    @property
    def entries(self) -> list[VAPEntry]:
        return list(self._entries)
