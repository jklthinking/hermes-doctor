"""
Hermes Doctor — Trace-based Observability
==========================================
Inspired by Dify (145K⭐) ops trace system.

Key patterns adopted:
- TraceID propagation across diagnosis chain
- Span-based execution tracking (start_time, end_time, metadata)
- Retryable failure classification
- Health check with structured diagnostics
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from enum import Enum


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class DiagnosticSpan:
    """A single diagnostic span — tracks one check operation."""
    span_id: str
    name: str
    status: SpanStatus = SpanStatus.OK
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    error: str = ""
    metadata: dict = field(default_factory=dict)

    def finish(self, status: SpanStatus = SpanStatus.OK, outputs: dict = None, error: str = ""):
        self.end_time = datetime.now()
        self.status = status
        if outputs:
            self.outputs = outputs
        if error:
            self.error = error

    @property
    def duration_ms(self) -> float:
        if not self.end_time:
            return 0
        return (self.end_time - self.start_time).total_seconds() * 1000

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start_time"] = self.start_time.isoformat()
        d["end_time"] = self.end_time.isoformat() if self.end_time else None
        d["duration_ms"] = round(self.duration_ms, 1)
        return d


@dataclass
class DiagnosticTrace:
    """Full diagnostic trace — collection of spans forming a diagnosis chain.
    
    Similar to Dify's BaseTraceInfo with trace_id propagation.
    """
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_id: str = ""
    spans: list[DiagnosticSpan] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    overall_status: SpanStatus = SpanStatus.OK
    diagnosis: str = ""
    prescription: str = ""

    def start_span(self, name: str, inputs: dict = None) -> DiagnosticSpan:
        span = DiagnosticSpan(
            span_id=f"{self.trace_id}-{len(self.spans)}",
            name=name,
            inputs=inputs or {},
        )
        self.spans.append(span)
        return span

    def finish(self):
        self.end_time = datetime.now()
        failed = [s for s in self.spans if s.status == SpanStatus.ERROR]
        if failed:
            self.overall_status = SpanStatus.ERROR
        timed_out = [s for s in self.spans if s.status == SpanStatus.TIMEOUT]
        if timed_out and not failed:
            self.overall_status = SpanStatus.TIMEOUT

    @property
    def duration_ms(self) -> float:
        if not self.end_time:
            return 0
        return (self.end_time - self.start_time).total_seconds() * 1000

    def summary(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "agent_id": self.agent_id,
            "overall_status": self.overall_status.value,
            "duration_ms": round(self.duration_ms, 1),
            "total_spans": len(self.spans),
            "failed_spans": sum(1 for s in self.spans if s.status == SpanStatus.ERROR),
            "diagnosis": self.diagnosis,
            "prescription": self.prescription,
            "spans": [s.to_dict() for s in self.spans],
        }

    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.summary(), f, ensure_ascii=False, indent=2)


# ──── Diagnostic Checks ────

def check_gateway_health(trace: DiagnosticTrace) -> bool:
    """Check if Hermes gateway is responsive."""
    span = trace.start_span("gateway_health", {"check": "ping"})
    try:
        import subprocess
        result = subprocess.run(
            ["pgrep", "-f", "hermes.*gateway"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            span.finish(SpanStatus.OK, {"running": True, "pids": result.stdout.strip()})
            return True
        else:
            span.finish(SpanStatus.ERROR, {"running": False}, "Gateway process not found")
            return False
    except Exception as e:
        span.finish(SpanStatus.ERROR, error=str(e))
        return False


def check_skills_integrity(trace: DiagnosticTrace) -> dict:
    """Check skills directory integrity."""
    span = trace.start_span("skills_integrity", {"check": "file_count"})
    try:
        import os
        skills_dir = os.path.expanduser("~/.hermes/skills")
        if not os.path.exists(skills_dir):
            span.finish(SpanStatus.ERROR, error="Skills directory not found")
            return {"status": "error", "count": 0}

        count = 0
        for root, dirs, files in os.walk(skills_dir):
            dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules']]
            for f in files:
                if f == "SKILL.md":
                    count += 1

        span.finish(SpanStatus.OK, {"skill_count": count})
        return {"status": "ok", "count": count}
    except Exception as e:
        span.finish(SpanStatus.ERROR, error=str(e))
        return {"status": "error", "count": 0}


def check_memory_health(trace: DiagnosticTrace) -> dict:
    """Check memory files health."""
    span = trace.start_span("memory_health", {"check": "file_sizes"})
    try:
        import os
        memory_dir = os.path.expanduser("~/.hermes")
        sizes = {}
        for fname in ["MEMORY.md", "USER.md"]:
            fpath = os.path.join(memory_dir, fname)
            if os.path.exists(fpath):
                size = os.path.getsize(fpath)
                sizes[fname] = size
                if size > 50000:  # 50KB warning
                    span.metadata[f"warning_{fname}"] = f"File too large: {size} bytes"

        span.finish(SpanStatus.OK, {"file_sizes": sizes})
        return {"status": "ok", "sizes": sizes}
    except Exception as e:
        span.finish(SpanStatus.ERROR, error=str(e))
        return {"status": "error"}


def run_diagnosis(agent_id: str = "default") -> dict:
    """Run full agent diagnosis with trace-based observability."""
    trace = DiagnosticTrace(agent_id=agent_id)

    gateway_ok = check_gateway_health(trace)
    skills_result = check_skills_integrity(trace)
    memory_result = check_memory_health(trace)

    # Generate diagnosis
    issues = []
    if not gateway_ok:
        issues.append("Gateway进程未运行")
    if skills_result.get("count", 0) == 0:
        issues.append("Skills目录为空")
    if memory_result.get("status") == "error":
        issues.append("Memory文件异常")

    trace.diagnosis = "无异常" if not issues else "; ".join(issues)
    trace.prescription = "系统正常运行" if not issues else f"需要修复: {'、'.join(issues)}"
    trace.finish()

    return trace.summary()


if __name__ == "__main__":
    result = run_diagnosis("test-agent")
    print(json.dumps(result, ensure_ascii=False, indent=2))
