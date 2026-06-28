"""Error Classifier - 错误分类层级

融合自 dify 的错误分类体系 (core/errors/error.py)。
提供结构化的 Agent 错误分类、严重度评估和修复建议。
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class ErrorSeverity(Enum):
    """错误严重度"""
    LOW = "low"           # 警告，不影响核心功能
    MEDIUM = "medium"     # 部分功能受影响
    HIGH = "high"         # 核心功能不可用
    CRITICAL = "critical" # 系统级故障


class ErrorCategory(Enum):
    """错误分类（融合自 dify 错误层级）"""
    # LLM 相关
    LLM_ERROR = "llm_error"
    LLM_BAD_REQUEST = "llm_bad_request"
    LLM_RATE_LIMIT = "llm_rate_limit"
    LLM_QUOTA_EXCEEDED = "llm_quota_exceeded"
    LLM_MODEL_NOT_SUPPORTED = "llm_model_not_supported"
    
    # Provider 相关
    PROVIDER_TOKEN_NOT_INIT = "provider_token_not_init"
    PROVIDER_AUTH_FAILED = "provider_auth_failed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    
    # 配置相关
    CONFIG_INVALID = "config_invalid"
    CONFIG_MISSING = "config_missing"
    CONFIG_PERMISSION_DENIED = "config_permission_denied"
    
    # 工具相关
    TOOL_NOT_FOUND = "tool_not_found"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    TOOL_TIMEOUT = "tool_timeout"
    
    # 网络相关
    NETWORK_ERROR = "network_error"
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_DNS_FAILED = "network_dns_failed"
    
    # 文件系统相关
    FILE_NOT_FOUND = "file_not_found"
    FILE_PERMISSION_DENIED = "file_permission_denied"
    FILE_CORRUPTED = "file_corrupted"
    
    # 未知
    UNKNOWN = "unknown"


# 错误模式匹配规则
ERROR_PATTERNS: dict[str, tuple[ErrorCategory, ErrorSeverity, str]] = {
    # LLM 错误
    "invalid_api_key": (ErrorCategory.PROVIDER_AUTH_FAILED, ErrorSeverity.HIGH, "API Key 无效或已过期"),
    "rate_limit": (ErrorCategory.LLM_RATE_LIMIT, ErrorSeverity.MEDIUM, "请求频率超限，建议降低调用频率"),
    "quota_exceeded": (ErrorCategory.LLM_QUOTA_EXCEEDED, ErrorSeverity.HIGH, "API 配额已用完"),
    "model_not_found": (ErrorCategory.LLM_MODEL_NOT_SUPPORTED, ErrorSeverity.HIGH, "模型不存在或不可用"),
    "context_length_exceeded": (ErrorCategory.LLM_BAD_REQUEST, ErrorSeverity.MEDIUM, "上下文长度超限，建议缩短输入"),
    
    # 网络错误
    "connection_refused": (ErrorCategory.NETWORK_ERROR, ErrorSeverity.HIGH, "连接被拒绝，检查服务是否运行"),
    "connection_timeout": (ErrorCategory.NETWORK_TIMEOUT, ErrorSeverity.MEDIUM, "连接超时，检查网络状态"),
    "dns_resolution_failed": (ErrorCategory.NETWORK_DNS_FAILED, ErrorSeverity.HIGH, "DNS 解析失败"),
    "ssl_error": (ErrorCategory.NETWORK_ERROR, ErrorSeverity.HIGH, "SSL/TLS 错误"),
    
    # 文件错误
    "no such file": (ErrorCategory.FILE_NOT_FOUND, ErrorSeverity.LOW, "文件不存在"),
    "permission denied": (ErrorCategory.FILE_PERMISSION_DENIED, ErrorSeverity.MEDIUM, "权限不足"),
    
    # 配置错误
    "config not found": (ErrorCategory.CONFIG_MISSING, ErrorSeverity.HIGH, "配置文件缺失"),
    "invalid config": (ErrorCategory.CONFIG_INVALID, ErrorSeverity.HIGH, "配置格式错误"),
}


@dataclass
class ClassifiedError:
    """分类后的错误"""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    suggestion: str
    original_error: Optional[Exception] = None
    context: dict = None
    
    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "suggestion": self.suggestion,
            "context": self.context or {},
        }


class ErrorClassifier:
    """Agent 错误分类器
    
    融合自 dify 的错误分类体系，提供：
    - 结构化错误分类
    - 严重度评估
    - 修复建议
    - 错误模式匹配
    """
    
    def __init__(self):
        self.patterns = ERROR_PATTERNS.copy()
    
    def register_pattern(self, pattern: str, category: ErrorCategory, 
                        severity: ErrorSeverity, suggestion: str):
        """注册自定义错误模式"""
        self.patterns[pattern.lower()] = (category, severity, suggestion)
    
    def classify(self, error: Exception) -> ClassifiedError:
        """分类一个错误"""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # 尝试模式匹配
        for pattern, (category, severity, suggestion) in self.patterns.items():
            if pattern in error_str or pattern in error_type:
                return ClassifiedError(
                    category=category,
                    severity=severity,
                    message=str(error),
                    suggestion=suggestion,
                    original_error=error,
                )
        
        # 默认分类
        return ClassifiedError(
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            message=str(error),
            suggestion="未知错误，请检查日志获取更多信息",
            original_error=error,
        )
    
    def classify_string(self, error_msg: str) -> ClassifiedError:
        """分类一个错误消息字符串"""
        class MockError(Exception):
            pass
        
        return self.classify(MockError(error_msg))


# 使用示例
if __name__ == "__main__":
    classifier = ErrorClassifier()
    
    # 测试各种错误
    test_errors = [
        "Invalid API Key provided",
        "Rate limit exceeded for requests",
        "Connection refused to localhost:8080",
        "No such file or directory: /path/to/file",
        "Some unknown error",
    ]
    
    for msg in test_errors:
        result = classifier.classify_string(msg)
        print(f"[{result.severity.value}] {result.category.value}: {result.message}")
        print(f"  -> {result.suggestion}")
        print()
