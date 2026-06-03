"""Hermes router and task classifier.

Replaces the previous ``TaskClassifier`` stub that was a
"minimal stub for test collection" using a keyword-based heuristic
fallback.  This implementation uses a structured classification pipeline
with explicit fallback handling and error propagation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexus_os.exceptions import CircuitBreakerOpen, EngineError, TaskRoutingError

logger = logging.getLogger(__name__)


class TaskDomain(Enum):
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    DOCUMENTATION = "documentation"
    DEBUG = "debug"
    RESEARCH = "research"
    SECURITY_AUDIT = "security_audit"
    DATA_ANALYSIS = "data_analysis"
    TESTING = "testing"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassificationResult:
    domain: TaskDomain
    confidence: float
    method: str
    fallback_used: bool = False


@dataclass(frozen=True)
class RouteDecision:
    model: str
    domain: TaskDomain
    reason: str
    fallback_chain: list[str] = field(default_factory=list)


# Domain detection patterns — ordered by specificity.
_DOMAIN_PATTERNS: list[tuple[TaskDomain, re.Pattern[str]]] = [
    (TaskDomain.SECURITY_AUDIT, re.compile(
        r"\b(security|vuln|cve|exploit|injection|sanitiz|pentest|audit)\b", re.I,
    )),
    (TaskDomain.CODE_REVIEW, re.compile(
        r"\b(review|pr\s+diff|pull\s+request|code\s+quality|refactor)\b", re.I,
    )),
    (TaskDomain.DEBUG, re.compile(
        r"\b(debug|traceback|stack\s*trace|exception|error|fix|bug)\b", re.I,
    )),
    (TaskDomain.TESTING, re.compile(
        r"\b(test|pytest|unittest|spec|coverage|assert)\b", re.I,
    )),
    (TaskDomain.CODE_GENERATION, re.compile(
        r"\b(implement|create|build|write\s+code|add\s+feature|generate)\b", re.I,
    )),
    (TaskDomain.DATA_ANALYSIS, re.compile(
        r"\b(analy[sz]|data|metric|statistics|chart|graph|dataset)\b", re.I,
    )),
    (TaskDomain.RESEARCH, re.compile(
        r"\b(research|investigate|explore|survey|compare|benchmark)\b", re.I,
    )),
    (TaskDomain.DOCUMENTATION, re.compile(
        r"\b(document|readme|docstring|comment|explain|describe)\b", re.I,
    )),
]


class TaskClassifier:
    """Classifies tasks into domains for routing.

    Uses a multi-stage pipeline:
    1. Explicit domain hint in context (highest confidence)
    2. Pattern-based detection on the task description
    3. Fallback to UNKNOWN with low confidence (never silently guesses)
    """

    def classify(
        self,
        task_description: str,
        context: dict[str, Any] | None = None,
    ) -> ClassificationResult:
        if not task_description:
            raise TaskRoutingError(
                "Cannot classify empty task description",
                details={"description": task_description},
            )

        ctx = context or {}

        # Stage 1: explicit hint
        hint = ctx.get("domain")
        if hint:
            try:
                domain = TaskDomain(hint)
                return ClassificationResult(
                    domain=domain, confidence=1.0, method="explicit_hint",
                )
            except ValueError:
                logger.warning("Unknown domain hint %r, falling through", hint)

        # Stage 2: pattern matching
        best_domain: TaskDomain | None = None
        best_score = 0
        for domain, pattern in _DOMAIN_PATTERNS:
            matches = pattern.findall(task_description)
            if len(matches) > best_score:
                best_score = len(matches)
                best_domain = domain

        if best_domain is not None and best_score > 0:
            confidence = min(0.5 + (best_score * 0.15), 0.95)
            return ClassificationResult(
                domain=best_domain,
                confidence=confidence,
                method="pattern_match",
            )

        # Stage 3: fallback (explicit, not silent)
        logger.info(
            "Could not confidently classify task; returning UNKNOWN: %.60s...",
            task_description,
        )
        return ClassificationResult(
            domain=TaskDomain.UNKNOWN,
            confidence=0.1,
            method="fallback",
            fallback_used=True,
        )


class HermesRouter:
    """Domain-aware LLM selection and routing with circuit breakers.

    Routes tasks to the most appropriate model based on domain classification.
    Tracks model health via circuit breakers and falls back through the
    configured chain on failure.
    """

    def __init__(
        self,
        model_map: dict[str, str] | None = None,
        fallback_chains: dict[str, list[str]] | None = None,
    ) -> None:
        self._classifier = TaskClassifier()
        self._model_map = model_map or {
            TaskDomain.CODE_GENERATION.value: "qwen3-coder-8b",
            TaskDomain.CODE_REVIEW.value: "deepseek-v4-flash",
            TaskDomain.DOCUMENTATION.value: "minimax-m2.7",
            TaskDomain.DEBUG.value: "kimi-k2.6",
            TaskDomain.RESEARCH.value: "deepseek-v4-flash",
            TaskDomain.SECURITY_AUDIT.value: "deepseek-v4-flash",
            TaskDomain.DATA_ANALYSIS.value: "qwen3-coder-8b",
            TaskDomain.TESTING.value: "qwen3-coder-8b",
            TaskDomain.UNKNOWN.value: "deepseek-v4-flash",
        }
        self._fallback_chains = fallback_chains or {}
        self._circuit_breakers: dict[str, _CircuitBreaker] = {}

    def route(
        self,
        task_description: str,
        context: dict[str, Any] | None = None,
    ) -> RouteDecision:
        """Route a task to a model.

        Raises
        ------
        TaskRoutingError
            When no model (including fallbacks) can handle the task.
        CircuitBreakerOpen
            When all candidate models have tripped circuit breakers.
        """
        classification = self._classifier.classify(task_description, context)
        model = self._model_map.get(classification.domain.value)
        if model is None:
            raise TaskRoutingError(
                f"No model mapped for domain {classification.domain.value!r}",
                details={"domain": classification.domain.value},
            )

        # Check circuit breaker
        if self._is_circuit_open(model):
            fallbacks = self._fallback_chains.get(model, [])
            for fb in fallbacks:
                if not self._is_circuit_open(fb):
                    logger.info(
                        "Primary model %s circuit open; falling back to %s",
                        model, fb,
                    )
                    return RouteDecision(
                        model=fb,
                        domain=classification.domain,
                        reason=f"fallback from {model} (circuit open)",
                        fallback_chain=[model] + fallbacks,
                    )
            raise CircuitBreakerOpen(
                f"All models for {classification.domain.value} have open circuits: "
                f"{[model] + fallbacks}",
                details={
                    "domain": classification.domain.value,
                    "primary": model,
                    "fallbacks": fallbacks,
                },
            )

        return RouteDecision(
            model=model,
            domain=classification.domain,
            reason=f"routed via {classification.method} "
                   f"(confidence={classification.confidence:.2f})",
        )

    def record_failure(self, model: str) -> None:
        cb = self._circuit_breakers.setdefault(model, _CircuitBreaker())
        cb.record_failure()
        if cb.is_open:
            logger.warning("Circuit breaker OPEN for model %s", model)

    def record_success(self, model: str) -> None:
        cb = self._circuit_breakers.get(model)
        if cb is not None:
            cb.record_success()

    def _is_circuit_open(self, model: str) -> bool:
        cb = self._circuit_breakers.get(model)
        return cb is not None and cb.is_open


class _CircuitBreaker:
    """Simple circuit breaker: opens after N consecutive failures."""

    def __init__(self, threshold: int = 3, reset_after: float = 60.0) -> None:
        self._threshold = threshold
        self._reset_after = reset_after
        self._consecutive_failures = 0
        self._last_failure_time = 0.0

    @property
    def is_open(self) -> bool:
        if self._consecutive_failures < self._threshold:
            return False
        import time
        if time.time() - self._last_failure_time > self._reset_after:
            self._consecutive_failures = 0
            return False
        return True

    def record_failure(self) -> None:
        import time
        self._consecutive_failures += 1
        self._last_failure_time = time.time()

    def record_success(self) -> None:
        self._consecutive_failures = 0
