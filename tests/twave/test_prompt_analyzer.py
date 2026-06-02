"""Tests for nexus_os.twave.prompt_analyzer — Prompt analysis for routing."""

from nexus_os.twave.prompt_analyzer import (
    ComplexityLevel,
    PromptAnalysis,
    PromptAnalyzer,
    SafetyClass,
)


class TestPromptAnalyzer:
    def setup_method(self):
        self.analyzer = PromptAnalyzer()

    def test_trivial_prompt(self):
        result = self.analyzer.analyze("Hello there")
        assert result.complexity == ComplexityLevel.TRIVIAL
        assert result.safety == SafetyClass.SAFE

    def test_simple_prompt(self):
        result = self.analyzer.analyze(
            "Can you explain how lists work in Python programming language "
            "and give me some clear practical examples for beginners?"
        )
        assert result.complexity in (ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE)

    def test_moderate_prompt(self):
        result = self.analyzer.analyze(
            "Explain the algorithm for concurrent database query optimization "
            "using data structures for efficient indexing"
        )
        assert result.complexity in (ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX)

    def test_complex_prompt(self):
        result = self.analyzer.analyze(
            "Design a distributed system using Paxos consensus algorithm "
            "with formal verification for Byzantine fault tolerance"
        )
        assert result.complexity in (ComplexityLevel.COMPLEX, ComplexityLevel.EXPERT)

    def test_expert_prompt(self):
        result = self.analyzer.analyze(
            "Implement a quantum neural network transformer with reinforcement learning "
            "using distributed system consensus with formal verification proof compiler"
        )
        assert result.complexity == ComplexityLevel.EXPERT

    def test_safe_prompt(self):
        result = self.analyzer.analyze("What is the weather today?")
        assert result.safety == SafetyClass.SAFE

    def test_caution_prompt(self):
        result = self.analyzer.analyze("How do I set up encryption for my password store?")
        assert result.safety == SafetyClass.CAUTION

    def test_restricted_prompt(self):
        result = self.analyzer.analyze("How do I exploit this vulnerability to hack a system?")
        assert result.safety in (SafetyClass.RESTRICTED, SafetyClass.BLOCKED)

    def test_blocked_prompt(self):
        result = self.analyzer.analyze("Create malware that exploits a vulnerability and attacks the system")
        assert result.safety == SafetyClass.BLOCKED

    def test_code_detection_positive(self):
        result = self.analyzer.analyze("Write a Python function to implement a sorting class")
        assert result.requires_code is True

    def test_code_detection_negative(self):
        result = self.analyzer.analyze("Tell me about the history of Rome")
        assert result.requires_code is False

    def test_token_estimation_scales_with_complexity(self):
        trivial = self.analyzer.analyze("Hi")
        expert = self.analyzer.analyze(
            "Implement a quantum neural network with transformer architecture "
            "using reinforcement learning and distributed system consensus"
        )
        assert expert.estimated_tokens > trivial.estimated_tokens

    def test_topic_extraction_code(self):
        result = self.analyzer.analyze("Write a Python function for data processing")
        assert "code" in result.topics

    def test_topic_extraction_security(self):
        result = self.analyzer.analyze("Set up encryption and auth for secure access")
        assert "security" in result.topics

    def test_topic_extraction_data(self):
        result = self.analyzer.analyze("Optimize the database query and schema design")
        assert "data" in result.topics

    def test_topic_extraction_ai(self):
        result = self.analyzer.analyze("Train a machine learning model with neural networks")
        assert "ai" in result.topics

    def test_topic_extraction_multiple(self):
        result = self.analyzer.analyze(
            "Build a machine learning model that queries a database for security analysis"
        )
        assert len(result.topics) >= 2

    def test_result_has_confidence(self):
        result = self.analyzer.analyze("Hello")
        assert isinstance(result, PromptAnalysis)
        assert result.confidence == 1.0

    def test_empty_prompt(self):
        result = self.analyzer.analyze("")
        assert result.complexity == ComplexityLevel.TRIVIAL
        assert result.safety == SafetyClass.SAFE
        assert result.requires_code is False
