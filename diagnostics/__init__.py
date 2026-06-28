"""Hermes Doctor Diagnostics - 诊断模块

融合自 dify 的诊断能力，提供：
- HealthChecker: 健康端点监控
- ErrorClassifier: 错误分类层级
- TraceManager: 结构化日志追踪
"""

from .health_checker import HealthChecker, HealthStatus
from .error_classifier import ErrorClassifier, ErrorCategory, ErrorSeverity, ClassifiedError
from .trace_manager import TraceManager, TraceSpan, TraceRecord, get_request_id, get_trace_id

__all__ = [
    "HealthChecker", "HealthStatus",
    "ErrorClassifier", "ErrorCategory", "ErrorSeverity", "ClassifiedError",
    "TraceManager", "TraceSpan", "TraceRecord",
    "get_request_id", "get_trace_id",
]
