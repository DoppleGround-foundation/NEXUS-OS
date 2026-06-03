"""Tests validating that errors are properly propagated, not silently swallowed.

Each test verifies a specific error-handling improvement:
- Exceptions are raised (not caught and discarded)
- Error details are preserved for debugging and auditing
- The exception hierarchy is correct
"""

from __future__ import annotations

import pytest

from nexus_os.exceptions import (
    AuthenticationFailed,
    BridgeError,
    BudgetExceeded,
    CVAVerificationFailed,
    EncryptionRequired,
    ExecutionError,
    GovernorError,
    HealthCheckFailed,
    IntegrityViolation,
    KAIJUDenied,
    ModelUnavailable,
    NexusError,
    ProofChainError,
    ProviderError,
    PTYError,
    RPCError,
    SanitizationError,
    SecretNotFound,
    StorageCorrupted,
    SwarmError,
    TaskExecutionFailed,
    TaskRoutingError,
    TokenGuardError,
    TrackNotFound,
    TrustBelowThreshold,
    VaultError,
    WorkerAllocationFailed,
)


# ---------------------------------------------------------------------------
# Exception hierarchy tests
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    """Verify all exceptions inherit from NexusError and carry details."""

    def test_nexus_error_base(self) -> None:
        exc = NexusError("test", details={"key": "val"})
        assert str(exc) == "test"
        assert exc.details == {"key": "val"}
        assert exc.code == "NEXUS_ERROR"

    def test_governor_errors_inherit(self) -> None:
        for cls in [GovernorError, KAIJUDenied, TrustBelowThreshold,
                     CVAVerificationFailed, ProofChainError]:
            assert issubclass(cls, NexusError)

    def test_engine_errors_inherit(self) -> None:
        for cls in [TaskRoutingError, ExecutionError]:
            assert issubclass(cls, NexusError)

    def test_vault_errors_inherit(self) -> None:
        for cls in [VaultError, TrackNotFound, EncryptionRequired, StorageCorrupted]:
            assert issubclass(cls, NexusError)

    def test_bridge_errors_inherit(self) -> None:
        for cls in [BridgeError, RPCError, AuthenticationFailed, SecretNotFound]:
            assert issubclass(cls, NexusError)

    def test_kaiju_denied_carries_details(self) -> None:
        exc = KAIJUDenied("denied", gate_stage=3, agent_id="agent-1")
        assert exc.details["gate_stage"] == 3
        assert exc.details["agent_id"] == "agent-1"

    def test_trust_below_threshold_carries_scores(self) -> None:
        exc = TrustBelowThreshold(
            "too low", current_score=15.0, threshold=25.0, agent_id="a1",
        )
        assert exc.details["current_score"] == 15.0
        assert exc.details["threshold"] == 25.0

    def test_budget_exceeded_carries_limits(self) -> None:
        exc = BudgetExceeded("over", used=100, limit=50)
        assert exc.details["used"] == 100
        assert exc.details["limit"] == 50

    def test_provider_error_carries_provider(self) -> None:
        exc = ProviderError("fail", provider="nvidia", status_code=500)
        assert exc.details["provider"] == "nvidia"
        assert exc.details["status_code"] == 500


# ---------------------------------------------------------------------------
# Governor: KAIJU gates + CVA + VAP chain
# ---------------------------------------------------------------------------

class TestKAIJUGate:
    """Verify KAIJU gate propagates errors instead of swallowing them."""

    def test_empty_action_denied(self) -> None:
        from nexus_os.governor.base import KAIJUGate
        gate = KAIJUGate()
        result = gate.evaluate("agent-1", "", {})
        assert result.decision.value == "DENY"

    def test_injection_hard_stop(self) -> None:
        from nexus_os.governor.base import KAIJUGate
        gate = KAIJUGate()
        with pytest.raises(KAIJUDenied) as exc_info:
            gate.evaluate("agent-1", "eval(bad_code)", {})
        assert "injection" in str(exc_info.value).lower()

    def test_cva_safety_violation_raises(self) -> None:
        from nexus_os.governor.base import verify_core_value_alignment
        with pytest.raises(CVAVerificationFailed):
            verify_core_value_alignment(
                "deploy",
                {"safety_review": {"passed": False, "reason": "not reviewed"}},
                required_values=["safety_first"],
            )

    def test_cva_passes_with_all_evidence(self) -> None:
        from nexus_os.governor.base import verify_core_value_alignment
        passed, reason = verify_core_value_alignment(
            "deploy",
            {
                "evidence": "test report",
                "proposal_id": "P-123",
                "tests_passed": True,
                "audit_trail": "chain:abc",
                "safety_review": {"passed": True},
            },
        )
        assert passed is True

    def test_cva_fails_without_evidence(self) -> None:
        from nexus_os.governor.base import verify_core_value_alignment
        passed, reason = verify_core_value_alignment(
            "deploy", {}, required_values=["evidence_grounded"],
        )
        assert passed is False
        assert "evidence" in reason.lower()


class TestVAPChain:
    """Verify proof chain raises on integrity violations."""

    def test_valid_chain(self) -> None:
        from nexus_os.governor.base import VAPChain
        chain = VAPChain()
        chain.append("agent-1", "action-a", "hash-a")
        chain.append("agent-1", "action-b", "hash-b")
        chain.verify_integrity()  # should not raise

    def test_tampered_chain_raises(self) -> None:
        from nexus_os.governor.base import VAPChain
        chain = VAPChain()
        chain.append("agent-1", "action-a", "hash-a")
        chain.append("agent-1", "action-b", "hash-b")
        # Tamper with the chain
        chain._entries[0] = chain._entries[0].__class__(
            sequence=0,
            timestamp=chain._entries[0].timestamp,
            agent_id="agent-1",
            action="action-a",
            result_hash="hash-a",
            prev_hash="0" * 64,
            entry_hash="tampered",
        )
        with pytest.raises(ProofChainError):
            chain.verify_integrity()


# ---------------------------------------------------------------------------
# TrustEngine
# ---------------------------------------------------------------------------

class TestTrustEngine:
    """Verify trust engine errors are propagated."""

    def test_unregistered_agent_raises(self) -> None:
        from nexus_os.governor.trust_engine import TrustEngine
        engine = TrustEngine()
        with pytest.raises(GovernorError, match="not registered"):
            engine.get_score("unknown-agent")

    def test_negative_reward_raises(self) -> None:
        from nexus_os.governor.trust_engine import TrustEngine
        engine = TrustEngine()
        engine.register_agent("a1")
        with pytest.raises(GovernorError, match="positive"):
            engine.reward("a1", -5.0)

    def test_require_threshold_raises(self) -> None:
        from nexus_os.governor.trust_engine import TrustEngine
        engine = TrustEngine()
        engine.register_agent("a1", initial_score=10.0)
        with pytest.raises(TrustBelowThreshold) as exc_info:
            engine.require_threshold("a1", 50.0)
        assert exc_info.value.details["current_score"] == 10.0

    def test_critical_violation_forces_critical_cdr(self) -> None:
        from nexus_os.governor.trust_engine import CDRStage, TrustEngine
        engine = TrustEngine()
        engine.register_agent("a1", initial_score=80.0)
        engine.critical_violation("a1", reason="safety breach")
        assert engine.get_cdr_stage("a1") == CDRStage.CRITICAL


# ---------------------------------------------------------------------------
# Vault
# ---------------------------------------------------------------------------

class TestVaultManager:
    """Verify vault errors are raised, not swallowed."""

    def test_invalid_track_raises(self) -> None:
        from nexus_os.vault.manager import VaultManager
        vault = VaultManager(allow_unencrypted=True)
        with pytest.raises(TrackNotFound, match="bogus"):
            vault.store_track("bogus", "key", "val")

    def test_encryption_required_raises(self) -> None:
        from nexus_os.vault.manager import VaultManager
        vault = VaultManager(allow_unencrypted=False)
        with pytest.raises(EncryptionRequired):
            vault.store_track("event", "key", "val")

    def test_missing_key_raises(self) -> None:
        from nexus_os.vault.manager import VaultManager
        vault = VaultManager(allow_unencrypted=True)
        with pytest.raises(VaultError, match="not found"):
            vault.retrieve_track("event", "nonexistent")

    def test_store_and_retrieve_plaintext(self) -> None:
        from nexus_os.vault.manager import VaultManager
        vault = VaultManager(allow_unencrypted=True)
        vault.store_track("event", "test-key", "test-value")
        result = vault.retrieve_track("event", "test-key")
        assert result == "test-value"


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------

class TestBridgeServer:
    """Verify bridge propagates errors as structured RPC responses."""

    def test_parse_error(self) -> None:
        import json
        from nexus_os.bridge.server import BridgeServer
        server = BridgeServer()
        raw = server.handle_raw("not json")
        resp = json.loads(raw)
        assert resp["error"]["code"] == -32700

    def test_method_not_found(self) -> None:
        import json
        from nexus_os.bridge.server import BridgeServer
        server = BridgeServer()
        raw = server.handle_raw('{"jsonrpc":"2.0","method":"nope","id":1}')
        resp = json.loads(raw)
        assert resp["error"]["code"] == -32601

    def test_handler_exception_wrapped(self) -> None:
        import json
        from nexus_os.bridge.server import BridgeServer
        server = BridgeServer()

        def bad_handler() -> None:
            raise ValueError("boom")

        server.register_method("bad", bad_handler)
        raw = server.handle_raw('{"jsonrpc":"2.0","method":"bad","id":2}')
        resp = json.loads(raw)
        assert resp["error"]["code"] == -32603

    def test_secrets_not_found_raises(self) -> None:
        from nexus_os.bridge.server import SecretsManager
        sm = SecretsManager()
        with pytest.raises(SecretNotFound, match="nvidia"):
            sm.get_secret("nvidia")

    def test_internal_call_method_not_found(self) -> None:
        from nexus_os.bridge.server import BridgeServer
        server = BridgeServer()
        with pytest.raises(RPCError, match="not found"):
            server.call("nonexistent")


# ---------------------------------------------------------------------------
# Engine: Executor
# ---------------------------------------------------------------------------

class TestBridgeExecutor:
    """Verify executor no longer returns success=False silently."""

    def test_no_bridge_raises(self) -> None:
        from nexus_os.engine.executor import BridgeExecutor
        executor = BridgeExecutor(bridge_client=None)
        with pytest.raises(ExecutionError, match="No bridge client"):
            executor.execute("t1", "action", {})

    def test_kaiju_denial_propagated(self) -> None:
        from unittest.mock import MagicMock
        from nexus_os.engine.executor import BridgeExecutor
        from nexus_os.governor.base import GateDecision, GateResult

        mock_kaiju = MagicMock()
        mock_kaiju.evaluate.return_value = GateResult(
            decision=GateDecision.DENY, reason="trust too low", stage=2,
        )
        executor = BridgeExecutor(bridge_client=MagicMock(), kaiju_gate=mock_kaiju)
        with pytest.raises(KAIJUDenied, match="trust too low"):
            executor.execute("t1", "action", {}, agent_id="a1")


# ---------------------------------------------------------------------------
# Hermes router
# ---------------------------------------------------------------------------

class TestHermesRouter:
    """Verify router errors are propagated, not silently dropped."""

    def test_empty_description_raises(self) -> None:
        from nexus_os.engine.hermes import TaskClassifier
        classifier = TaskClassifier()
        with pytest.raises(TaskRoutingError, match="empty"):
            classifier.classify("")

    def test_unknown_domain_marked_fallback(self) -> None:
        from nexus_os.engine.hermes import TaskClassifier, TaskDomain
        classifier = TaskClassifier()
        result = classifier.classify("xyzzy flurb garble")
        assert result.domain == TaskDomain.UNKNOWN
        assert result.fallback_used is True
        assert result.confidence < 0.5

    def test_code_generation_detected(self) -> None:
        from nexus_os.engine.hermes import TaskClassifier, TaskDomain
        classifier = TaskClassifier()
        result = classifier.classify("implement a new REST API endpoint")
        assert result.domain == TaskDomain.CODE_GENERATION


# ---------------------------------------------------------------------------
# Security: Sanitizer
# ---------------------------------------------------------------------------

class TestTerminalSanitizer:
    """Verify sanitizer raises on invalid input."""

    def test_strips_ansi_sequences(self) -> None:
        from nexus_os.security.sanitizer import TerminalSanitizer
        dirty = "hello\x1b[31mworld\x1b[0m"
        assert TerminalSanitizer.sanitize(dirty) == "helloworld"

    def test_non_string_raises(self) -> None:
        from nexus_os.security.sanitizer import TerminalSanitizer
        with pytest.raises(SanitizationError, match="Expected str"):
            TerminalSanitizer.sanitize(123)  # type: ignore[arg-type]


class TestVerifiableOutput:
    """Verify integrity checks raise on mismatch."""

    def test_valid_output_passes(self) -> None:
        from nexus_os.security.sanitizer import VerifiableOutput
        vo = VerifiableOutput.create("hello")
        vo.verify()  # should not raise

    def test_tampered_output_raises(self) -> None:
        from nexus_os.security.sanitizer import VerifiableOutput
        vo = VerifiableOutput(content="hello", content_hash="bad_hash")
        with pytest.raises(IntegrityViolation):
            vo.verify()


# ---------------------------------------------------------------------------
# Monitoring: TokenGuard
# ---------------------------------------------------------------------------

class TestTokenGuard:
    """Verify budget enforcement raises, not silently allows."""

    def test_unregistered_agent_raises(self) -> None:
        from nexus_os.monitoring.token_guard import TokenGuard
        guard = TokenGuard()
        with pytest.raises(TokenGuardError, match="not registered"):
            guard.check_budget("unknown")

    def test_budget_exceeded_raises(self) -> None:
        from nexus_os.monitoring.token_guard import TokenGuard
        guard = TokenGuard(default_limit=100)
        guard.register_agent("a1", limit=100)
        guard.consume("a1", 100)
        with pytest.raises(BudgetExceeded):
            guard.consume("a1", 1)

    def test_negative_consumption_raises(self) -> None:
        from nexus_os.monitoring.token_guard import TokenGuard
        guard = TokenGuard()
        guard.register_agent("a1")
        with pytest.raises(TokenGuardError, match="negative"):
            guard.consume("a1", -10)


# ---------------------------------------------------------------------------
# Swarm: Worker
# ---------------------------------------------------------------------------

class TestWorker:
    """Verify worker raises on failure instead of returning fake output."""

    def test_no_executor_raises(self) -> None:
        from nexus_os.swarm.worker import TaskAssignment, Worker
        worker = Worker("w1", executor=None)
        assignment = TaskAssignment(
            task_id="t1", action="test", context={}, agent_id="a1",
        )
        with pytest.raises(TaskExecutionFailed, match="no executor"):
            worker.execute_task(assignment)

    def test_busy_worker_raises(self) -> None:
        from nexus_os.swarm.worker import TaskAssignment, Worker, WorkerStatus
        worker = Worker("w1", executor=lambda a, c: None)
        worker._state.status = WorkerStatus.BUSY
        assignment = TaskAssignment(
            task_id="t1", action="test", context={}, agent_id="a1",
        )
        with pytest.raises(WorkerAllocationFailed, match="busy"):
            worker.execute_task(assignment)

    def test_executor_exception_wrapped(self) -> None:
        from nexus_os.swarm.worker import TaskAssignment, Worker

        def bad_executor(action: str, ctx: dict) -> None:
            raise RuntimeError("connection lost")

        worker = Worker("w1", executor=bad_executor)
        assignment = TaskAssignment(
            task_id="t1", action="test", context={}, agent_id="a1",
        )
        with pytest.raises(TaskExecutionFailed, match="connection lost"):
            worker.execute_task(assignment)


# ---------------------------------------------------------------------------
# Relay
# ---------------------------------------------------------------------------

class TestModelRelay:
    """Verify relay propagates provider errors."""

    def test_unmapped_model_raises(self) -> None:
        from nexus_os.relay.model_relay import ModelRelay, RelayRequest
        relay = ModelRelay()
        with pytest.raises(ModelUnavailable, match="No provider"):
            relay.relay(RelayRequest(model="unknown", prompt="hi"))

    def test_unregistered_provider_raises(self) -> None:
        from nexus_os.relay.model_relay import ModelRelay
        relay = ModelRelay()
        with pytest.raises(HealthCheckFailed.__mro__[1]):
            relay.register_model("model-a", "nonexistent")

    def test_unhealthy_provider_raises(self) -> None:
        from unittest.mock import MagicMock
        from nexus_os.relay.model_relay import (
            ModelRelay,
            ProviderStatus,
            RelayRequest,
        )
        mock_provider = MagicMock()
        relay = ModelRelay(providers={"test": mock_provider})
        relay.register_model("m1", "test")
        # Force unhealthy
        relay._health["test"].status = ProviderStatus.UNHEALTHY
        relay._health["test"].consecutive_failures = 5
        with pytest.raises(ModelUnavailable, match="unhealthy"):
            relay.relay(RelayRequest(model="m1", prompt="hi"))
