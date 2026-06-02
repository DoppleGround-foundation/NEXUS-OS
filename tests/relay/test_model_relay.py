"""Tests for nexus_os.relay.model_relay — Transparent model relay proxy."""

import pytest

from nexus_os.relay.model_relay import (
    BackendConfig,
    BackendType,
    HealthSnapshot,
    ModelRelay,
    RelayRequest,
    RelayResponse,
    RelayStatus,
)


class TestBackendConfig:
    def test_defaults(self):
        cfg = BackendConfig(name="ollama", backend_type=BackendType.OLLAMA, endpoint="http://localhost:11434")
        assert cfg.priority == 0
        assert cfg.max_retries == 3
        assert cfg.timeout == 30.0
        assert cfg.active is True

    def test_custom_values(self):
        cfg = BackendConfig(
            name="cloud", backend_type=BackendType.CLOUD, endpoint="https://api.example.com",
            priority=10, max_retries=5, active=False,
        )
        assert cfg.priority == 10
        assert cfg.active is False


class TestHealthSnapshot:
    def test_error_rate_zero(self):
        h = HealthSnapshot(backend_name="test", status=RelayStatus.HEALTHY)
        assert h.error_rate == 0.0

    def test_error_rate_calculation(self):
        h = HealthSnapshot(backend_name="test", status=RelayStatus.DEGRADED, error_count=2, success_count=8)
        assert h.error_rate == pytest.approx(0.2)

    def test_error_rate_all_errors(self):
        h = HealthSnapshot(backend_name="test", status=RelayStatus.UNHEALTHY, error_count=5, success_count=0)
        assert h.error_rate == 1.0


class TestModelRelay:
    def _make_relay(self):
        relay = ModelRelay()
        relay.register_backend(BackendConfig(
            name="ollama", backend_type=BackendType.OLLAMA,
            endpoint="http://localhost:11434", priority=5,
        ))
        relay.register_backend(BackendConfig(
            name="chimera", backend_type=BackendType.CHIMERA,
            endpoint="http://localhost:7353", priority=10,
        ))
        return relay

    def test_register_backend(self):
        relay = ModelRelay()
        cfg = BackendConfig(name="test", backend_type=BackendType.OLLAMA, endpoint="http://localhost")
        relay.register_backend(cfg)
        assert relay.get_backend("test") is cfg

    def test_remove_backend(self):
        relay = self._make_relay()
        assert relay.remove_backend("ollama") is True
        assert relay.get_backend("ollama") is None
        assert relay.remove_backend("nonexistent") is False

    def test_list_backends(self):
        relay = self._make_relay()
        assert len(relay.backends) == 2

    def test_get_health(self):
        relay = self._make_relay()
        health = relay.get_health("ollama")
        assert health is not None
        assert health.status == RelayStatus.HEALTHY

    def test_select_backend_by_priority(self):
        relay = self._make_relay()
        selected = relay.select_backend()
        assert selected is not None
        assert selected.name == "chimera"

    def test_select_backend_skips_unhealthy(self):
        relay = self._make_relay()
        health = relay.get_health("chimera")
        health.status = RelayStatus.UNHEALTHY
        selected = relay.select_backend()
        assert selected.name == "ollama"

    def test_select_backend_none_available(self):
        relay = ModelRelay()
        assert relay.select_backend() is None

    def test_record_success(self):
        relay = self._make_relay()
        relay.record_success("ollama", 50.0)
        health = relay.get_health("ollama")
        assert health.success_count == 1
        assert health.latency_ms == 50.0

    def test_record_failure_degrades(self):
        relay = self._make_relay()
        for _ in range(5):
            relay.record_success("ollama", 10.0)
        relay.record_failure("ollama")
        health = relay.get_health("ollama")
        assert health.error_count == 1

    def test_record_failure_marks_unhealthy(self):
        relay = self._make_relay()
        relay.record_success("ollama", 10.0)
        for _ in range(3):
            relay.record_failure("ollama")
        health = relay.get_health("ollama")
        assert health.status == RelayStatus.UNHEALTHY

    def test_relay_request(self):
        relay = self._make_relay()
        request = RelayRequest(prompt="Hello world", agent_id="agent-1")
        response = relay.relay(request)
        assert isinstance(response, RelayResponse)
        assert response.backend == "chimera"
        assert "Hello world" in response.content

    def test_relay_increments_request_count(self):
        relay = self._make_relay()
        relay.relay(RelayRequest(prompt="test"))
        relay.relay(RelayRequest(prompt="test2"))
        assert relay.request_count == 2

    def test_relay_no_backends_raises(self):
        relay = ModelRelay()
        with pytest.raises(RuntimeError, match="No healthy backends"):
            relay.relay(RelayRequest(prompt="test"))

    def test_inactive_backend_not_selected(self):
        relay = ModelRelay()
        relay.register_backend(BackendConfig(
            name="inactive", backend_type=BackendType.CLOUD,
            endpoint="http://example.com", active=False,
        ))
        assert relay.select_backend() is None

    def test_degraded_backend_still_selectable(self):
        relay = ModelRelay()
        relay.register_backend(BackendConfig(
            name="deg", backend_type=BackendType.OLLAMA,
            endpoint="http://localhost", priority=1,
        ))
        health = relay.get_health("deg")
        health.status = RelayStatus.DEGRADED
        assert relay.select_backend() is not None
