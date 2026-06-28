"""Trace Manager - 结构化日志追踪

融合自 dify 的 core/logging/ 和 core/ops/ 模块。
提供请求级追踪、结构化日志、OpenTelemetry 集成。
"""

import logging
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Optional


# 请求级上下文变量（融合自 dify core/logging/context.py）
_request_id: ContextVar[str] = ContextVar("trace_request_id", default="")
_trace_id: ContextVar[str] = ContextVar("trace_trace_id", default="")
_span_id: ContextVar[str] = ContextVar("trace_span_id", default="")


def get_request_id() -> str:
    """获取当前请求 ID"""
    return _request_id.get()


def get_trace_id() -> str:
    """获取当前追踪 ID"""
    return _trace_id.get()


def get_span_id() -> str:
    """获取当前 Span ID"""
    return _span_id.get()


def init_request_context() -> tuple[str, str]:
    """初始化请求上下文，返回 (request_id, trace_id)"""
    req_id = uuid.uuid4().hex[:10]
    trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, req_id).hex
    _request_id.set(req_id)
    _trace_id.set(trace_id)
    return req_id, trace_id


def clear_request_context():
    """清除请求上下文"""
    _request_id.set("")
    _trace_id.set("")
    _span_id.set("")


@dataclass
class TraceSpan:
    """追踪 Span"""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    name: str
    start_time: float
    end_time: Optional[float] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000
    
    def finish(self):
        self.end_time = time.time()
    
    def add_event(self, name: str, attributes: dict[str, Any] = None):
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })
    
    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": self.events,
        }


@dataclass
class TraceRecord:
    """追踪记录（融合自 dify TraceTaskName）"""
    trace_id: str
    request_id: str
    task_name: str  # message, tool, workflow, dataset_retrieval 等
    message_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_inputs: Optional[dict] = None
    tool_outputs: Optional[Any] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0
    
    def finish(self):
        self.end_time = time.time()
    
    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "task_name": self.task_name,
            "message_id": self.message_id,
            "tool_name": self.tool_name,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class TraceManager:
    """追踪管理器
    
    融合自 dify 的 ops_trace_manager，提供：
    - 请求级追踪 (request_id, trace_id)
    - Span 管理（父子关系）
    - 工具调用追踪
    - 结构化日志输出
    """
    
    def __init__(self, logger_name: str = "hermes.trace"):
        self.logger = logging.getLogger(logger_name)
        self._spans: dict[str, TraceSpan] = {}
        self._records: list[TraceRecord] = []
        self._current_span: Optional[TraceSpan] = None
    
    def start_trace(self, task_name: str, **kwargs) -> TraceRecord:
        """开始一个新的追踪记录"""
        req_id, trace_id = init_request_context()
        
        record = TraceRecord(
            trace_id=trace_id,
            request_id=req_id,
            task_name=task_name,
            **kwargs,
        )
        self._records.append(record)
        
        self.logger.info(
            f"[Trace] Started: {task_name}",
            extra={"trace_id": trace_id, "request_id": req_id},
        )
        
        return record
    
    def start_span(self, name: str, parent_span_id: str = None) -> TraceSpan:
        """开始一个新的 Span"""
        span_id = uuid.uuid4().hex[:8]
        trace_id = get_trace_id()
        
        span = TraceSpan(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id or (self._current_span.span_id if self._current_span else None),
            name=name,
            start_time=time.time(),
        )
        
        self._spans[span_id] = span
        self._current_span = span
        _span_id.set(span_id)
        
        self.logger.debug(f"[Span] Started: {name} ({span_id})")
        return span
    
    def end_span(self, span_id: str = None):
        """结束一个 Span"""
        target_id = span_id or (self._current_span.span_id if self._current_span else None)
        if target_id and target_id in self._spans:
            span = self._spans[target_id]
            span.finish()
            
            self.logger.debug(
                f"[Span] Ended: {span.name} ({span.span_id}) - {span.duration_ms:.1f}ms"
            )
            
            if self._current_span and self._current_span.span_id == target_id:
                self._current_span = None
    
    def add_tool_trace(self, tool_name: str, tool_inputs: dict, 
                       tool_outputs: Any = None, message_id: str = None):
        """添加工具调用追踪（融合自 dify TraceTaskName.TOOL_TRACE）"""
        trace_id = get_trace_id()
        request_id = get_request_id()
        
        record = TraceRecord(
            trace_id=trace_id,
            request_id=request_id,
            task_name="tool_trace",
            tool_name=tool_name,
            tool_inputs=tool_inputs,
            tool_outputs=str(tool_outputs)[:1000] if tool_outputs else None,
            message_id=message_id,
        )
        record.finish()
        self._records.append(record)
        
        self.logger.info(
            f"[Tool] {tool_name} - {record.duration_ms:.1f}ms",
            extra={"trace_id": trace_id, "tool": tool_name},
        )
    
    def get_current_context(self) -> dict[str, str]:
        """获取当前追踪上下文"""
        return {
            "request_id": get_request_id(),
            "trace_id": get_trace_id(),
            "span_id": get_span_id(),
        }
    
    def get_records(self, task_name: str = None) -> list[TraceRecord]:
        """获取追踪记录"""
        if task_name:
            return [r for r in self._records if r.task_name == task_name]
        return self._records.copy()
    
    def get_spans(self) -> list[TraceSpan]:
        """获取所有 Span"""
        return list(self._spans.values())
    
    def export_json(self) -> dict:
        """导出为 JSON 格式（可用于 OpenTelemetry 兼容系统）"""
        return {
            "resource_spans": [{
                "spans": [s.to_dict() for s in self._spans.values()],
            }],
            "records": [r.to_dict() for r in self._records],
        }


# 结构化日志格式器（融合自 dify structured_formatter.py）
class StructuredFormatter(logging.Formatter):
    """结构化日志格式器，自动注入追踪上下文"""
    
    def format(self, record):
        # 注入追踪上下文
        record.request_id = get_request_id()
        record.trace_id = get_trace_id()
        record.span_id = get_span_id()
        
        return super().format(record)


# 使用示例
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    manager = TraceManager()
    
    # 开始追踪
    trace = manager.start_trace("test_workflow")
    
    # 创建 Span
    span1 = manager.start_span("step1")
    span1.add_event("processing", {"item_count": 42})
    manager.end_span()
    
    # 工具调用追踪
    manager.add_tool_trace(
        tool_name="web_search",
        tool_inputs={"query": "test"},
        tool_outputs={"results": ["item1", "item2"]},
    )
    
    # 导出
    import json
    print(json.dumps(manager.export_json(), indent=2))
