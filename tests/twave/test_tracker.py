"""Tests for nexus_os.twave.tracker — Landau-Ginzburg hallucination tracker."""

import pytest

from nexus_os.twave.tracker import (
    CKPlugController,
    ControllerType,
    EDTController,
    EPRController,
    HallucinationRisk,
    LandauGinzburgTracker,
    LEADController,
    LEDController,
    SequenceAnalysis,
    TokenMetrics,
)


class TestEDTController:
    def test_below_threshold(self):
        edt = EDTController(entropy_threshold=2.0)
        t = edt.compute_temperature(1.5, base_temperature=0.7)
        assert t == 0.7

    def test_above_threshold_lowers_temperature(self):
        edt = EDTController(entropy_threshold=2.0, scale_factor=0.5)
        t = edt.compute_temperature(4.0, base_temperature=0.7)
        assert t < 0.7
        assert t >= 0.05

    def test_very_high_entropy_clamps(self):
        edt = EDTController(entropy_threshold=1.0, scale_factor=2.0)
        t = edt.compute_temperature(10.0, base_temperature=0.7)
        assert t == pytest.approx(0.05, abs=0.01)

    def test_should_flag_below(self):
        edt = EDTController(entropy_threshold=2.0)
        assert edt.should_flag(2.5) is False

    def test_should_flag_above(self):
        edt = EDTController(entropy_threshold=2.0)
        assert edt.should_flag(3.5) is True


class TestLEADController:
    def test_below_threshold(self):
        lead = LEADController(switch_threshold=3.0)
        assert lead.evaluate(2.0) is False
        assert lead.is_latent is False

    def test_above_threshold(self):
        lead = LEADController(switch_threshold=3.0)
        assert lead.evaluate(4.0) is True
        assert lead.is_latent is True

    def test_toggle(self):
        lead = LEADController(switch_threshold=3.0)
        lead.evaluate(4.0)
        assert lead.is_latent is True
        lead.evaluate(1.0)
        assert lead.is_latent is False


class TestEPRController:
    def test_first_observation(self):
        epr = EPRController()
        residual = epr.update(1.0)
        assert residual == 0.0

    def test_stable_sequence(self):
        epr = EPRController(residual_threshold=1.5)
        for _ in range(5):
            epr.update(1.0)
        assert not epr.is_anomalous(1.1)

    def test_anomalous_spike(self):
        epr = EPRController(residual_threshold=1.0)
        for _ in range(5):
            epr.update(1.0)
        assert epr.is_anomalous(5.0)

    def test_reset(self):
        epr = EPRController()
        epr.update(1.0)
        epr.update(2.0)
        epr.reset()
        assert epr.update(1.0) == 0.0

    def test_window_size(self):
        epr = EPRController(window_size=3)
        for v in [1.0, 1.0, 1.0, 1.0, 1.0]:
            epr.update(v)
        assert len(epr._history) == 5


class TestLEDController:
    def test_empty_layers(self):
        led = LEDController()
        depth, max_e = led.analyze_layers([])
        assert depth == 0
        assert max_e == 0.0

    def test_no_deep_exploration(self):
        led = LEDController(num_layers=12, depth_threshold=0.6)
        layers = [0.1] * 12
        assert led.is_deep_exploration(layers) is False

    def test_deep_exploration(self):
        led = LEDController(num_layers=12, depth_threshold=0.6)
        layers = [0.8] * 12
        assert led.is_deep_exploration(layers) is True

    def test_partial_exploration(self):
        led = LEDController(num_layers=12, depth_threshold=0.6)
        layers = [0.8] * 5 + [0.1] * 7
        depth, _ = led.analyze_layers(layers)
        assert depth == 5

    def test_max_layer_entropy(self):
        led = LEDController()
        _, max_e = led.analyze_layers([0.1, 0.5, 0.9, 0.3])
        assert max_e == 0.9


class TestCKPlugController:
    def test_should_retrieve_below(self):
        ck = CKPlugController(retrieval_threshold=2.5)
        assert ck.should_retrieve(2.0) is False

    def test_should_retrieve_above(self):
        ck = CKPlugController(retrieval_threshold=2.5)
        assert ck.should_retrieve(3.0) is True

    def test_empty_knowledge(self):
        ck = CKPlugController()
        assert ck.get_grounding(["test"]) == []

    def test_register_and_retrieve(self):
        ck = CKPlugController()
        ck.register_knowledge("fact_1", relevance=0.9)
        ck.register_knowledge("fact_2", relevance=0.5)
        ck.register_knowledge("fact_3", relevance=0.8)
        results = ck.get_grounding(["query"])
        assert results[0] == "fact_1"
        assert len(results) == 3

    def test_retrieve_max_5(self):
        ck = CKPlugController()
        for i in range(10):
            ck.register_knowledge(f"fact_{i}", relevance=float(i))
        results = ck.get_grounding(["query"])
        assert len(results) == 5


class TestTokenMetrics:
    def test_defaults(self):
        m = TokenMetrics(token="hello")
        assert m.entropy == 0.0
        assert m.confidence == 1.0
        assert m.is_hallucinated is False
        assert m.controller_flags == []


class TestSequenceAnalysis:
    def test_empty(self):
        sa = SequenceAnalysis(tokens=[])
        assert sa.hallucination_rate == 0.0
        assert sa.token_count == 0

    def test_with_tokens(self):
        tokens = [
            TokenMetrics(token="a", is_hallucinated=True),
            TokenMetrics(token="b", is_hallucinated=False),
            TokenMetrics(token="c", is_hallucinated=True),
        ]
        sa = SequenceAnalysis(tokens=tokens, hallucination_count=2)
        assert sa.hallucination_rate == pytest.approx(2 / 3)
        assert sa.token_count == 3


class TestLandauGinzburgTracker:
    def test_analyze_low_entropy_token(self):
        tracker = LandauGinzburgTracker(entropy_threshold=2.0)
        metrics = tracker.analyze_token("hello", entropy=0.5)
        assert metrics.is_hallucinated is False
        assert len(metrics.controller_flags) == 0

    def test_analyze_high_entropy_token(self):
        tracker = LandauGinzburgTracker(entropy_threshold=1.0, hallucination_threshold=1.5)
        metrics = tracker.analyze_token("asdf", entropy=5.0)
        assert metrics.is_hallucinated is True
        assert len(metrics.controller_flags) >= 2

    def test_analyze_with_layer_entropies(self):
        tracker = LandauGinzburgTracker()
        layers = [0.8] * 12
        metrics = tracker.analyze_token("test", entropy=4.0, layer_entropies=layers)
        assert ControllerType.LED in metrics.controller_flags

    def test_analyze_sequence_low_risk(self):
        tracker = LandauGinzburgTracker(entropy_threshold=2.0)
        tokens = [("hello", 0.5), ("world", 0.3), ("test", 0.4)]
        analysis = tracker.analyze_sequence(tokens)
        assert analysis.overall_risk == HallucinationRisk.LOW
        assert analysis.hallucination_count == 0

    def test_analyze_sequence_high_risk(self):
        tracker = LandauGinzburgTracker(entropy_threshold=0.5, hallucination_threshold=0.8)
        tokens = [(f"tok{i}", 3.0 + i) for i in range(10)]
        analysis = tracker.analyze_sequence(tokens)
        assert analysis.overall_risk in (HallucinationRisk.HIGH, HallucinationRisk.CRITICAL)
        assert analysis.hallucination_count > 0

    def test_analyze_sequence_stats(self):
        tracker = LandauGinzburgTracker()
        tokens = [("a", 1.0), ("b", 2.0), ("c", 3.0)]
        analysis = tracker.analyze_sequence(tokens)
        assert analysis.mean_entropy == pytest.approx(2.0)
        assert analysis.max_entropy == 3.0
        assert analysis.token_count == 3

    def test_analysis_count(self):
        tracker = LandauGinzburgTracker()
        tracker.analyze_sequence([("a", 1.0)])
        tracker.analyze_sequence([("b", 2.0)])
        assert tracker.analysis_count == 2
        assert len(tracker.analyses) == 2

    def test_confidence_decreases_with_entropy(self):
        tracker = LandauGinzburgTracker(hallucination_threshold=3.0)
        low = tracker.analyze_token("a", entropy=0.5)
        high = tracker.analyze_token("b", entropy=5.0)
        assert low.confidence > high.confidence

    def test_epr_detects_spike_in_sequence(self):
        tracker = LandauGinzburgTracker(entropy_threshold=2.0, hallucination_threshold=3.0)
        tokens = [("a", 1.0)] * 8 + [("spike", 8.0)]
        analysis = tracker.analyze_sequence(tokens)
        spike_token = analysis.tokens[-1]
        assert spike_token.is_hallucinated is True
