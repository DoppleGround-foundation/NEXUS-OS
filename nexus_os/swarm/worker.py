"""Swarm worker with proper task execution and error handling.

Replaces the previous stub at ``worker.py:180`` that produced fake
simulated outputs with no real task execution.  All failures are now
propagated as ``SwarmError`` variants.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from nexus_os.exceptions import (
    NexusError,
    SwarmError,
    TaskExecutionFailed,
    WorkerAllocationFailed,
)

logger = logging.getLogger(__name__)


class WorkerStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"
    FAILED = "failed"


@dataclass
class TaskAssignment:
    task_id: str
    action: str
    context: dict[str, Any]
    agent_id: str
    assigned_at: float = field(default_factory=time.time)


@dataclass
class WorkerState:
    worker_id: str
    status: WorkerStatus = WorkerStatus.IDLE
    current_task: TaskAssignment | None = None
    completed_count: int = 0
    failed_count: int = 0
    last_heartbeat: float = field(default_factory=time.time)


class Worker:
    """Swarm worker that executes real tasks via a pluggable executor.

    The previous implementation at ``worker.py:180`` produced fake
    simulated outputs.  This version dispatches to a real executor
    and propagates all errors.
    """

    def __init__(
        self,
        worker_id: str,
        executor: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> None:
        self._state = WorkerState(worker_id=worker_id)
        self._executor = executor

    @property
    def worker_id(self) -> str:
        return self._state.worker_id

    @property
    def status(self) -> WorkerStatus:
        return self._state.status

    def execute_task(self, assignment: TaskAssignment) -> Any:
        """Execute a task assignment.

        Raises
        ------
        WorkerAllocationFailed
            If the worker is not IDLE.
        TaskExecutionFailed
            If the executor raises or is not configured.
        SwarmError
            On unexpected internal errors.
        """
        if self._state.status != WorkerStatus.IDLE:
            raise WorkerAllocationFailed(
                f"Worker {self.worker_id} is {self._state.status.value}, cannot accept task",
                details={
                    "worker_id": self.worker_id,
                    "status": self._state.status.value,
                    "task_id": assignment.task_id,
                },
            )

        if self._executor is None:
            raise TaskExecutionFailed(
                f"Worker {self.worker_id} has no executor configured",
                details={"worker_id": self.worker_id, "task_id": assignment.task_id},
            )

        self._state.status = WorkerStatus.BUSY
        self._state.current_task = assignment
        start = time.monotonic()

        try:
            result = self._executor(assignment.action, assignment.context)
        except NexusError:
            self._record_failure(assignment)
            raise
        except Exception as exc:
            self._record_failure(assignment)
            raise TaskExecutionFailed(
                f"Task {assignment.task_id} failed on worker {self.worker_id}: {exc}",
                details={
                    "worker_id": self.worker_id,
                    "task_id": assignment.task_id,
                    "action": assignment.action,
                    "duration_ms": (time.monotonic() - start) * 1000,
                },
                cause=exc,
            ) from exc

        duration_ms = (time.monotonic() - start) * 1000
        self._state.status = WorkerStatus.IDLE
        self._state.current_task = None
        self._state.completed_count += 1
        self._state.last_heartbeat = time.time()

        logger.debug(
            "Worker %s completed task %s in %.1fms",
            self.worker_id, assignment.task_id, duration_ms,
        )
        return result

    def heartbeat(self) -> dict[str, Any]:
        self._state.last_heartbeat = time.time()
        return {
            "worker_id": self.worker_id,
            "status": self._state.status.value,
            "completed": self._state.completed_count,
            "failed": self._state.failed_count,
            "current_task": (
                self._state.current_task.task_id
                if self._state.current_task else None
            ),
            "last_heartbeat": self._state.last_heartbeat,
        }

    def drain(self) -> None:
        """Mark worker as draining — will not accept new tasks."""
        self._state.status = WorkerStatus.DRAINING
        logger.info("Worker %s is draining", self.worker_id)

    def _record_failure(self, assignment: TaskAssignment) -> None:
        self._state.status = WorkerStatus.IDLE
        self._state.current_task = None
        self._state.failed_count += 1
        logger.warning(
            "Worker %s failed task %s (total failures: %d)",
            self.worker_id, assignment.task_id, self._state.failed_count,
        )


class WorkerPool:
    """Manages a pool of workers with proper allocation error handling."""

    def __init__(self) -> None:
        self._workers: dict[str, Worker] = {}

    def add_worker(self, worker: Worker) -> None:
        if worker.worker_id in self._workers:
            raise SwarmError(
                f"Worker {worker.worker_id!r} already in pool",
                details={"worker_id": worker.worker_id},
            )
        self._workers[worker.worker_id] = worker

    def allocate(self, task: TaskAssignment) -> Worker:
        """Find an idle worker for the task.

        Raises
        ------
        WorkerAllocationFailed
            If no idle workers are available.
        """
        for worker in self._workers.values():
            if worker.status == WorkerStatus.IDLE:
                return worker

        raise WorkerAllocationFailed(
            f"No idle workers available for task {task.task_id}",
            details={
                "task_id": task.task_id,
                "pool_size": len(self._workers),
                "statuses": {
                    wid: w.status.value for wid, w in self._workers.items()
                },
            },
        )

    def remove_worker(self, worker_id: str) -> None:
        worker = self._workers.pop(worker_id, None)
        if worker is None:
            raise SwarmError(
                f"Worker {worker_id!r} not found in pool",
                details={"worker_id": worker_id},
            )

    @property
    def idle_count(self) -> int:
        return sum(1 for w in self._workers.values() if w.status == WorkerStatus.IDLE)

    @property
    def total_count(self) -> int:
        return len(self._workers)
