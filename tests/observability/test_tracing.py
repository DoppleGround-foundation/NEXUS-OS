"""Tests for nexus_os.observability.tracing — Distributed tracing."""

from nexus_os.observability.tracing import Span, SpanStatus, TraceContext, Tracer


class TestSpan:
    def test_creation(self):
        span = Span(name="test-op", trace_id="t1")
        assert span.name == "test-op"
        assert span.trace_id == "t1"
        assert span.parent_id is None
        assert span.status == SpanStatus.OK
        assert not span.is_finished

    def test_duration_before_finish(self):
        span = Span(name="op", trace_id="t1")
        assert span.duration_ms is None

    def test_finish_sets_end_time(self):
        span = Span(name="op", trace_id="t1")
        span.finish()
        assert span.is_finished
        assert span.end_time is not None
        assert span.duration_ms is not None
        assert span.duration_ms >= 0

    def test_finish_with_status(self):
        span = Span(name="op", trace_id="t1")
        span.finish(SpanStatus.ERROR)
        assert span.status == SpanStatus.ERROR

    def test_set_attribute(self):
        span = Span(name="op", trace_id="t1")
        span.set_attribute("agent_id", "a1")
        assert span.attributes["agent_id"] == "a1"

    def test_add_event(self):
        span = Span(name="op", trace_id="t1")
        span.add_event("checkpoint", {"step": 1})
        assert len(span.events) == 1
        assert span.events[0]["name"] == "checkpoint"
        assert span.events[0]["attributes"]["step"] == 1

    def test_multiple_events(self):
        span = Span(name="op", trace_id="t1")
        span.add_event("start")
        span.add_event("end")
        assert len(span.events) == 2


class TestTraceContext:
    def test_create_with_auto_id(self):
        ctx = TraceContext()
        assert len(ctx.trace_id) == 32

    def test_create_with_explicit_id(self):
        ctx = TraceContext(trace_id="my-trace")
        assert ctx.trace_id == "my-trace"

    def test_start_span(self):
        ctx = TraceContext()
        span = ctx.start_span("root")
        assert span.name == "root"
        assert span.trace_id == ctx.trace_id
        assert span.parent_id is None
        assert ctx.active_span is span

    def test_nested_spans(self):
        ctx = TraceContext()
        root = ctx.start_span("root")
        child = ctx.start_span("child")
        assert child.parent_id == root.span_id
        assert ctx.active_span is child

    def test_finish_span_restores_parent(self):
        ctx = TraceContext()
        root = ctx.start_span("root")
        child = ctx.start_span("child")
        ctx.finish_span(child)
        assert ctx.active_span is root

    def test_is_complete(self):
        ctx = TraceContext()
        s1 = ctx.start_span("op1")
        s2 = ctx.start_span("op2")
        assert not ctx.is_complete
        ctx.finish_span(s2)
        assert not ctx.is_complete
        ctx.finish_span(s1)
        assert ctx.is_complete

    def test_spans_list(self):
        ctx = TraceContext()
        ctx.start_span("a")
        ctx.start_span("b")
        assert len(ctx.spans) == 2


class TestTracer:
    def test_create_trace(self):
        tracer = Tracer()
        ctx = tracer.create_trace()
        assert tracer.get_trace(ctx.trace_id) is ctx

    def test_service_name(self):
        tracer = Tracer(service_name="governor")
        assert tracer.service_name == "governor"

    def test_get_nonexistent_trace(self):
        tracer = Tracer()
        assert tracer.get_trace("missing") is None

    def test_export_completed(self):
        tracer = Tracer()
        ctx = tracer.create_trace()
        span = ctx.start_span("op")
        assert tracer.export_completed() == []
        ctx.finish_span(span)
        exported = tracer.export_completed()
        assert len(exported) == 1
        assert exported[0] is span

    def test_export_idempotent(self):
        tracer = Tracer()
        ctx = tracer.create_trace()
        span = ctx.start_span("op")
        ctx.finish_span(span)
        tracer.export_completed()
        assert tracer.export_completed() == []

    def test_flush(self):
        tracer = Tracer()
        ctx = tracer.create_trace()
        span = ctx.start_span("op")
        ctx.finish_span(span)
        tracer.export_completed()
        count = tracer.flush()
        assert count == 1

    def test_active_traces(self):
        tracer = Tracer()
        ctx = tracer.create_trace()
        span = ctx.start_span("op")
        assert tracer.active_traces == 1
        ctx.finish_span(span)
        assert tracer.active_traces == 0

    def test_multiple_traces(self):
        tracer = Tracer()
        ctx1 = tracer.create_trace()
        ctx2 = tracer.create_trace()
        s1 = ctx1.start_span("op1")
        s2 = ctx2.start_span("op2")
        ctx1.finish_span(s1)
        assert tracer.active_traces == 1
        ctx2.finish_span(s2)
        assert tracer.active_traces == 0
