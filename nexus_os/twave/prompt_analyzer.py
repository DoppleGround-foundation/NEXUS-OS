"""PromptAnalyzer - Complexity, safety, and code detection for TWAVE routing.

Analyzes prompts to determine complexity level, safety classification,
and whether code generation is likely needed. Used by ChimeraRouterV2
for tiered model selection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ComplexityLevel(Enum):
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EXPERT = "expert"


class SafetyClass(Enum):
    SAFE = "safe"
    CAUTION = "caution"
    RESTRICTED = "restricted"
    BLOCKED = "blocked"


@dataclass
class PromptAnalysis:
    complexity: ComplexityLevel
    safety: SafetyClass
    requires_code: bool
    estimated_tokens: int
    topics: list[str]
    confidence: float = 1.0


_CODE_INDICATORS = [
    re.compile(r"\b(write|create|implement|code|function|class|def |import |from )\b", re.IGNORECASE),
    re.compile(r"\b(python|javascript|typescript|rust|java|sql|html|css)\b", re.IGNORECASE),
    re.compile(r"```"),
    re.compile(r"\b(debug|fix|refactor|optimize|test)\b", re.IGNORECASE),
    re.compile(r"\b(API|endpoint|route|handler|middleware)\b", re.IGNORECASE),
]

_SAFETY_BLOCKLIST = [
    re.compile(r"\b(hack|exploit|vulnerability|attack|inject|bypass)\b", re.IGNORECASE),
    re.compile(r"\b(malware|virus|trojan|ransomware|keylogger)\b", re.IGNORECASE),
    re.compile(r"\b(weapon|explosive|poison|drug synthesis)\b", re.IGNORECASE),
]

_SAFETY_CAUTION = [
    re.compile(r"\b(security|penetration test|pentest|audit)\b", re.IGNORECASE),
    re.compile(r"\b(encryption|decrypt|password|credential)\b", re.IGNORECASE),
]

_COMPLEXITY_EXPERT = [
    re.compile(r"\b(quantum|neural network|transformer|diffusion|reinforcement learning)\b", re.IGNORECASE),
    re.compile(r"\b(distributed system|consensus|Byzantine|Paxos|Raft)\b", re.IGNORECASE),
    re.compile(r"\b(compiler|parser|AST|formal verification|proof)\b", re.IGNORECASE),
]

_COMPLEXITY_MODERATE = [
    re.compile(r"\b(algorithm|data structure|concurrency|async|threading)\b", re.IGNORECASE),
    re.compile(r"\b(database|schema|migration|query optimization)\b", re.IGNORECASE),
    re.compile(r"\b(architecture|design pattern|microservice)\b", re.IGNORECASE),
]


class PromptAnalyzer:
    """Analyzes prompts for routing decisions in ChimeraRouterV2."""

    def analyze(self, prompt: str) -> PromptAnalysis:
        complexity = self._assess_complexity(prompt)
        safety = self._assess_safety(prompt)
        requires_code = self._detect_code_need(prompt)
        estimated_tokens = self._estimate_tokens(prompt, complexity)
        topics = self._extract_topics(prompt)

        return PromptAnalysis(
            complexity=complexity,
            safety=safety,
            requires_code=requires_code,
            estimated_tokens=estimated_tokens,
            topics=topics,
        )

    def _assess_complexity(self, prompt: str) -> ComplexityLevel:
        word_count = len(prompt.split())
        expert_hits = sum(1 for p in _COMPLEXITY_EXPERT if p.search(prompt))
        moderate_hits = sum(1 for p in _COMPLEXITY_MODERATE if p.search(prompt))

        if expert_hits >= 2 or (expert_hits >= 1 and word_count > 100):
            return ComplexityLevel.EXPERT
        if expert_hits >= 1 or moderate_hits >= 2:
            return ComplexityLevel.COMPLEX
        if moderate_hits >= 1 or word_count > 50:
            return ComplexityLevel.MODERATE
        if word_count > 15:
            return ComplexityLevel.SIMPLE
        return ComplexityLevel.TRIVIAL

    def _assess_safety(self, prompt: str) -> SafetyClass:
        block_hits = sum(1 for p in _SAFETY_BLOCKLIST if p.search(prompt))
        caution_hits = sum(1 for p in _SAFETY_CAUTION if p.search(prompt))

        if block_hits >= 2:
            return SafetyClass.BLOCKED
        if block_hits >= 1:
            return SafetyClass.RESTRICTED
        if caution_hits >= 1:
            return SafetyClass.CAUTION
        return SafetyClass.SAFE

    def _detect_code_need(self, prompt: str) -> bool:
        hits = sum(1 for p in _CODE_INDICATORS if p.search(prompt))
        return hits >= 2

    def _estimate_tokens(self, prompt: str, complexity: ComplexityLevel) -> int:
        base = len(prompt.split()) * 4
        multipliers = {
            ComplexityLevel.TRIVIAL: 2,
            ComplexityLevel.SIMPLE: 3,
            ComplexityLevel.MODERATE: 5,
            ComplexityLevel.COMPLEX: 8,
            ComplexityLevel.EXPERT: 12,
        }
        return base * multipliers.get(complexity, 4)

    def _extract_topics(self, prompt: str) -> list[str]:
        topics = []
        topic_patterns = {
            "code": re.compile(r"\b(code|programming|function|class|script)\b", re.IGNORECASE),
            "math": re.compile(r"\b(math|calculate|equation|formula|algebra)\b", re.IGNORECASE),
            "science": re.compile(r"\b(physics|chemistry|biology|quantum|molecule)\b", re.IGNORECASE),
            "security": re.compile(r"\b(security|encryption|auth|permission|access)\b", re.IGNORECASE),
            "data": re.compile(r"\b(data|database|query|schema|table)\b", re.IGNORECASE),
            "ai": re.compile(r"\b(AI|machine learning|model|neural|training)\b", re.IGNORECASE),
        }
        for topic, pattern in topic_patterns.items():
            if pattern.search(prompt):
                topics.append(topic)
        return topics
