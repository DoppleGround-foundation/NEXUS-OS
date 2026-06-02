"""ChimeraRouterV2 - Tiered model routing with ERNIE callback.

Routes prompts to the appropriate model tier:
  Control -> Local Std -> Local Power -> Cloud
with ERNIE external agent callback for complex tasks.

Includes QWAVE budget allocator and 6 temperature policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexus_os.twave.prompt_analyzer import ComplexityLevel, PromptAnalyzer, SafetyClass


class ModelTier(Enum):
    CONTROL = "control"
    LOCAL_STD = "local_std"
    LOCAL_POWER = "local_power"
    CLOUD = "cloud"
    ERNIE = "ernie"


class TemperaturePolicy(Enum):
    FIXED = "fixed"
    EDT = "edt"
    EAD = "ead"
    LEAD = "lead"
    AUTO = "auto"
    ERNIE = "ernie"


@dataclass
class ModelProfile:
    model_id: str
    tier: ModelTier
    capabilities: list[str] = field(default_factory=list)
    max_tokens: int = 4096
    vram_mb: int = 0
    black_box: bool = True
    layer_access: bool = False
    attention_weights: bool = False


@dataclass
class RoutingDecision:
    model_id: str
    tier: ModelTier
    temperature: float
    temperature_policy: TemperaturePolicy
    budget_tokens: int
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QWAVEBudget:
    """Budget allocation from QWAVE allocator."""
    max_tokens: int
    priority: float
    allow_cloud: bool = False
    allow_ernie: bool = False


class ChimeraRouterV2:
    """Tiered model routing with complexity-aware selection."""

    def __init__(self, default_temperature: float = 0.7) -> None:
        self._models: dict[str, ModelProfile] = {}
        self._analyzer = PromptAnalyzer()
        self._default_temperature = default_temperature
        self._routing_log: list[RoutingDecision] = []
        self._total_vram_budget_mb: int = 8192

    def register_model(self, profile: ModelProfile) -> None:
        self._models[profile.model_id] = profile

    def get_model(self, model_id: str) -> ModelProfile | None:
        return self._models.get(model_id)

    def list_models(self, tier: ModelTier | None = None) -> list[ModelProfile]:
        if tier is None:
            return list(self._models.values())
        return [m for m in self._models.values() if m.tier == tier]

    def set_vram_budget(self, budget_mb: int) -> None:
        self._total_vram_budget_mb = budget_mb

    def allocate_budget(self, complexity: ComplexityLevel, safety: SafetyClass) -> QWAVEBudget:
        """QWAVE budget allocation based on prompt analysis."""
        base_tokens = {
            ComplexityLevel.TRIVIAL: 256,
            ComplexityLevel.SIMPLE: 512,
            ComplexityLevel.MODERATE: 1024,
            ComplexityLevel.COMPLEX: 2048,
            ComplexityLevel.EXPERT: 4096,
        }
        tokens = base_tokens.get(complexity, 1024)
        allow_cloud = complexity in (ComplexityLevel.COMPLEX, ComplexityLevel.EXPERT)
        allow_ernie = complexity == ComplexityLevel.EXPERT

        if safety == SafetyClass.BLOCKED:
            return QWAVEBudget(max_tokens=0, priority=0.0)
        if safety == SafetyClass.RESTRICTED:
            tokens = min(tokens, 512)
            allow_cloud = False
            allow_ernie = False

        priority = {
            ComplexityLevel.TRIVIAL: 0.2,
            ComplexityLevel.SIMPLE: 0.4,
            ComplexityLevel.MODERATE: 0.6,
            ComplexityLevel.COMPLEX: 0.8,
            ComplexityLevel.EXPERT: 1.0,
        }.get(complexity, 0.5)

        return QWAVEBudget(
            max_tokens=tokens,
            priority=priority,
            allow_cloud=allow_cloud,
            allow_ernie=allow_ernie,
        )

    def select_temperature(self, policy: TemperaturePolicy, complexity: ComplexityLevel) -> float:
        """Select temperature based on policy and complexity."""
        if policy == TemperaturePolicy.FIXED:
            return self._default_temperature
        if policy == TemperaturePolicy.EDT:
            return max(0.1, self._default_temperature - 0.1 * complexity.value.__len__())
        if policy == TemperaturePolicy.EAD:
            return min(1.5, self._default_temperature + 0.05 * complexity.value.__len__())
        if policy == TemperaturePolicy.LEAD:
            return 0.3 if complexity in (ComplexityLevel.EXPERT, ComplexityLevel.COMPLEX) else 0.8
        if policy == TemperaturePolicy.ERNIE:
            return 0.1
        # AUTO
        complexity_temps = {
            ComplexityLevel.TRIVIAL: 0.9,
            ComplexityLevel.SIMPLE: 0.7,
            ComplexityLevel.MODERATE: 0.5,
            ComplexityLevel.COMPLEX: 0.3,
            ComplexityLevel.EXPERT: 0.2,
        }
        return complexity_temps.get(complexity, self._default_temperature)

    def _select_tier(self, complexity: ComplexityLevel, budget: QWAVEBudget) -> ModelTier:
        if budget.max_tokens == 0:
            return ModelTier.CONTROL
        if complexity == ComplexityLevel.EXPERT and budget.allow_ernie:
            return ModelTier.ERNIE
        if complexity in (ComplexityLevel.COMPLEX, ComplexityLevel.EXPERT) and budget.allow_cloud:
            return ModelTier.CLOUD
        if complexity in (ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX):
            return ModelTier.LOCAL_POWER
        if complexity == ComplexityLevel.SIMPLE:
            return ModelTier.LOCAL_STD
        return ModelTier.CONTROL

    def _select_model(self, tier: ModelTier) -> ModelProfile | None:
        candidates = self.list_models(tier)
        if not candidates:
            for fallback_tier in [ModelTier.LOCAL_STD, ModelTier.LOCAL_POWER, ModelTier.CONTROL]:
                candidates = self.list_models(fallback_tier)
                if candidates:
                    break
        if not candidates:
            return None
        return candidates[0]

    def route(self, prompt: str, policy: TemperaturePolicy = TemperaturePolicy.AUTO) -> RoutingDecision:
        """Route a prompt to the best model/tier."""
        analysis = self._analyzer.analyze(prompt)
        budget = self.allocate_budget(analysis.complexity, analysis.safety)
        tier = self._select_tier(analysis.complexity, budget)
        model = self._select_model(tier)
        temperature = self.select_temperature(policy, analysis.complexity)

        decision = RoutingDecision(
            model_id=model.model_id if model else "none",
            tier=tier,
            temperature=temperature,
            temperature_policy=policy,
            budget_tokens=budget.max_tokens,
            reason=f"complexity={analysis.complexity.value}, safety={analysis.safety.value}",
            metadata={
                "topics": analysis.topics,
                "requires_code": analysis.requires_code,
                "estimated_tokens": analysis.estimated_tokens,
            },
        )
        self._routing_log.append(decision)
        return decision

    @property
    def routing_log(self) -> list[RoutingDecision]:
        return list(self._routing_log)

    @property
    def total_routes(self) -> int:
        return len(self._routing_log)
