"""
Hermes Doctor — LangChain-style Callback Handler System
========================================================
Inspired by LangChain's BaseCallbackHandler pattern (139K⭐).

Provides plug-and-play step-by-step agent monitoring:
- OnChainStart / OnChainEnd / OnChainError for any agent step
- OnLLMStart / OnLLMEnd / OnLLMError for LLM calls
- OnToolStart / OnToolEnd / OnToolError for tool invocations
- Parent-child relationship tracking
- Real-time event streaming
- Thread-safe context propagation

Brand: AtomCollide-智械工坊
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    CHAIN_START = "chain_start"
    CHAIN_END = "chain_end"
    CHAIN_ERROR = "chain_error"
    LLM_START = "llm_start"
    LLM_END = "llm_end"
    LLM_ERROR = "llm_error"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    TOOL_ERROR = "tool_error"
    RETRIEVER_START = "retriever_start"
    RETRIEVER_END = "retriever_end"
    RETRIEVER_ERROR = "retriever_error"


@dataclass
class StepEvent:
    """A single callback event emitted during agent execution."""
    event_type: EventType
    name: str
    run_id: str
    parent_run_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        d["timestamp"] = self.timestamp.isoformat()
        return d


class BaseCallbackHandler(ABC):
    """Abstract base class for callback handlers.

    Users subclass this to implement custom monitoring, logging,
    metrics collection, or real-time alerting during agent execution.

    Usage:
        class MyHandler(BaseCallbackHandler):
            def on_chain_start(self, event: StepEvent):
                print(f"Chain started: {event.name}")

        handler = MyHandler()
        with chain_context(handler, "my_chain") as ctx:
            with step_context(ctx, "sub_step") as span:
                # do work
                span.set_output({"result": "ok"})
    """

    @abstractmethod
    def on_chain_start(self, event: StepEvent) -> None: ...

    @abstractmethod
    def on_chain_end(self, event: StepEvent) -> None: ...

    @abstractmethod
    def on_chain_error(self, event: StepEvent) -> None: ...

    @abstractmethod
    def on_llm_start(self, event: StepEvent) -> None: ...

    @abstractmethod
    def on_llm_end(self, event: StepEvent) -> None: ...

    @abstractmethod
    def on_llm_error(self, event: StepEvent) -> None: ...

    @abstractmethod
    def on_tool_start(self, event: StepEvent) -> None: ...

    @abstractmethod
    def on_tool_end(self, event: StepEvent) -> None: ...

    @abstractmethod
    def on_tool_error(self, event: StepEvent) -> None: ...


class CollectingHandler(BaseCallbackHandler):
    """Default handler that collects all events into a list.

    Useful for:
    - Post-execution analysis
    - JSON export / trace visualization
    - Testing and debugging
    """

    def __init__(self) -> None:
        self.events: list[StepEvent] = []
        self._lock = threading.Lock()

    def _record(self, event: StepEvent) -> None:
        with self._lock:
            self.events.append(event)

    def on_chain_start(self, event: StepEvent) -> None:
        self._record(event)

    def on_chain_end(self, event: StepEvent) -> None:
        self._record(event)

    def on_chain_error(self, event: StepEvent) -> None:
        self._record(event)

    def on_llm_start(self, event: StepEvent) -> None:
        self._record(event)

    def on_llm_end(self, event: StepEvent) -> None:
        self._record(event)

    def on_llm_error(self, event: StepEvent) -> None:
        self._record(event)

    def on_tool_start(self, event: StepEvent) -> None:
        self._record(event)

    def on_tool_end(self, event: StepEvent) -> None:
        self._record(event)

    def on_tool_error(self, event: StepEvent) -> None:
        self._record(event)

    def get_trace_json(self) -> str:
        """Export all collected events as JSON."""
        return json.dumps(
            [e.to_dict() for e in self.events],
            ensure_ascii=False, indent=2
        )

    def summary(self) -> dict:
        """Return aggregated summary of collected events."""
        by_type: dict[str, int] = {}
        errors: list[str] = []
        total_duration = 0.0
        for e in self.events:
            key = e.event_type.value
            by_type[key] = by_type.get(key, 0) + 1
            total_duration += e.duration_ms
            if e.error:
                errors.append(f"[{key}] {e.name}: {e.error}")
        return {
            "total_events": len(self.events),
            "by_type": by_type,
            "total_duration_ms": round(total_duration, 1),
            "errors": errors,
        }


class PrintingHandler(BaseCallbackHandler):
    """Handler that prints events to stderr for real-time monitoring."""

    def __init__(self, prefix: str = "[HermesDoctor]") -> None:
        self.prefix = prefix

    def _emit(self, event_type: str, event: StepEvent) -> None:
        tag = f"{self.prefix} {event_type}"
        extra = ""
        if event.duration_ms > 0:
            extra = f" ({event.duration_ms:.0f}ms)"
        if event.error:
            print(f"{tag} ❌ {event.name}{extra}: {event.error}", flush=True)
        else:
            print(f"{tag} ✅ {event.name}{extra}", flush=True)

    def on_chain_start(self, event: StepEvent) -> None:
        self._emit("CHAIN_START", event)

    def on_chain_end(self, event: StepEvent) -> None:
        self._emit("CHAIN_END", event)

    def on_chain_error(self, event: StepEvent) -> None:
        self._emit("CHAIN_ERROR", event)

    def on_llm_start(self, event: StepEvent) -> None:
        self._emit("LLM_START", event)

    def on_llm_end(self, event: StepEvent) -> None:
        self._emit("LLM_END", event)

    def on_llm_error(self, event: StepEvent) -> None:
        self._emit("LLM_ERROR", event)

    def on_tool_start(self, event: StepEvent) -> None:
        self._emit("TOOL_START", event)

    def on_tool_end(self, event: StepEvent) -> None:
        self._emit("TOOL_END", event)

    def on_tool_error(self, event: StepEvent) -> None:
        self._emit("TOOL_ERROR", event)


# ──── Context propagation (thread-local) ────

_local = threading.local()


def _get_handlers() -> list[BaseCallbackHandler]:
    return getattr(_local, "handlers", [])


def _get_parent_run_id() -> Optional[str]:
    return getattr(_local, "parent_run_id", None)


def _set_parent_run_id(run_id: Optional[str]) -> None:
    _local.parent_run_id = run_id


@dataclass
class _StepTracker:
    """Internal tracker for an in-flight step."""
    run_id: str
    name: str
    event_type: EventType
    start_time: float
    inputs: dict
    parent_run_id: Optional[str] = None
    outputs: dict = field(default_factory=dict)
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def set_output(self, outputs: dict) -> None:
        self.outputs = outputs

    def set_error(self, error: str) -> None:
        self.error = error

    def set_metadata(self, metadata: dict) -> None:
        self.metadata = metadata


@contextmanager
def callback_context(handlers: list[BaseCallbackHandler]):
    """Set up callback handlers for the current thread.

    Usage:
        with callback_context([PrintingHandler(), CollectingHandler()]):
            # all step_context calls inside will notify these handlers
            ...
    """
    old_handlers = getattr(_local, "handlers", [])
    old_parent = getattr(_local, "parent_run_id", None)
    _local.handlers = handlers
    _local.parent_run_id = None
    try:
        yield
    finally:
        _local.handlers = old_handlers
        _local.parent_run_id = old_parent


@contextmanager
def chain_context(handlers: list[BaseCallbackHandler], name: str,
                  inputs: dict = None, metadata: dict = None):
    """Context manager for a top-level chain execution.

    Usage:
        with chain_context([handler], "diagnosis_chain", {"target": "."}) as tracker:
            with step_context(handler, "check", "tool", inputs={...}) as step:
                result = do_check()
                step.set_output(result)
    """
    run_id = str(uuid.uuid4())[:8]
    start = time.monotonic()
    tracker = _StepTracker(
        run_id=run_id, name=name, event_type=EventType.CHAIN_START,
        start_time=start, inputs=inputs or {}, metadata=metadata or {},
    )
    event = StepEvent(
        event_type=EventType.CHAIN_START, name=name, run_id=run_id,
        inputs=tracker.inputs, metadata=tracker.metadata,
    )
    for h in handlers:
        h.on_chain_start(event)

    old_handlers = getattr(_local, "handlers", [])
    old_parent = getattr(_local, "parent_run_id", None)
    _local.handlers = handlers
    _local.parent_run_id = run_id

    try:
        yield tracker
        duration = (time.monotonic() - start) * 1000
        end_event = StepEvent(
            event_type=EventType.CHAIN_END, name=name, run_id=run_id,
            outputs=tracker.outputs, metadata=tracker.metadata,
            duration_ms=round(duration, 1),
        )
        for h in handlers:
            h.on_chain_end(end_event)
    except Exception as exc:
        duration = (time.monotonic() - start) * 1000
        err_event = StepEvent(
            event_type=EventType.CHAIN_ERROR, name=name, run_id=run_id,
            error=str(exc), metadata=tracker.metadata,
            duration_ms=round(duration, 1),
        )
        for h in handlers:
            h.on_chain_error(err_event)
        raise
    finally:
        _local.handlers = old_handlers
        _local.parent_run_id = old_parent


@contextmanager
def step_context(handlers: list[BaseCallbackHandler], name: str,
                 step_type: str = "chain", inputs: dict = None,
                 metadata: dict = None):
    """Context manager for a single step (chain/llm/tool/retriever).

    Args:
        handlers: List of callback handlers to notify.
        name: Human-readable step name.
        step_type: One of "chain", "llm", "tool", "retriever".
        inputs: Input data for this step.
        metadata: Additional metadata.

    Yields:
        _StepTracker that can be used to set outputs/errors.
    """
    run_id = str(uuid.uuid4())[:8]
    parent_run_id = _get_parent_run_id()
    start = time.monotonic()

    type_map = {
        "chain": (EventType.CHAIN_START, EventType.CHAIN_END, EventType.CHAIN_ERROR),
        "llm": (EventType.LLM_START, EventType.LLM_END, EventType.LLM_ERROR),
        "tool": (EventType.TOOL_START, EventType.TOOL_END, EventType.TOOL_ERROR),
        "retriever": (EventType.RETRIEVER_START, EventType.RETRIEVER_END, EventType.RETRIEVER_ERROR),
    }
    start_type, end_type, err_type = type_map.get(step_type, type_map["chain"])

    tracker = _StepTracker(
        run_id=run_id, name=name, event_type=start_type,
        start_time=start, inputs=inputs or {},
        parent_run_id=parent_run_id, metadata=metadata or {},
    )
    start_event = StepEvent(
        event_type=start_type, name=name, run_id=run_id,
        parent_run_id=parent_run_id, inputs=tracker.inputs,
        metadata=tracker.metadata,
    )
    dispatch = {
        EventType.CHAIN_START: "on_chain_start",
        EventType.LLM_START: "on_llm_start",
        EventType.TOOL_START: "on_tool_start",
        EventType.RETRIEVER_START: "on_retriever_start",
    }
    for h in handlers:
        getattr(h, dispatch[start_type])(start_event)

    old_parent = _local.parent_run_id
    _local.parent_run_id = run_id

    try:
        yield tracker
        duration = (time.monotonic() - start) * 1000
        end_event = StepEvent(
            event_type=end_type, name=name, run_id=run_id,
            parent_run_id=parent_run_id,
            outputs=tracker.outputs, metadata=tracker.metadata,
            duration_ms=round(duration, 1),
        )
        end_dispatch = {
            EventType.CHAIN_END: "on_chain_end",
            EventType.LLM_END: "on_llm_end",
            EventType.TOOL_END: "on_tool_end",
            EventType.RETRIEVER_END: "on_retriever_end",
        }
        for h in handlers:
            getattr(h, end_dispatch[end_type])(end_event)
    except Exception as exc:
        duration = (time.monotonic() - start) * 1000
        err_event = StepEvent(
            event_type=err_type, name=name, run_id=run_id,
            parent_run_id=parent_run_id,
            error=str(exc), metadata=tracker.metadata,
            duration_ms=round(duration, 1),
        )
        err_dispatch = {
            EventType.CHAIN_ERROR: "on_chain_error",
            EventType.LLM_ERROR: "on_llm_error",
            EventType.TOOL_ERROR: "on_tool_error",
            EventType.RETRIEVER_ERROR: "on_retriever_error",
        }
        for h in handlers:
            getattr(h, err_dispatch[err_type])(err_event)
        raise
    finally:
        _local.parent_run_id = old_parent


# ──── Convenience: wrap existing trace_observability ────

def bridge_to_trace(trace, handler: CollectingHandler) -> None:
    """Bridge callback events into an existing DiagnosticTrace.

    Allows interoperability between the new callback system and
    the existing trace_observability.py DiagnosticTrace/DiagnosticSpan.
    """
    from trace_observability import DiagnosticSpan, SpanStatus

    status_map = {
        EventType.CHAIN_START: None,
        EventType.CHAIN_END: SpanStatus.OK,
        EventType.CHAIN_ERROR: SpanStatus.ERROR,
        EventType.TOOL_START: None,
        EventType.TOOL_END: SpanStatus.OK,
        EventType.TOOL_ERROR: SpanStatus.ERROR,
        EventType.LLM_START: None,
        EventType.LLM_END: SpanStatus.OK,
        EventType.LLM_ERROR: SpanStatus.ERROR,
    }

    spans_by_run: dict[str, DiagnosticSpan] = {}

    for event in handler.events:
        if event.event_type.value.endswith("_start"):
            span = trace.start_span(event.name, event.inputs)
            spans_by_run[event.run_id] = span
        elif event.event_type.value.endswith(("_end", "_error")):
            span = spans_by_run.get(event.run_id)
            if span:
                status = status_map.get(event.event_type, SpanStatus.ERROR)
                span.finish(status, event.outputs, event.error or "")


if __name__ == "__main__":
    # Demo: run a mock diagnosis chain with callback monitoring
    print("=== Hermes Doctor Callback Handler Demo ===\n")

    collector = CollectingHandler()
    printer = PrintingHandler()

    with chain_context([collector, printer], "agent_diagnosis", {"target": "."}) as chain:
        with step_context([collector, printer], "gateway_health", "tool",
                          inputs={"check": "ping"}) as step:
            time.sleep(0.05)
            step.set_output({"running": True})

        with step_context([collector, printer], "skills_integrity", "tool",
                          inputs={"check": "file_count"}) as step:
            time.sleep(0.03)
            step.set_output({"skill_count": 6})

        with step_context([collector, printer], "llm_diagnosis", "llm",
                          inputs={"prompt": "Analyze health..."}) as step:
            time.sleep(0.1)
            step.set_output({"diagnosis": "无异常"})

        chain.set_output({"score": 100, "status": "健康"})

    print(f"\n=== Collected {len(collector.events)} events ===")
    print(collector.get_trace_json())
    print(f"\n=== Summary ===")
    print(json.dumps(collector.summary(), ensure_ascii=False, indent=2))
