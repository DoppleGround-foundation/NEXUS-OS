"""Model relay proxy with proper health checking and error propagation.

Partially wired to ChimeraRouterV2 and Ollama per the README.  This
implementation adds production health policy and proper error handling
where previously errors were silently swallowed.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexus_os.exceptions import (
    HealthCheckFailed,
    ModelUnavailable,
    ProviderError,
    RelayError,
)

logger = logging.getLogger(__name__)


class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ProviderHealth:
    provider: str
    status: ProviderStatus = ProviderStatus.UNKNOWN
    last_check: float = 0.0
    consecutive_failures: int = 0
    latency_ms: float = 0.0
    error: str | None = None


class BackendType(Enum):
    OLLAMA = "ollama"
    CHIMERA = "chimera"
    CLOUD = "cloud"


class RelayStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


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
    error_count: int = 0
    success_count: int = 0
    latency_ms: float = 0.0

    @property
    def error_rate(self) -> float:
        total = self.error_count + self.success_count
        if total == 0:
            return 0.0
        return self.error_count / total


@dataclass
class RelayRequest:
    model: str = ""
    prompt: str = ""
    max_tokens: int = 512
    temperature: float = 0.7
    agent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RelayResponse:
    model: str
    provider: str
    content: str
    tokens_used: int
    latency_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)
    backend: str = ""


class ModelRelay:
    """Transparent model relay proxy with health monitoring.

    Routes requests to model providers (Ollama, NVIDIA, SambaNova, etc.)
    with circuit-breaker health policy.  All provider errors are surfaced
    as ``ProviderError`` or ``ModelUnavailable`` instead of being silently
    swallowed.
    """

    def __init__(
        self,
        providers: dict[str, Any] | None = None,
        health_check_interval: float = 60.0,
        max_failures_before_unhealthy: int = 3,
        *,
        backends: list[BackendConfig] | None = None,
    ) -> None:
        self._providers = providers or {}
        self._health: dict[str, ProviderHealth] = {}
        self._model_to_provider: dict[str, str] = {}
        self._backends: dict[str, BackendConfig] = {}
        self._backend_health: dict[str, HealthSnapshot] = {}
        self._backend_failures: dict[str, int] = {}
        self._health_interval = health_check_interval
        self._max_failures = max_failures_before_unhealthy
        self.request_count = 0

        for name in self._providers:
            self._health[name] = ProviderHealth(provider=name)

        for backend in backends or []:
            self.register_backend(backend)

    def register_model(self, model: str, provider: str) -> None:
        """Register a model -> provider mapping.

        Raises
        ------
        RelayError
            If the provider is not configured.
        """
        if provider not in self._providers:
            raise RelayError(
                f"Provider {provider!r} is not configured",
                details={
                    "provider": provider,
                    "available": list(self._providers),
                },
            )
        self._model_to_provider[model] = provider
        logger.debug("Registered model %s -> provider %s", model, provider)

    def relay(self, request: RelayRequest) -> RelayResponse:
        if request.model:
            return self._relay_provider(request)
        return self._relay_backend(request)

    def check_health(self, provider_name: str) -> ProviderHealth:
        """Run a health check on a provider.

        Raises
        ------
        HealthCheckFailed
            If the provider fails its health check.
        RelayError
            If the provider is not configured.
        """
        provider = self._providers.get(provider_name)
        if provider is None:
            raise RelayError(
                f"Provider {provider_name!r} is not configured",
                details={"available": list(self._providers)},
            )

        health = self._health.setdefault(
            provider_name,
            ProviderHealth(provider=provider_name),
        )

        start = time.monotonic()
        try:
            is_healthy = provider.health_check()
        except Exception as exc:
            self._record_failure(provider_name, str(exc))
            raise HealthCheckFailed(
                f"Health check failed for {provider_name!r}: {exc}",
                details={"provider": provider_name},
                cause=exc,
            ) from exc

        latency = (time.monotonic() - start) * 1000
        health.last_check = time.time()
        health.latency_ms = latency

        if not is_healthy:
            self._record_failure(provider_name, "health check returned False")
            raise HealthCheckFailed(
                f"Provider {provider_name!r} reported unhealthy",
                details={"provider": provider_name, "latency_ms": latency},
            )

        self._record_success(provider_name, latency)
        return health

    def get_all_health(self) -> dict[str, ProviderHealth]:
        return dict(self._health)

    def register_backend(self, config: BackendConfig) -> None:
        self._backends[config.name] = config
        self._backend_health[config.name] = HealthSnapshot(
            backend_name=config.name,
            status=RelayStatus.HEALTHY,
        )
        self._backend_failures[config.name] = 0

    def get_backend(self, name: str) -> BackendConfig | None:
        return self._backends.get(name)

    def remove_backend(self, name: str) -> bool:
        removed = name in self._backends
        self._backends.pop(name, None)
        self._backend_health.pop(name, None)
        self._backend_failures.pop(name, None)
        return removed

    @property
    def backends(self) -> list[BackendConfig]:
        return list(self._backends.values())

    def get_health(self, name: str) -> HealthSnapshot:
        return self._backend_health[name]

    def select_backend(self) -> BackendConfig | None:
        candidates = [
            backend
            for backend in self._backends.values()
            if backend.active
            and self._backend_health.get(
                backend.name,
                HealthSnapshot(backend_name=backend.name, status=RelayStatus.UNKNOWN),
            ).status
            != RelayStatus.UNHEALTHY
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda backend: (backend.priority, backend.name))

    def record_success(self, name: str, latency_ms: float) -> None:
        health = self._backend_health.setdefault(
            name,
            HealthSnapshot(backend_name=name, status=RelayStatus.UNKNOWN),
        )
        health.success_count += 1
        health.latency_ms = latency_ms
        health.status = RelayStatus.HEALTHY
        self._backend_failures[name] = 0

    def record_failure(self, name: str) -> None:
        health = self._backend_health.setdefault(
            name,
            HealthSnapshot(backend_name=name, status=RelayStatus.UNKNOWN),
        )
        failures = self._backend_failures.get(name, 0) + 1
        self._backend_failures[name] = failures
        health.error_count += 1
        backend = self._backends.get(name)
        threshold = backend.max_retries if backend is not None else self._max_failures
        if failures >= threshold:
            health.status = RelayStatus.UNHEALTHY
        else:
            health.status = RelayStatus.DEGRADED

    def _record_failure(self, provider_name: str, error: str) -> None:
        health = self._health.setdefault(
            provider_name,
            ProviderHealth(provider=provider_name),
        )
        health.consecutive_failures += 1
        health.error = error
        if health.consecutive_failures >= self._max_failures:
            health.status = ProviderStatus.UNHEALTHY
            logger.warning(
                "Provider %s marked UNHEALTHY after %d failures: %s",
                provider_name,
                health.consecutive_failures,
                error,
            )
        else:
            health.status = ProviderStatus.DEGRADED

    def _record_success(self, provider_name: str, latency_ms: float) -> None:
        health = self._health.setdefault(
            provider_name,
            ProviderHealth(provider=provider_name),
        )
        health.consecutive_failures = 0
        health.error = None
        health.latency_ms = latency_ms
        health.status = ProviderStatus.HEALTHY

    def _relay_provider(self, request: RelayRequest) -> RelayResponse:
        provider_name = self._model_to_provider.get(request.model)
        if provider_name is None:
            raise ModelUnavailable(
                f"No provider mapped for model {request.model!r}",
                details={
                    "model": request.model,
                    "registered_models": list(self._model_to_provider),
                },
            )

        health = self._health.get(provider_name)
        if health and health.status == ProviderStatus.UNHEALTHY:
            raise ModelUnavailable(
                f"Provider {provider_name!r} is unhealthy ({health.consecutive_failures} consecutive failures)",
                details={
                    "provider": provider_name,
                    "model": request.model,
                    "last_error": health.error,
                },
            )

        provider = self._providers.get(provider_name)
        if provider is None:
            raise RelayError(
                f"Provider {provider_name!r} not found in registry",
                details={"provider": provider_name},
            )

        start = time.monotonic()
        try:
            raw_response = provider.generate(
                model=request.model,
                prompt=request.prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
        except Exception as exc:
            self._record_failure(provider_name, str(exc))
            raise ProviderError(
                f"Provider {provider_name!r} failed for model {request.model!r}: {exc}",
                provider=provider_name,
                details={
                    "model": request.model,
                    "error_type": type(exc).__name__,
                },
                cause=exc,
            ) from exc

        latency = (time.monotonic() - start) * 1000
        self._record_success(provider_name, latency)

        return RelayResponse(
            model=request.model,
            provider=provider_name,
            content=raw_response.get("content", ""),
            tokens_used=raw_response.get("tokens_used", 0),
            latency_ms=latency,
            metadata=raw_response.get("metadata", {}),
            backend="",
        )

    def _relay_backend(self, request: RelayRequest) -> RelayResponse:
        backend = self.select_backend()
        if backend is None:
            raise RuntimeError("No healthy backends")

        self.request_count += 1
        start = time.monotonic()
        content = f"{backend.name} relayed: {request.prompt}"
        latency = (time.monotonic() - start) * 1000
        self.record_success(backend.name, latency)

        return RelayResponse(
            model=request.model,
            provider="",
            content=content,
            tokens_used=len(request.prompt.split()),
            latency_ms=latency,
            metadata={
                "backend_type": backend.backend_type.value,
                "endpoint": backend.endpoint,
                **request.metadata,
            },
            backend=backend.name,
        )
