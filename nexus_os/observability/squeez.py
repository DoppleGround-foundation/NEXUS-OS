"""Squeez - Log compression for Nexus OS observability.

Compresses structured log entries using pattern deduplication,
field extraction, and run-length encoding for efficient storage.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LogEntry:
    timestamp: float
    level: str
    message: str
    source: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.timestamp,
            "level": self.level,
            "msg": self.message,
            "src": self.source,
            **self.attributes,
        }


@dataclass
class CompressedBlock:
    pattern_hash: str
    pattern: str
    count: int
    first_ts: float
    last_ts: float
    variable_fields: list[dict[str, Any]] = field(default_factory=list)

    @property
    def compression_ratio(self) -> float:
        if self.count <= 1:
            return 1.0
        return 1.0 / self.count


class PatternExtractor:
    """Extracts common patterns from log messages for deduplication."""

    _VARIABLE_PATTERNS = [
        (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "<UUID>"),
        (re.compile(r"\b\d{10,13}\b"), "<TIMESTAMP>"),
        (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "<IP>"),
        (re.compile(r"\b\d+\.\d+(?:ms|s)\b"), "<DURATION>"),
        (re.compile(r"\b\d+\b"), "<NUM>"),
    ]

    def extract_pattern(self, message: str) -> tuple[str, dict[str, str]]:
        """Extract a normalized pattern and captured variables."""
        variables: dict[str, str] = {}
        pattern = message
        for idx, (regex, placeholder) in enumerate(self._VARIABLE_PATTERNS):
            matches = regex.findall(pattern)
            for i, match in enumerate(matches):
                var_key = f"v{idx}_{i}"
                variables[var_key] = match
            pattern = regex.sub(placeholder, pattern)
        return pattern, variables

    def pattern_hash(self, pattern: str) -> str:
        return hashlib.md5(pattern.encode()).hexdigest()[:12]


class SqueezCompressor:
    """Run-length compression for structured log streams."""

    def __init__(self, max_block_age: float = 60.0) -> None:
        self._extractor = PatternExtractor()
        self._blocks: dict[str, CompressedBlock] = {}
        self._completed: list[CompressedBlock] = []
        self._max_block_age = max_block_age
        self._total_input = 0
        self._total_compressed = 0

    def ingest(self, entry: LogEntry) -> None:
        self._total_input += 1
        pattern, variables = self._extractor.extract_pattern(entry.message)
        phash = self._extractor.pattern_hash(pattern)
        key = f"{entry.level}:{entry.source}:{phash}"

        if key in self._blocks:
            block = self._blocks[key]
            if entry.timestamp - block.first_ts > self._max_block_age:
                self._completed.append(block)
                self._blocks[key] = CompressedBlock(
                    pattern_hash=phash,
                    pattern=pattern,
                    count=1,
                    first_ts=entry.timestamp,
                    last_ts=entry.timestamp,
                    variable_fields=[variables] if variables else [],
                )
            else:
                block.count += 1
                block.last_ts = entry.timestamp
                if variables:
                    block.variable_fields.append(variables)
        else:
            self._blocks[key] = CompressedBlock(
                pattern_hash=phash,
                pattern=pattern,
                count=1,
                first_ts=entry.timestamp,
                last_ts=entry.timestamp,
                variable_fields=[variables] if variables else [],
            )

    def flush(self) -> list[CompressedBlock]:
        """Flush all blocks (active + completed) and return them."""
        result = list(self._completed)
        result.extend(self._blocks.values())
        self._total_compressed += len(result)
        self._completed.clear()
        self._blocks.clear()
        return result

    @property
    def active_blocks(self) -> int:
        return len(self._blocks)

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_input": self._total_input,
            "total_compressed_blocks": self._total_compressed,
            "active_blocks": self.active_blocks,
            "pending_completed": len(self._completed),
        }

    def serialize_blocks(self, blocks: list[CompressedBlock]) -> str:
        return json.dumps([{
            "hash": b.pattern_hash,
            "pattern": b.pattern,
            "count": b.count,
            "first_ts": b.first_ts,
            "last_ts": b.last_ts,
            "vars": b.variable_fields,
        } for b in blocks])
