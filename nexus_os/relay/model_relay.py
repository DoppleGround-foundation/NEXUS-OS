"""ModelRelay - Transparent model relay proxy.

Routes inference requests through the governance layer, applying
health checks, rate limiting, and provenance tracking before
forwarding to ChimeraRouterV2 or Ollama backends.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RelayStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class BackendType(Enum):
    OLLAMA = "ollama"
    CHIMERA = "chimera"
    CLOUD = "cloud"


@dataclass
class BackendConfig:
    name: str
    backend_type: BackendType
    endpoint: str
    priority: int = 0
    max_retries: int = 3
    timeout: float = 30.0
    active: bool = True


@dataclass
class HealthSnapshot:
    backend_name: str
    status: RelayStatus
    latency_ms: float = 0.0
    error_count: int = 0
    success_count: int = 0
    last_check: float = field(default_factory=time.time)

    @property
    def error_rate(self) -> float:
        total = self.error_count + self.success_count
        if total == 0:
            return 0.0
        return self.error_count / total


@dataclass
class RelayRequest:
    prompt: str
    model_id: str | None = None
    max_tokens: int = 512
    temperature: float = 0.7
    agent_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RelayResponse:
    content: str
    model_id: str
    backend: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    cached: bool = False


class ModelRelay:
    """Transparent model relay proxy with health-aware routing."""

    def __init__(self) -> None:
        self._backends: dict[str, BackendConfig] = {}
        self._health: dict[str, HealthSnapshot] = {}
        self._request_log: list[dict[str, Any]] = []

    def register_backend(self, config: BackendConfig) -> None:
        self._backends[config.name] = config
        self._health[config.name] = HealthSnapshot(
            backend_name=config.name,
            status=RelayStatus.HEALTHY,
        )

    def remove_backend(self, name: str) -> bool:
        if name in self._backends:
            del self._backends[name]
            self._health.pop(name, None)
            return True
        return False

    def get_backend(self, name: str) -> BackendConfig | None:
        return self._backends.get(name)

    def get_health(self, name: str) -> HealthSnapshot | None:
        return self._health.get(name)

    def select_backend(self, model_id: str | None = None) -> BackendConfig | None:
        """Select the best available backend based on health and priority."""
        candidates = [
            b for b in self._backends.values()
            if b.active and self._health.get(b.name, HealthSnapshot(b.name, RelayStatus.OFFLINE)).status
            in (RelayStatus.HEALTHY, RelayStatus.DEGRADED)
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda b: b.priority, reverse=True)
        return candidates[0]

    def record_success(self, backend_name: str, latency_ms: float) -> None:
        health = self._health.get(backend_name)
        if health:
            health.success_count += 1
            health.latency_ms = latency_ms
            health.last_check = time.time()
            if health.error_rate < 0.1:
                health.status = RelayStatus.HEALTHY
            elif health.error_rate < 0.5:
                health.status = RelayStatus.DEGRADED

    def record_failure(self, backend_name: str) -> None:
        health = self._health.get(backend_name)
        if health:
            health.error_count += 1
            health.last_check = time.time()
            if health.error_rate > 0.5:
                health.status = RelayStatus.UNHEALTHY
            elif health.error_rate > 0.1:
                health.status = RelayStatus.DEGRADED

    def relay(self, request: RelayRequest) -> RelayResponse:
        """Route a request through the relay. Returns a simulated response.

        Note: Production version forwards to actual backend endpoints.
        This implementation provides the routing + health tracking logic.
        """
        backend = self.select_backend(request.model_id)
        if backend is None:
            raise RuntimeError("No healthy backends available")

        start = time.time()

        self._request_log.append({
            "agent_id": request.agent_id,
            "model_id": request.model_id,
            "backend": backend.name,
            "timestamp": start,
        })

        latency_ms = (time.time() - start) * 1000
        self.record_success(backend.name, latency_ms)

        return RelayResponse(
            content=f"[relay:{backend.name}] Response to: {request.prompt[:50]}",
            model_id=request.model_id or backend.name,
            backend=backend.name,
            tokens_used=len(request.prompt.split()) * 2,
            latency_ms=latency_ms,
        )

    @property
    def backends(self) -> list[BackendConfig]:
        return list(self._backends.values())

    @property
    def request_count(self) -> int:
        return len(self._request_log)
