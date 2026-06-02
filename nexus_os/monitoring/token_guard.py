"""TokenGuard - Budget enforcement and usage monitoring.

Tracks token consumption per agent/model and enforces hard/soft limits.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class UsageRecord:
    agent_id: str
    model_id: str
    tokens_used: int = 0
    requests: int = 0
    last_request: float = field(default_factory=time.time)


@dataclass
class BudgetPolicy:
    max_tokens: int
    max_requests: int = 0
    window_seconds: float = 3600.0
    hard_limit: bool = True


class BudgetExceededError(Exception):
    pass


class TokenGuard:
    """Enforces token budgets per agent and model."""

    def __init__(self) -> None:
        self._usage: dict[str, UsageRecord] = {}
        self._policies: dict[str, BudgetPolicy] = {}
        self._global_policy: BudgetPolicy | None = None

    def set_global_policy(self, policy: BudgetPolicy) -> None:
        self._global_policy = policy

    def set_agent_policy(self, agent_id: str, policy: BudgetPolicy) -> None:
        self._policies[agent_id] = policy

    def get_usage(self, agent_id: str, model_id: str = "*") -> UsageRecord | None:
        key = f"{agent_id}:{model_id}"
        return self._usage.get(key)

    def record_usage(self, agent_id: str, model_id: str, tokens: int) -> UsageRecord:
        key = f"{agent_id}:{model_id}"
        if key not in self._usage:
            self._usage[key] = UsageRecord(agent_id=agent_id, model_id=model_id)
        record = self._usage[key]
        record.tokens_used += tokens
        record.requests += 1
        record.last_request = time.time()
        return record

    def check_budget(self, agent_id: str, model_id: str, requested_tokens: int) -> bool:
        """Return True if the request is within budget, False otherwise.

        Raises BudgetExceededError if a hard limit is breached.
        """
        policy = self._policies.get(agent_id, self._global_policy)
        if policy is None:
            return True

        key = f"{agent_id}:{model_id}"
        record = self._usage.get(key)
        current_tokens = record.tokens_used if record else 0
        current_requests = record.requests if record else 0

        if current_tokens + requested_tokens > policy.max_tokens:
            if policy.hard_limit:
                raise BudgetExceededError(
                    f"Agent '{agent_id}' would exceed token budget: "
                    f"{current_tokens + requested_tokens} > {policy.max_tokens}"
                )
            return False

        if policy.max_requests > 0 and current_requests + 1 > policy.max_requests:
            if policy.hard_limit:
                raise BudgetExceededError(
                    f"Agent '{agent_id}' would exceed request limit: "
                    f"{current_requests + 1} > {policy.max_requests}"
                )
            return False

        return True

    def get_total_usage(self, agent_id: str) -> int:
        total = 0
        for key, record in self._usage.items():
            if record.agent_id == agent_id:
                total += record.tokens_used
        return total

    def reset_usage(self, agent_id: str) -> None:
        keys_to_remove = [k for k, v in self._usage.items() if v.agent_id == agent_id]
        for key in keys_to_remove:
            del self._usage[key]
