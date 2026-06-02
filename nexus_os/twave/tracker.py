"""Landau-Ginzburg Hallucination Tracker - Token-level hallucination control.

Implements 5 sub-controllers for hallucination detection and mitigation:
  - EDT: Entropy-Driven Temperature (entropy -> temperature mapping)
  - LEAD: Latent-Discrete switching (latent <-> discrete mode)
  - EPR: Entropy Prediction Residual (black-box entropy detection)
  - LED: Layer-wise Exploration Depth (layer-level analysis)
  - CK-PLUG: Chemical-potential retrieval plug
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum


class ControllerType(Enum):
    EDT = "edt"
    LEAD = "lead"
    EPR = "epr"
    LED = "led"
    CK_PLUG = "ck_plug"


class HallucinationRisk(Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TokenMetrics:
    token: str
    entropy: float = 0.0
    confidence: float = 1.0
    layer_depth: int = 0
    is_hallucinated: bool = False
    controller_flags: list[ControllerType] = field(default_factory=list)


@dataclass
class SequenceAnalysis:
    tokens: list[TokenMetrics]
    overall_risk: HallucinationRisk = HallucinationRisk.LOW
    mean_entropy: float = 0.0
    max_entropy: float = 0.0
    hallucination_count: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def hallucination_rate(self) -> float:
        if not self.tokens:
            return 0.0
        return self.hallucination_count / len(self.tokens)

    @property
    def token_count(self) -> int:
        return len(self.tokens)


class EDTController:
    """Entropy-Driven Temperature: maps entropy to temperature adjustments."""

    def __init__(self, entropy_threshold: float = 2.0, scale_factor: float = 0.5) -> None:
        self.entropy_threshold = entropy_threshold
        self.scale_factor = scale_factor

    def compute_temperature(self, entropy: float, base_temperature: float = 0.7) -> float:
        if entropy <= self.entropy_threshold:
            return base_temperature
        excess = entropy - self.entropy_threshold
        adjustment = -self.scale_factor * (1 - math.exp(-excess))
        return max(0.05, base_temperature + adjustment)

    def should_flag(self, entropy: float) -> bool:
        return entropy > self.entropy_threshold * 1.5


class LEADController:
    """Latent-Discrete switching: toggles between generation modes."""

    def __init__(self, switch_threshold: float = 3.0) -> None:
        self.switch_threshold = switch_threshold
        self._in_latent_mode = False

    def evaluate(self, entropy: float) -> bool:
        """Return True if should switch to latent mode."""
        should_switch = entropy > self.switch_threshold
        self._in_latent_mode = should_switch
        return should_switch

    @property
    def is_latent(self) -> bool:
        return self._in_latent_mode


class EPRController:
    """Entropy Prediction Residual: black-box entropy anomaly detection."""

    def __init__(self, window_size: int = 10, residual_threshold: float = 1.5) -> None:
        self.window_size = window_size
        self.residual_threshold = residual_threshold
        self._history: list[float] = []

    def update(self, entropy: float) -> float:
        """Add entropy observation and return the prediction residual."""
        self._history.append(entropy)
        if len(self._history) < 2:
            return 0.0
        window = self._history[-self.window_size:]
        predicted = sum(window[:-1]) / len(window[:-1])
        residual = abs(entropy - predicted)
        return residual

    def is_anomalous(self, entropy: float) -> bool:
        residual = self.update(entropy)
        return residual > self.residual_threshold

    def reset(self) -> None:
        self._history.clear()


class LEDController:
    """Layer-wise Exploration Depth: analyzes per-layer attention patterns."""

    def __init__(self, num_layers: int = 12, depth_threshold: float = 0.6) -> None:
        self.num_layers = num_layers
        self.depth_threshold = depth_threshold

    def analyze_layers(self, layer_entropies: list[float]) -> tuple[int, float]:
        """Analyze layer entropies and return (exploration_depth, max_layer_entropy)."""
        if not layer_entropies:
            return 0, 0.0
        max_entropy = max(layer_entropies)
        depth = sum(1 for e in layer_entropies if e > self.depth_threshold)
        return depth, max_entropy

    def is_deep_exploration(self, layer_entropies: list[float]) -> bool:
        depth, _ = self.analyze_layers(layer_entropies)
        return depth > self.num_layers // 2


class CKPlugController:
    """CK-PLUG: Chemical-potential retrieval for grounding."""

    def __init__(self, retrieval_threshold: float = 2.5) -> None:
        self.retrieval_threshold = retrieval_threshold
        self._knowledge_base: dict[str, float] = {}

    def register_knowledge(self, key: str, relevance: float = 1.0) -> None:
        self._knowledge_base[key] = relevance

    def should_retrieve(self, entropy: float) -> bool:
        return entropy > self.retrieval_threshold

    def get_grounding(self, query_tokens: list[str]) -> list[str]:
        """Return relevant knowledge keys for grounding."""
        if not self._knowledge_base:
            return []
        return sorted(self._knowledge_base.keys(), key=lambda k: self._knowledge_base[k], reverse=True)[:5]


class LandauGinzburgTracker:
    """Top-level hallucination tracker orchestrating all 5 sub-controllers."""

    def __init__(
        self,
        entropy_threshold: float = 2.0,
        hallucination_threshold: float = 3.0,
    ) -> None:
        self.edt = EDTController(entropy_threshold=entropy_threshold)
        self.lead = LEADController(switch_threshold=hallucination_threshold)
        self.epr = EPRController()
        self.led = LEDController()
        self.ck_plug = CKPlugController(retrieval_threshold=hallucination_threshold)
        self._hallucination_threshold = hallucination_threshold
        self._analyses: list[SequenceAnalysis] = []

    def analyze_token(self, token: str, entropy: float, layer_entropies: list[float] | None = None) -> TokenMetrics:
        """Analyze a single token for hallucination risk."""
        metrics = TokenMetrics(token=token, entropy=entropy)
        flags: list[ControllerType] = []

        if self.edt.should_flag(entropy):
            flags.append(ControllerType.EDT)
        if self.lead.evaluate(entropy):
            flags.append(ControllerType.LEAD)
        if self.epr.is_anomalous(entropy):
            flags.append(ControllerType.EPR)
        if layer_entropies and self.led.is_deep_exploration(layer_entropies):
            flags.append(ControllerType.LED)
            metrics.layer_depth = sum(1 for e in layer_entropies if e > self.led.depth_threshold)
        if self.ck_plug.should_retrieve(entropy):
            flags.append(ControllerType.CK_PLUG)

        metrics.controller_flags = flags
        metrics.is_hallucinated = len(flags) >= 2
        metrics.confidence = max(0.0, 1.0 - (entropy / (self._hallucination_threshold * 2)))

        return metrics

    def analyze_sequence(self, tokens: list[tuple[str, float]]) -> SequenceAnalysis:
        """Analyze a sequence of (token, entropy) pairs."""
        self.epr.reset()
        token_metrics = [self.analyze_token(t, e) for t, e in tokens]

        entropies = [m.entropy for m in token_metrics]
        mean_entropy = sum(entropies) / len(entropies) if entropies else 0.0
        max_entropy = max(entropies) if entropies else 0.0
        hallucination_count = sum(1 for m in token_metrics if m.is_hallucinated)

        if hallucination_count == 0:
            risk = HallucinationRisk.LOW
        elif hallucination_count / len(token_metrics) < 0.1:
            risk = HallucinationRisk.MODERATE
        elif hallucination_count / len(token_metrics) < 0.3:
            risk = HallucinationRisk.HIGH
        else:
            risk = HallucinationRisk.CRITICAL

        analysis = SequenceAnalysis(
            tokens=token_metrics,
            overall_risk=risk,
            mean_entropy=mean_entropy,
            max_entropy=max_entropy,
            hallucination_count=hallucination_count,
        )
        self._analyses.append(analysis)
        return analysis

    @property
    def analysis_count(self) -> int:
        return len(self._analyses)

    @property
    def analyses(self) -> list[SequenceAnalysis]:
        return list(self._analyses)
