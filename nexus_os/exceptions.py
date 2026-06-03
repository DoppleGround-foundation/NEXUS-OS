"""Nexus OS exception hierarchy.

Every module raises domain-specific exceptions that inherit from a common
``NexusError`` base. This replaces all bare ``except: pass`` blocks with
structured, propagatable errors.

Hierarchy
---------
NexusError
 +-- GovernorError
 |    +-- KAIJUDenied
 |    +-- TrustBelowThreshold
 |    +-- CVAVerificationFailed
 |    +-- ProofChainError
 +-- EngineError
 |    +-- TaskRoutingError
 |    +-- ExecutionError
 |    +-- CircuitBreakerOpen
 |    +-- TaskDependencyCycle
 +-- VaultError
 |    +-- TrackNotFound
 |    +-- EncryptionRequired
 |    +-- EncryptionFailed
 |    +-- StorageCorrupted
 +-- BridgeError
 |    +-- RPCError
 |    +-- AuthenticationFailed
 |    +-- SecretNotFound
 +-- SecurityError
 |    +-- SanitizationError
 |    +-- IntegrityViolation
 |    +-- PTYError
 +-- MonitoringError
 |    +-- BudgetExceeded
 |    +-- TokenGuardError
 +-- SwarmError
 |    +-- WorkerAllocationFailed
 |    +-- AuctionFailed
 |    +-- TaskExecutionFailed
 +-- RelayError
 |    +-- ModelUnavailable
 |    +-- HealthCheckFailed
 |    +-- ProviderError
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("nexus_os")


class NexusError(Exception):
    """Base exception for all Nexus OS errors.

    Every subclass carries a ``code`` for machine-readable identification and
    an optional ``details`` dict for structured context that gets logged and
    propagated through the VAP audit chain.
    """

    code: str = "NEXUS_ERROR"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.details = details or {}
        if cause is not None:
            self.__cause__ = cause


# -- Governor ----------------------------------------------------------------

class GovernorError(NexusError):
    """Base for all governance-layer errors."""
    code = "GOVERNOR_ERROR"


class KAIJUDenied(GovernorError):
    """A KAIJU gate denied the proposed action."""
    code = "KAIJU_DENIED"

    def __init__(
        self,
        message: str,
        *,
        gate_stage: int | None = None,
        agent_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged = {**(details or {}), "gate_stage": gate_stage, "agent_id": agent_id}
        super().__init__(message, details=merged)


class TrustBelowThreshold(GovernorError):
    """Agent trust score is below the required threshold."""
    code = "TRUST_BELOW_THRESHOLD"

    def __init__(
        self,
        message: str,
        *,
        current_score: float,
        threshold: float,
        agent_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged = {
            **(details or {}),
            "current_score": current_score,
            "threshold": threshold,
            "agent_id": agent_id,
        }
        super().__init__(message, details=merged)


class CVAVerificationFailed(GovernorError):
    """Core Value Alignment verification failed."""
    code = "CVA_VERIFICATION_FAILED"


class ProofChainError(GovernorError):
    """VAP proof chain integrity violation."""
    code = "PROOF_CHAIN_ERROR"


# -- Engine ------------------------------------------------------------------

class EngineError(NexusError):
    """Base for all engine/routing errors."""
    code = "ENGINE_ERROR"


class TaskRoutingError(EngineError):
    """Failed to route a task to an appropriate handler."""
    code = "TASK_ROUTING_ERROR"


class ExecutionError(EngineError):
    """Task execution failed."""
    code = "EXECUTION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        task_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged = {**(details or {}), "task_id": task_id}
        super().__init__(message, details=merged)


class CircuitBreakerOpen(EngineError):
    """Circuit breaker tripped — model/service temporarily unavailable."""
    code = "CIRCUIT_BREAKER_OPEN"


class TaskDependencyCycle(EngineError):
    """Detected a cycle in task dependencies."""
    code = "TASK_DEPENDENCY_CYCLE"


# -- Vault -------------------------------------------------------------------

class VaultError(NexusError):
    """Base for all vault/storage errors."""
    code = "VAULT_ERROR"


class TrackNotFound(VaultError):
    """Requested memory track does not exist."""
    code = "TRACK_NOT_FOUND"


class EncryptionRequired(VaultError):
    """Operation requires encryption but ``allow_unencrypted`` is not set."""
    code = "ENCRYPTION_REQUIRED"


class EncryptionFailed(VaultError):
    """Encryption or decryption operation failed."""
    code = "ENCRYPTION_FAILED"


class StorageCorrupted(VaultError):
    """Storage integrity check failed — data may be corrupted."""
    code = "STORAGE_CORRUPTED"


# -- Bridge ------------------------------------------------------------------

class BridgeError(NexusError):
    """Base for all bridge/API errors."""
    code = "BRIDGE_ERROR"


class RPCError(BridgeError):
    """JSON-RPC call failed."""
    code = "RPC_ERROR"

    def __init__(
        self,
        message: str,
        *,
        rpc_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged = {**(details or {}), "rpc_code": rpc_code}
        super().__init__(message, details=merged)


class AuthenticationFailed(BridgeError):
    """Authentication or authorization check failed."""
    code = "AUTHENTICATION_FAILED"


class SecretNotFound(BridgeError):
    """Required secret is not available in the secrets store."""
    code = "SECRET_NOT_FOUND"


# -- Security ----------------------------------------------------------------

class SecurityError(NexusError):
    """Base for all security-layer errors."""
    code = "SECURITY_ERROR"


class SanitizationError(SecurityError):
    """Output sanitization detected dangerous content that could not be cleaned."""
    code = "SANITIZATION_ERROR"


class IntegrityViolation(SecurityError):
    """SHA-256 content hash mismatch — content was tampered with."""
    code = "INTEGRITY_VIOLATION"


class PTYError(SecurityError):
    """Agent PTY allocation or I/O error."""
    code = "PTY_ERROR"


# -- Monitoring --------------------------------------------------------------

class MonitoringError(NexusError):
    """Base for all monitoring errors."""
    code = "MONITORING_ERROR"


class BudgetExceeded(MonitoringError):
    """Token or resource budget has been exceeded."""
    code = "BUDGET_EXCEEDED"

    def __init__(
        self,
        message: str,
        *,
        used: int | float,
        limit: int | float,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged = {**(details or {}), "used": used, "limit": limit}
        super().__init__(message, details=merged)


class TokenGuardError(MonitoringError):
    """TokenGuard enforcement error."""
    code = "TOKEN_GUARD_ERROR"


# -- Swarm -------------------------------------------------------------------

class SwarmError(NexusError):
    """Base for all swarm/worker errors."""
    code = "SWARM_ERROR"


class WorkerAllocationFailed(SwarmError):
    """Could not allocate a worker for the task."""
    code = "WORKER_ALLOCATION_FAILED"


class AuctionFailed(SwarmError):
    """Task auction did not produce a winning bid."""
    code = "AUCTION_FAILED"


class TaskExecutionFailed(SwarmError):
    """Worker failed to execute the assigned task."""
    code = "TASK_EXECUTION_FAILED"


# -- Relay -------------------------------------------------------------------

class RelayError(NexusError):
    """Base for all relay/model proxy errors."""
    code = "RELAY_ERROR"


class ModelUnavailable(RelayError):
    """Requested model is not available or healthy."""
    code = "MODEL_UNAVAILABLE"


class HealthCheckFailed(RelayError):
    """Health check for a model provider failed."""
    code = "HEALTH_CHECK_FAILED"


class ProviderError(RelayError):
    """Upstream model provider returned an error."""
    code = "PROVIDER_ERROR"

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged = {
            **(details or {}),
            "provider": provider,
            "status_code": status_code,
        }
        super().__init__(message, details=merged)
