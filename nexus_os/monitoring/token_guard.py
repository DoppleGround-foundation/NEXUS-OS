"""TokenGuard - Budget enforcement and usage monitoring.

Replaces bare ``except: pass`` blocks in budget checking with proper
``BudgetExceeded`` and ``TokenGuardError`` exceptions.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexus_os.exceptions import BudgetExceeded, TokenGuardError

logger = logging.getLogger(__name__)


class Strategy(Enum):
    ECO = "eco"
    BALANCED = "balanced"
    FAST = "fast"
    UNLIMITED = "unlimited"


STRATEGY_MULTIPLIERS: dict[Strategy, float] = {
    Strategy.ECO: 0.5,
    Strategy.BALANCED: 1.0,
    Strategy.FAST: 2.0,
    Strategy.UNLIMITED: float("inf"),
}


@dataclass
class BudgetRecord:
    agent_id: str
    tokens_used: int = 0
    tokens_limit: int = 100_000
    strategy: Strategy = Strategy.BALANCED
    last_check: float = field(default_factory=time.time)
    history: list[dict[str, Any]] = field(default_factory=list)


class TokenGuard:
    """Token budget enforcement with per-agent tracking.

    All budget checks raise ``BudgetExceeded`` when the limit is hit,
    rather than silently allowing overspend.
    """

    def __init__(self, default_limit: int = 100_000) -> None:
        self._default_limit = default_limit
        self._records: dict[str, BudgetRecord] = {}
        self._lock = threading.Lock()

    def register_agent(
        self,
        agent_id: str,
        *,
        limit: int | None = None,
        strategy: Strategy = Strategy.BALANCED,
    ) -> None:
        with self._lock:
            if agent_id in self._records:
                logger.debug("Agent %s already registered with TokenGuard", agent_id)
                return
            self._records[agent_id] = BudgetRecord(
                agent_id=agent_id,
                tokens_limit=limit or self._default_limit,
                strategy=strategy,
            )
        logger.info(
            "TokenGuard registered %s (limit=%d, strategy=%s)",
            agent_id, limit or self._default_limit, strategy.value,
        )

    def check_budget(
        self,
        agent_id: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Check whether the agent has budget remaining.

        Returns ``True`` if budget is available, raises ``BudgetExceeded``
        if not.

        Raises
        ------
        TokenGuardError
            If the agent is not registered.
        BudgetExceeded
            If the agent has exhausted their token budget.
        """
        record = self._get_record(agent_id)
        effective_limit = self._effective_limit(record)

        if record.tokens_used >= effective_limit:
            raise BudgetExceeded(
                f"Agent {agent_id} has exhausted token budget: "
                f"{record.tokens_used}/{effective_limit}",
                used=record.tokens_used,
                limit=effective_limit,
                details={
                    "agent_id": agent_id,
                    "strategy": record.strategy.value,
                },
            )

        record.last_check = time.time()
        return True

    def consume(self, agent_id: str, tokens: int) -> int:
        """Record token usage.

        Raises
        ------
        TokenGuardError
            If the agent is not registered or tokens is negative.
        BudgetExceeded
            If this consumption would exceed the budget.
        """
        if tokens < 0:
            raise TokenGuardError(
                f"Cannot consume negative tokens: {tokens}",
                details={"agent_id": agent_id, "tokens": tokens},
            )

        record = self._get_record(agent_id)
        effective_limit = self._effective_limit(record)

        new_total = record.tokens_used + tokens
        if new_total > effective_limit:
            raise BudgetExceeded(
                f"Consumption of {tokens} tokens would exceed budget for {agent_id}: "
                f"{new_total}/{effective_limit}",
                used=record.tokens_used,
                limit=effective_limit,
                details={
                    "agent_id": agent_id,
                    "requested": tokens,
                    "would_be_total": new_total,
                },
            )

        with self._lock:
            record.tokens_used = new_total
            record.history.append({
                "tokens": tokens,
                "total": new_total,
                "timestamp": time.time(),
            })

        return record.tokens_used

    def get_usage(self, agent_id: str) -> dict[str, Any]:
        record = self._get_record(agent_id)
        effective_limit = self._effective_limit(record)
        return {
            "agent_id": agent_id,
            "tokens_used": record.tokens_used,
            "tokens_limit": effective_limit,
            "remaining": max(0, effective_limit - record.tokens_used),
            "strategy": record.strategy.value,
            "utilization": record.tokens_used / effective_limit if effective_limit else 0,
        }

    def set_strategy(self, agent_id: str, strategy: Strategy) -> None:
        record = self._get_record(agent_id)
        old = record.strategy
        record.strategy = strategy
        logger.info(
            "TokenGuard strategy for %s: %s -> %s",
            agent_id, old.value, strategy.value,
        )

    def _get_record(self, agent_id: str) -> BudgetRecord:
        with self._lock:
            record = self._records.get(agent_id)
        if record is None:
            raise TokenGuardError(
                f"Agent {agent_id!r} is not registered with TokenGuard",
                details={"agent_id": agent_id},
            )
        return record

    def _effective_limit(self, record: BudgetRecord) -> int:
        multiplier = STRATEGY_MULTIPLIERS.get(record.strategy, 1.0)
        if multiplier == float("inf"):
            return 2**63  # practical "unlimited"
        return int(record.tokens_limit * multiplier)
