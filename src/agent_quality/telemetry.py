from __future__ import annotations

import os
from contextlib import nullcontext
from typing import Any

_configured = False
_tracer: Any = None
_provider: Any = None


def configure_tracing() -> None:
    global _configured, _tracer, _provider
    if _configured:
        return
    _configured = True
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    except ImportError:
        if endpoint:
            raise RuntimeError("OpenTelemetry endpoint is set but observability dependencies are not installed")
        return
    provider = TracerProvider(resource=Resource.create({"service.name": "agent-quality-demo"}))
    if endpoint:
        provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    _provider = provider
    _tracer = trace.get_tracer("agent-quality-demo")


def span(name: str, attributes: dict[str, Any] | None = None) -> Any:
    if _tracer is None:
        return nullcontext(_NoopSpan())
    return _tracer.start_as_current_span(name, attributes=attributes or {})


def force_flush() -> bool:
    return True if _provider is None else bool(_provider.force_flush())


class _NoopSpan:
    def set_attribute(self, name: str, value: Any) -> None:
        return
