"""TrustEngine v2.2 - HARDWALL defense scoring for agent behavior.

Implements logistic scaling, adaptive decay, non-compensatory CRITICAL scoring,
and 6-stage CDR (Nominal -> Caution -> Restricted -> High Risk -> Critical -> Collapsed).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum


class CDRStage(Enum):
    """6-stage Credibility Decay Rating lifecycle."""

    NOMINAL = "nominal"
    CAUTION = "caution"
    RESTRICTED = "restricted"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"
    COLLAPSED = "collapsed"


CDR_THRESHOLDS: dict[CDRStage, float] = {
    CDRStage.NOMINAL: 70.0,
    CDRStage.CAUTION: 55.0,
    CDRStage.RESTRICTED: 40.0,
    CDRStage.HIGH_RISK: 25.0,
    CDRStage.CRITICAL: 10.0,
    CDRStage.COLLAPSED: 0.0,
}

BASELINE_SCORE = 25.0
MAX_SCORE = 99.5
MIN_SCORE = 0.0


@dataclass
class TrustRecord:
    agent_id: str
    score: float = BASELINE_SCORE
    stage: CDRStage = CDRStage.HIGH_RISK
    violations: int = 0
    last_update: float = field(default_factory=time.time)
    critical_flags: list[str] = field(default_factory=list)


class TrustEngine:
    """Non-compensatory trust scoring with HARDWALL defense."""

    def __init__(self) -> None:
        self._records: dict[str, TrustRecord] = {}

    def register_agent(self, agent_id: str, initial_score: float | None = None) -> TrustRecord:
        score = initial_score if initial_score is not None else BASELINE_SCORE
        score = max(MIN_SCORE, min(MAX_SCORE, score))
        record = TrustRecord(agent_id=agent_id, score=score)
        record.stage = self._compute_stage(score)
        self._records[agent_id] = record
        return record

    def get_record(self, agent_id: str) -> TrustRecord | None:
        return self._records.get(agent_id)

    def logistic_scale(self, raw_delta: float, current_score: float) -> float:
        """HARDWALL: logistic scaling prevents trust score gaming."""
        midpoint = (MAX_SCORE + MIN_SCORE) / 2
        k = 0.08
        factor = 1.0 / (1.0 + math.exp(-k * (current_score - midpoint)))
        if raw_delta > 0:
            return raw_delta * (1.0 - factor)
        return raw_delta * factor

    def apply_reward(self, agent_id: str, amount: float) -> TrustRecord:
        record = self._require_record(agent_id)
        if record.stage == CDRStage.COLLAPSED:
            return record
        scaled = self.logistic_scale(abs(amount), record.score)
        record.score = min(MAX_SCORE, record.score + scaled)
        record.stage = self._compute_stage(record.score)
        record.last_update = time.time()
        return record

    def apply_penalty(self, agent_id: str, amount: float, critical: str | None = None) -> TrustRecord:
        record = self._require_record(agent_id)
        scaled = self.logistic_scale(-abs(amount), record.score)
        record.score = max(MIN_SCORE, record.score + scaled)
        record.violations += 1
        if critical:
            record.critical_flags.append(critical)
            record.score = max(MIN_SCORE, record.score - 10.0)
        record.stage = self._compute_stage(record.score)
        record.last_update = time.time()
        return record

    def adaptive_decay(self, agent_id: str, elapsed_seconds: float) -> TrustRecord:
        """Apply time-based trust decay."""
        record = self._require_record(agent_id)
        decay_rate = 0.001 * (1.0 + record.violations * 0.1)
        decay = decay_rate * elapsed_seconds
        record.score = max(MIN_SCORE, record.score - decay)
        record.stage = self._compute_stage(record.score)
        record.last_update = time.time()
        return record

    def _compute_stage(self, score: float) -> CDRStage:
        for stage, threshold in CDR_THRESHOLDS.items():
            if score >= threshold:
                return stage
        return CDRStage.COLLAPSED

    def _require_record(self, agent_id: str) -> TrustRecord:
        record = self._records.get(agent_id)
        if record is None:
            raise KeyError(f"Agent '{agent_id}' not registered")
        return record
