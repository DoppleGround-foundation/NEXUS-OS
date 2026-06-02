"""Distributed tracing for Nexus OS governance operations.

Provides span-based tracing with context propagation for tracking
governance decisions, model routing, and agent actions across the system.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SpanStatus(Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_id: str | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    status: SpanStatus = SpanStatus.OK
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def finish(self, status: SpanStatus | None = None) -> None:
        self.end_time = time.time()
        if status is not None:
            self.status = status

    @property
    def is_finished(self) -> bool:
        return self.end_time is not None


class TraceContext:
    """Propagation context for distributed traces."""

    def __init__(self, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex
        self._spans: list[Span] = []
        self._active_span: Span | None = None

    def start_span(self, name: str, parent_id: str | None = None) -> Span:
        if parent_id is None and self._active_span is not None:
            parent_id = self._active_span.span_id
        span = Span(name=name, trace_id=self.trace_id, parent_id=parent_id)
        self._spans.append(span)
        self._active_span = span
        return span

    def finish_span(self, span: Span, status: SpanStatus | None = None) -> None:
        span.finish(status)
        if self._active_span is span:
            parent_spans = [s for s in self._spans if s.span_id == span.parent_id and not s.is_finished]
            self._active_span = parent_spans[0] if parent_spans else None

    @property
    def active_span(self) -> Span | None:
        return self._active_span

    @property
    def spans(self) -> list[Span]:
        return list(self._spans)

    @property
    def is_complete(self) -> bool:
        return all(s.is_finished for s in self._spans)


class Tracer:
    """Top-level tracer that manages trace contexts."""

    def __init__(self, service_name: str = "nexus-os") -> None:
        self.service_name = service_name
        self._traces: dict[str, TraceContext] = {}
        self._export_buffer: list[Span] = []

    def create_trace(self, trace_id: str | None = None) -> TraceContext:
        ctx = TraceContext(trace_id)
        self._traces[ctx.trace_id] = ctx
        return ctx

    def get_trace(self, trace_id: str) -> TraceContext | None:
        return self._traces.get(trace_id)

    def export_completed(self) -> list[Span]:
        """Collect all finished spans for export."""
        completed = []
        for ctx in self._traces.values():
            for span in ctx.spans:
                if span.is_finished and span not in self._export_buffer:
                    completed.append(span)
                    self._export_buffer.append(span)
        return completed

    def flush(self) -> int:
        """Flush export buffer. Returns number of spans flushed."""
        count = len(self._export_buffer)
        self._export_buffer.clear()
        return count

    @property
    def active_traces(self) -> int:
        return sum(1 for ctx in self._traces.values() if not ctx.is_complete)
