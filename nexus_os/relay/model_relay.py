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


@dataclass
class RelayRequest:
    model: str
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RelayResponse:
    model: str
    provider: str
    content: str
    tokens_used: int
    latency_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


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
    ) -> None:
        self._providers = providers or {}
        self._health: dict[str, ProviderHealth] = {}
        self._model_to_provider: dict[str, str] = {}
        self._health_interval = health_check_interval
        self._max_failures = max_failures_before_unhealthy

        for name in self._providers:
            self._health[name] = ProviderHealth(provider=name)

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
        """Relay a request to the appropriate provider.

        Raises
        ------
        ModelUnavailable
            If no provider is mapped or the provider is unhealthy.
        ProviderError
            If the provider returns an error.
        """
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
                f"Provider {provider_name!r} is unhealthy "
                f"({health.consecutive_failures} consecutive failures)",
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
        )

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
            provider_name, ProviderHealth(provider=provider_name),
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

    def _record_failure(self, provider_name: str, error: str) -> None:
        health = self._health.setdefault(
            provider_name, ProviderHealth(provider=provider_name),
        )
        health.consecutive_failures += 1
        health.error = error
        if health.consecutive_failures >= self._max_failures:
            health.status = ProviderStatus.UNHEALTHY
            logger.warning(
                "Provider %s marked UNHEALTHY after %d failures: %s",
                provider_name, health.consecutive_failures, error,
            )
        else:
            health.status = ProviderStatus.DEGRADED

    def _record_success(self, provider_name: str, latency_ms: float) -> None:
        health = self._health.setdefault(
            provider_name, ProviderHealth(provider=provider_name),
        )
        health.consecutive_failures = 0
        health.error = None
        health.latency_ms = latency_ms
        health.status = ProviderStatus.HEALTHY
