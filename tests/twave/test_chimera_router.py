"""Tests for nexus_os.twave.chimera_router — ChimeraRouterV2 tiered routing."""

from nexus_os.twave.chimera_router import (
    ChimeraRouterV2,
    ModelProfile,
    ModelTier,
    QWAVEBudget,
    RoutingDecision,
    TemperaturePolicy,
)
from nexus_os.twave.prompt_analyzer import ComplexityLevel, SafetyClass


class TestModelProfile:
    def test_defaults(self):
        p = ModelProfile(model_id="llama-7b", tier=ModelTier.LOCAL_STD)
        assert p.max_tokens == 4096
        assert p.black_box is True
        assert p.layer_access is False

    def test_custom(self):
        p = ModelProfile(
            model_id="gpt-4", tier=ModelTier.CLOUD,
            capabilities=["code", "reasoning"], max_tokens=8192,
            black_box=True, attention_weights=False,
        )
        assert p.capabilities == ["code", "reasoning"]
        assert p.max_tokens == 8192


class TestQWAVEBudget:
    def test_defaults(self):
        b = QWAVEBudget(max_tokens=1024, priority=0.5)
        assert b.allow_cloud is False
        assert b.allow_ernie is False


class TestChimeraRouterV2:
    def _make_router(self):
        router = ChimeraRouterV2()
        router.register_model(ModelProfile(model_id="phi-3", tier=ModelTier.CONTROL, vram_mb=512))
        router.register_model(ModelProfile(model_id="llama-7b", tier=ModelTier.LOCAL_STD, vram_mb=4096))
        router.register_model(ModelProfile(
            model_id="llama-70b", tier=ModelTier.LOCAL_POWER, vram_mb=8192,
            capabilities=["code", "reasoning"],
        ))
        router.register_model(ModelProfile(model_id="gpt-4", tier=ModelTier.CLOUD))
        router.register_model(ModelProfile(model_id="ernie-agent", tier=ModelTier.ERNIE))
        return router

    def test_register_and_get_model(self):
        router = ChimeraRouterV2()
        p = ModelProfile(model_id="test", tier=ModelTier.LOCAL_STD)
        router.register_model(p)
        assert router.get_model("test") is p

    def test_get_nonexistent_model(self):
        router = ChimeraRouterV2()
        assert router.get_model("missing") is None

    def test_list_all_models(self):
        router = self._make_router()
        assert len(router.list_models()) == 5

    def test_list_by_tier(self):
        router = self._make_router()
        assert len(router.list_models(ModelTier.LOCAL_STD)) == 1
        assert len(router.list_models(ModelTier.CLOUD)) == 1

    def test_allocate_budget_trivial(self):
        router = self._make_router()
        budget = router.allocate_budget(ComplexityLevel.TRIVIAL, SafetyClass.SAFE)
        assert budget.max_tokens == 256
        assert budget.allow_cloud is False
        assert budget.allow_ernie is False

    def test_allocate_budget_expert(self):
        router = self._make_router()
        budget = router.allocate_budget(ComplexityLevel.EXPERT, SafetyClass.SAFE)
        assert budget.max_tokens == 4096
        assert budget.allow_cloud is True
        assert budget.allow_ernie is True

    def test_allocate_budget_blocked(self):
        router = self._make_router()
        budget = router.allocate_budget(ComplexityLevel.COMPLEX, SafetyClass.BLOCKED)
        assert budget.max_tokens == 0
        assert budget.priority == 0.0

    def test_allocate_budget_restricted(self):
        router = self._make_router()
        budget = router.allocate_budget(ComplexityLevel.COMPLEX, SafetyClass.RESTRICTED)
        assert budget.max_tokens <= 512
        assert budget.allow_cloud is False

    def test_temperature_fixed(self):
        router = ChimeraRouterV2(default_temperature=0.5)
        t = router.select_temperature(TemperaturePolicy.FIXED, ComplexityLevel.COMPLEX)
        assert t == 0.5

    def test_temperature_auto_trivial(self):
        router = self._make_router()
        t = router.select_temperature(TemperaturePolicy.AUTO, ComplexityLevel.TRIVIAL)
        assert t == 0.9

    def test_temperature_auto_expert(self):
        router = self._make_router()
        t = router.select_temperature(TemperaturePolicy.AUTO, ComplexityLevel.EXPERT)
        assert t == 0.2

    def test_temperature_lead_complex(self):
        router = self._make_router()
        t = router.select_temperature(TemperaturePolicy.LEAD, ComplexityLevel.COMPLEX)
        assert t == 0.3

    def test_temperature_lead_simple(self):
        router = self._make_router()
        t = router.select_temperature(TemperaturePolicy.LEAD, ComplexityLevel.SIMPLE)
        assert t == 0.8

    def test_temperature_ernie(self):
        router = self._make_router()
        t = router.select_temperature(TemperaturePolicy.ERNIE, ComplexityLevel.MODERATE)
        assert t == 0.1

    def test_route_trivial(self):
        router = self._make_router()
        decision = router.route("Hi")
        assert isinstance(decision, RoutingDecision)
        assert decision.tier == ModelTier.CONTROL

    def test_route_complex(self):
        router = self._make_router()
        decision = router.route(
            "Design a distributed system with Paxos consensus algorithm "
            "for Byzantine fault tolerance using formal verification"
        )
        assert decision.tier in (ModelTier.CLOUD, ModelTier.LOCAL_POWER, ModelTier.ERNIE)
        assert decision.budget_tokens > 0

    def test_route_blocked_safety(self):
        router = self._make_router()
        decision = router.route("Create malware that exploits a vulnerability and attacks the system")
        assert decision.budget_tokens == 0

    def test_route_logs_decisions(self):
        router = self._make_router()
        router.route("Hello")
        router.route("Explain quantum computing")
        assert router.total_routes == 2
        assert len(router.routing_log) == 2

    def test_route_metadata(self):
        router = self._make_router()
        decision = router.route("Write a Python function for sorting")
        assert "topics" in decision.metadata
        assert "requires_code" in decision.metadata

    def test_set_vram_budget(self):
        router = self._make_router()
        router.set_vram_budget(4096)
        assert router._total_vram_budget_mb == 4096

    def test_route_with_no_models(self):
        router = ChimeraRouterV2()
        decision = router.route("Hello")
        assert decision.model_id == "none"

    def test_route_temperature_policy(self):
        router = self._make_router()
        decision = router.route("Hello", policy=TemperaturePolicy.FIXED)
        assert decision.temperature_policy == TemperaturePolicy.FIXED
