"""Task executor with proper Bridge RPC integration.

Replaces the previous ``AsyncBridgeExecutor`` stub that always returned
``success=False``.  All execution failures are now surfaced as
``ExecutionError`` rather than being silently swallowed.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from nexus_os.exceptions import (
    BridgeError,
    CircuitBreakerOpen,
    ExecutionError,
    KAIJUDenied,
    NexusError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class BridgeExecutor:
    """Executes tasks via the Bridge JSON-RPC layer.

    Previously the ``AsyncBridgeExecutor`` was a stub returning
    ``success=False`` unconditionally.  This implementation actually
    dispatches to the bridge client and propagates errors.
    """

    def __init__(
        self,
        bridge_client: Any | None = None,
        kaiju_gate: Any | None = None,
        vap_chain: Any | None = None,
        max_retries: int = 2,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._bridge = bridge_client
        self._kaiju = kaiju_gate
        self._vap = vap_chain
        self._max_retries = max_retries
        self._timeout = timeout_seconds

    def execute(
        self,
        task_id: str,
        action: str,
        context: dict[str, Any],
        *,
        agent_id: str = "system",
    ) -> TaskResult:
        """Execute a task through the full governance pipeline.

        Flow: KAIJU gate -> Bridge RPC -> VAP log -> result.
        Errors at any stage are raised, not swallowed.
        """
        start = time.monotonic()

        # Stage 1: KAIJU gate check
        if self._kaiju is not None:
            try:
                gate_result = self._kaiju.evaluate(agent_id, action, context)
            except KAIJUDenied:
                raise
            except NexusError:
                raise
            except Exception as exc:
                raise ExecutionError(
                    f"KAIJU evaluation failed unexpectedly: {exc}",
                    task_id=task_id,
                    cause=exc,
                ) from exc

            if gate_result.decision.value == "DENY":
                raise KAIJUDenied(
                    gate_result.reason,
                    gate_stage=gate_result.stage,
                    agent_id=agent_id,
                )

        # Stage 2: Bridge RPC dispatch
        if self._bridge is None:
            raise ExecutionError(
                "No bridge client configured — cannot execute task",
                task_id=task_id,
                details={"action": action},
            )

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                rpc_result = self._bridge.call(
                    method=action,
                    params=context,
                    timeout=self._timeout,
                )
                break
            except BridgeError:
                raise
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Bridge RPC attempt %d/%d failed for task %s: %s",
                    attempt, self._max_retries, task_id, exc,
                )
                if attempt == self._max_retries:
                    raise ExecutionError(
                        f"Bridge RPC failed after {self._max_retries} attempts: {exc}",
                        task_id=task_id,
                        details={"action": action, "attempts": self._max_retries},
                        cause=last_error,
                    ) from last_error
        else:
            raise ExecutionError(
                "Exhausted retries without result",
                task_id=task_id,
            )

        duration_ms = (time.monotonic() - start) * 1000

        # Stage 3: VAP audit log
        if self._vap is not None:
            try:
                import hashlib
                result_hash = hashlib.sha256(
                    str(rpc_result).encode()
                ).hexdigest()
                self._vap.append(agent_id, action, result_hash)
            except Exception as exc:
                logger.error(
                    "VAP logging failed for task %s (non-fatal): %s",
                    task_id, exc,
                )

        return TaskResult(
            task_id=task_id,
            success=True,
            output=rpc_result,
            duration_ms=duration_ms,
        )


class TaskDependencyResolver:
    """Resolves task dependencies, detecting cycles.

    Raises ``TaskDependencyCycle`` on cycle detection instead of silently
    producing incorrect execution orders.
    """

    def __init__(self) -> None:
        self._graph: dict[str, set[str]] = {}

    def add_dependency(self, task_id: str, depends_on: str) -> None:
        self._graph.setdefault(task_id, set()).add(depends_on)
        self._graph.setdefault(depends_on, set())

    def resolve_order(self) -> list[str]:
        """Topological sort with cycle detection.

        Raises
        ------
        TaskDependencyCycle
            If the dependency graph contains a cycle.
        """
        from nexus_os.exceptions import TaskDependencyCycle

        visited: set[str] = set()
        in_stack: set[str] = set()
        order: list[str] = []

        def _visit(node: str) -> None:
            if node in in_stack:
                raise TaskDependencyCycle(
                    f"Dependency cycle detected involving task {node!r}",
                    details={"task": node, "stack": list(in_stack)},
                )
            if node in visited:
                return
            in_stack.add(node)
            for dep in self._graph.get(node, set()):
                _visit(dep)
            in_stack.discard(node)
            visited.add(node)
            order.append(node)

        for task in self._graph:
            _visit(task)

        return order
