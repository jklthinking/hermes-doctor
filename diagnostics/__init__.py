"""Hermes Doctor Diagnostics - 诊断模块

提供运行时诊断能力：
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
    "RuntimeIssue", "diagnose_flow_log", "diagnose_pending_events", "diagnose_transition_drift",
    "BridgePreflightDoctor", "DiagnosticFinding",
]

from .agent_runtime_diagnostics import RuntimeIssue, diagnose_flow_log, diagnose_pending_events, diagnose_transition_drift
from .agent_bridge_preflight import BridgePreflightDoctor, DiagnosticFinding
