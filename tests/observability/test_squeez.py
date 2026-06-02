"""Tests for nexus_os.observability.squeez — Log compression."""

import json

from nexus_os.observability.squeez import (
    CompressedBlock,
    LogEntry,
    PatternExtractor,
    SqueezCompressor,
)


class TestLogEntry:
    def test_creation(self):
        entry = LogEntry(timestamp=1.0, level="INFO", message="hello")
        assert entry.level == "INFO"
        assert entry.message == "hello"

    def test_to_dict(self):
        entry = LogEntry(timestamp=1.0, level="INFO", message="hello", source="gov")
        d = entry.to_dict()
        assert d["ts"] == 1.0
        assert d["level"] == "INFO"
        assert d["msg"] == "hello"
        assert d["src"] == "gov"

    def test_attributes_in_dict(self):
        entry = LogEntry(timestamp=1.0, level="DEBUG", message="x", attributes={"k": "v"})
        d = entry.to_dict()
        assert d["k"] == "v"


class TestPatternExtractor:
    def test_extract_uuid(self):
        extractor = PatternExtractor()
        msg = "Processing request 550e8400-e29b-41d4-a716-446655440000"
        pattern, variables = extractor.extract_pattern(msg)
        assert "<UUID>" in pattern
        assert "550e8400-e29b-41d4-a716-446655440000" in variables.values()

    def test_extract_ip(self):
        extractor = PatternExtractor()
        msg = "Connection from 192.168.1.100 accepted"
        pattern, variables = extractor.extract_pattern(msg)
        assert "<IP>" in pattern

    def test_extract_numbers(self):
        extractor = PatternExtractor()
        msg = "Processed 42 items in batch"
        pattern, variables = extractor.extract_pattern(msg)
        assert "<NUM>" in pattern

    def test_extract_duration(self):
        extractor = PatternExtractor()
        msg = "Request took 123.45ms"
        pattern, variables = extractor.extract_pattern(msg)
        assert "<DURATION>" in pattern

    def test_pattern_hash_deterministic(self):
        extractor = PatternExtractor()
        h1 = extractor.pattern_hash("hello <NUM> world")
        h2 = extractor.pattern_hash("hello <NUM> world")
        assert h1 == h2

    def test_pattern_hash_different(self):
        extractor = PatternExtractor()
        h1 = extractor.pattern_hash("pattern A")
        h2 = extractor.pattern_hash("pattern B")
        assert h1 != h2

    def test_no_variables(self):
        extractor = PatternExtractor()
        msg = "Simple log message"
        pattern, variables = extractor.extract_pattern(msg)
        assert pattern == "Simple log message"
        assert variables == {}


class TestCompressedBlock:
    def test_compression_ratio_single(self):
        block = CompressedBlock(
            pattern_hash="abc", pattern="test", count=1, first_ts=1.0, last_ts=1.0
        )
        assert block.compression_ratio == 1.0

    def test_compression_ratio_multiple(self):
        block = CompressedBlock(
            pattern_hash="abc", pattern="test", count=10, first_ts=1.0, last_ts=2.0
        )
        assert block.compression_ratio == 0.1


class TestSqueezCompressor:
    def test_ingest_single(self):
        compressor = SqueezCompressor()
        entry = LogEntry(timestamp=1.0, level="INFO", message="hello")
        compressor.ingest(entry)
        assert compressor.active_blocks == 1

    def test_ingest_deduplication(self):
        compressor = SqueezCompressor()
        for i in range(5):
            compressor.ingest(LogEntry(timestamp=float(i), level="INFO", message="same message"))
        blocks = compressor.flush()
        assert len(blocks) == 1
        assert blocks[0].count == 5

    def test_different_messages_separate_blocks(self):
        compressor = SqueezCompressor()
        compressor.ingest(LogEntry(timestamp=1.0, level="INFO", message="alpha"))
        compressor.ingest(LogEntry(timestamp=2.0, level="INFO", message="beta"))
        assert compressor.active_blocks == 2

    def test_different_levels_separate_blocks(self):
        compressor = SqueezCompressor()
        compressor.ingest(LogEntry(timestamp=1.0, level="INFO", message="msg"))
        compressor.ingest(LogEntry(timestamp=2.0, level="ERROR", message="msg"))
        assert compressor.active_blocks == 2

    def test_flush_clears_blocks(self):
        compressor = SqueezCompressor()
        compressor.ingest(LogEntry(timestamp=1.0, level="INFO", message="hello"))
        compressor.flush()
        assert compressor.active_blocks == 0

    def test_stats(self):
        compressor = SqueezCompressor()
        for i in range(3):
            compressor.ingest(LogEntry(timestamp=float(i), level="INFO", message="msg"))
        stats = compressor.stats
        assert stats["total_input"] == 3
        assert stats["active_blocks"] == 1

    def test_max_block_age(self):
        compressor = SqueezCompressor(max_block_age=10.0)
        compressor.ingest(LogEntry(timestamp=1.0, level="INFO", message="msg"))
        compressor.ingest(LogEntry(timestamp=5.0, level="INFO", message="msg"))
        compressor.ingest(LogEntry(timestamp=15.0, level="INFO", message="msg"))
        blocks = compressor.flush()
        assert len(blocks) == 2

    def test_serialize_blocks(self):
        compressor = SqueezCompressor()
        compressor.ingest(LogEntry(timestamp=1.0, level="INFO", message="hello"))
        blocks = compressor.flush()
        serialized = compressor.serialize_blocks(blocks)
        parsed = json.loads(serialized)
        assert len(parsed) == 1
        assert parsed[0]["count"] == 1
        assert parsed[0]["pattern"] == "hello"

    def test_variable_dedup(self):
        compressor = SqueezCompressor()
        compressor.ingest(LogEntry(timestamp=1.0, level="INFO", message="Request 100 done"))
        compressor.ingest(LogEntry(timestamp=2.0, level="INFO", message="Request 200 done"))
        blocks = compressor.flush()
        assert len(blocks) == 1
        assert blocks[0].count == 2
        assert len(blocks[0].variable_fields) == 2
