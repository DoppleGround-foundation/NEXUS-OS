"""TrustEngine v2.2 - HARDWALL defense with proper error propagation.

Implements logistic scaling, adaptive decay, non-compensatory CRITICAL
evaluation, and the 6-stage CDR lifecycle.  All trust mutations are
logged and errors are propagated — never silently swallowed.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexus_os.exceptions import GovernorError, TrustBelowThreshold

logger = logging.getLogger(__name__)

BASELINE_SCORE = 25.0
MAX_SCORE = 99.5
MIN_SCORE = 0.0


class CDRStage(Enum):
    """6-stage Confidence/Decay/Recovery lifecycle."""
    NOMINAL = "nominal"
    CAUTION = "caution"
    RESTRICTED = "restricted"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"
    COLLAPSED = "collapsed"


CDR_THRESHOLDS: dict[CDRStage, float] = {
    CDRStage.NOMINAL: 70.0,
    CDRStage.CAUTION: 50.0,
    CDRStage.RESTRICTED: 35.0,
    CDRStage.HIGH_RISK: 20.0,
    CDRStage.CRITICAL: 10.0,
    CDRStage.COLLAPSED: 0.0,
}


@dataclass
class TrustRecord:
    agent_id: str
    score: float = BASELINE_SCORE
    cdr_stage: CDRStage = CDRStage.RESTRICTED
    last_updated: float = field(default_factory=time.time)
    history: list[dict[str, Any]] = field(default_factory=list)


class TrustEngine:
    """HARDWALL-defended trust scoring engine.

    Key properties
    --------------
    * **Logistic scaling** — reward diminishes near the cap (99.5), preventing
      trust score gaming.
    * **Adaptive decay** — trust decays faster when the agent is already in a
      risky CDR stage.
    * **Non-compensatory CRITICAL** — a single critical violation forces the
      CDR to CRITICAL regardless of the overall score.

    All mutations are recorded in the agent's history for auditability.
    Errors during scoring are propagated, not swallowed.
    """

    def __init__(self) -> None:
        self._records: dict[str, TrustRecord] = {}

    def register_agent(self, agent_id: str, initial_score: float | None = None) -> None:
        if agent_id in self._records:
            logger.debug("Agent %s already registered", agent_id)
            return
        score = initial_score if initial_score is not None else BASELINE_SCORE
        self._records[agent_id] = TrustRecord(agent_id=agent_id, score=score)
        self._update_cdr(agent_id)
        logger.info("Registered agent %s with score %.1f", agent_id, score)

    def get_score(self, agent_id: str) -> float:
        record = self._get_record(agent_id)
        return record.score

    def get_cdr_stage(self, agent_id: str) -> CDRStage:
        record = self._get_record(agent_id)
        return record.cdr_stage

    def reward(self, agent_id: str, amount: float, *, reason: str = "") -> float:
        """Apply a positive trust adjustment with HARDWALL logistic scaling.

        The effective reward is attenuated as the score approaches ``MAX_SCORE``
        to prevent gaming.
        """
        record = self._get_record(agent_id)
        if amount <= 0:
            raise GovernorError(
                f"Reward amount must be positive, got {amount}",
                details={"agent_id": agent_id, "amount": amount},
            )

        effective = self._logistic_scale(record.score, amount)
        new_score = min(record.score + effective, MAX_SCORE)
        self._apply_mutation(record, new_score, "reward", reason, amount, effective)
        return record.score

    def penalize(self, agent_id: str, amount: float, *, reason: str = "") -> float:
        """Apply a negative trust adjustment."""
        record = self._get_record(agent_id)
        if amount <= 0:
            raise GovernorError(
                f"Penalty amount must be positive, got {amount}",
                details={"agent_id": agent_id, "amount": amount},
            )

        new_score = max(record.score - amount, MIN_SCORE)
        self._apply_mutation(record, new_score, "penalty", reason, amount, amount)
        return record.score

    def critical_violation(self, agent_id: str, *, reason: str) -> float:
        """Non-compensatory CRITICAL: force CDR to CRITICAL regardless of score.

        This cannot be silently ignored — it always moves the agent to CRITICAL
        and logs the violation.
        """
        record = self._get_record(agent_id)
        old_stage = record.cdr_stage
        new_score = min(record.score, CDR_THRESHOLDS[CDRStage.CRITICAL])
        record.score = new_score
        record.cdr_stage = CDRStage.CRITICAL
        record.last_updated = time.time()
        record.history.append({
            "type": "critical_violation",
            "reason": reason,
            "old_score": record.score,
            "new_score": new_score,
            "old_stage": old_stage.value,
            "new_stage": CDRStage.CRITICAL.value,
            "timestamp": record.last_updated,
        })
        logger.warning(
            "CRITICAL violation for %s: %s (score=%.1f, CDR=%s->%s)",
            agent_id, reason, new_score, old_stage.value, CDRStage.CRITICAL.value,
        )
        return record.score

    def apply_decay(self, agent_id: str) -> float:
        """Apply adaptive time-based decay.

        Decay rate increases with CDR severity — agents in HIGH_RISK or
        CRITICAL decay faster, preventing prolonged operation in risky states.
        """
        record = self._get_record(agent_id)
        decay_rate = self._adaptive_decay_rate(record.cdr_stage)
        elapsed = time.time() - record.last_updated
        decay = decay_rate * (elapsed / 3600.0)  # per-hour decay
        if decay > 0:
            new_score = max(record.score - decay, MIN_SCORE)
            self._apply_mutation(record, new_score, "decay", "time-based", decay, decay)
        return record.score

    def require_threshold(self, agent_id: str, threshold: float) -> None:
        """Raise ``TrustBelowThreshold`` if the agent's score is too low."""
        score = self.get_score(agent_id)
        if score < threshold:
            raise TrustBelowThreshold(
                f"Agent {agent_id} trust {score:.1f} < required {threshold:.1f}",
                current_score=score,
                threshold=threshold,
                agent_id=agent_id,
            )

    # -- internals ------------------------------------------------------------

    def _get_record(self, agent_id: str) -> TrustRecord:
        record = self._records.get(agent_id)
        if record is None:
            raise GovernorError(
                f"Agent {agent_id!r} is not registered with TrustEngine",
                details={"agent_id": agent_id},
            )
        return record

    def _logistic_scale(self, current: float, raw_reward: float) -> float:
        """HARDWALL logistic scaling: reward diminishes near the cap."""
        headroom = MAX_SCORE - current
        if headroom <= 0:
            return 0.0
        ratio = headroom / MAX_SCORE
        # Logistic curve: steep near bottom, flat near top
        scale = 1.0 / (1.0 + math.exp(-10 * (ratio - 0.5)))
        return raw_reward * scale

    def _adaptive_decay_rate(self, stage: CDRStage) -> float:
        """Higher CDR severity = faster decay."""
        rates = {
            CDRStage.NOMINAL: 0.1,
            CDRStage.CAUTION: 0.3,
            CDRStage.RESTRICTED: 0.5,
            CDRStage.HIGH_RISK: 1.0,
            CDRStage.CRITICAL: 2.0,
            CDRStage.COLLAPSED: 5.0,
        }
        return rates.get(stage, 0.5)

    def _update_cdr(self, agent_id: str) -> None:
        record = self._records[agent_id]
        for stage in CDRStage:
            if record.score >= CDR_THRESHOLDS[stage]:
                record.cdr_stage = stage
                return
        record.cdr_stage = CDRStage.COLLAPSED

    def _apply_mutation(
        self,
        record: TrustRecord,
        new_score: float,
        mutation_type: str,
        reason: str,
        raw_amount: float,
        effective_amount: float,
    ) -> None:
        old_score = record.score
        old_stage = record.cdr_stage
        record.score = new_score
        record.last_updated = time.time()
        self._update_cdr(record.agent_id)
        record.history.append({
            "type": mutation_type,
            "reason": reason,
            "raw_amount": raw_amount,
            "effective_amount": effective_amount,
            "old_score": old_score,
            "new_score": new_score,
            "old_stage": old_stage.value,
            "new_stage": record.cdr_stage.value,
            "timestamp": record.last_updated,
        })
        if old_stage != record.cdr_stage:
            logger.info(
                "CDR transition for %s: %s -> %s (score %.1f -> %.1f)",
                record.agent_id,
                old_stage.value,
                record.cdr_stage.value,
                old_score,
                new_score,
            )
