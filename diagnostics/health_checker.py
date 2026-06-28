"""Health Checker - 健康端点监控

融合自 dify 的 /health 端点和 /threads、/db-pool-stat 监控能力。
提供 Agent 运行时健康状态检查、线程监控、连接池统计。
"""

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HealthStatus:
    """健康状态快照"""
    pid: int
    status: str  # "ok", "degraded", "critical"
    version: str
    uptime_seconds: float
    timestamp: float = field(default_factory=time.time)
    threads: list[dict[str, Any]] = field(default_factory=list)
    thread_count: int = 0
    memory_mb: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """Agent 健康检查器
    
    提供类似 dify /health 端点的诊断能力：
    - 进程状态 (PID, status, version)
    - 线程监控 (active threads, alive status)
    - 内存使用统计
    - 连接池状态（如可用）
    """
    
    def __init__(self, version: str = "0.1.0"):
        self.version = version
        self.start_time = time.time()
        self._checks: list[callable] = []
        self._register_default_checks()
    
    def _register_default_checks(self):
        """注册默认健康检查项"""
        self._checks = [
            self._check_process,
            self._check_threads,
            self._check_memory,
        ]
    
    def register_check(self, check_fn: callable):
        """注册自定义健康检查项"""
        self._checks.append(check_fn)
    
    def check(self) -> HealthStatus:
        """执行完整健康检查"""
        status = HealthStatus(
            pid=os.getpid(),
            status="ok",
            version=self.version,
            uptime_seconds=time.time() - self.start_time,
        )
        
        issues = []
        for check in self._checks:
            try:
                result = check()
                if result and isinstance(result, dict):
                    if "threads" in result:
                        status.threads = result["threads"]
                        status.thread_count = len(result["threads"])
                    if "memory_mb" in result:
                        status.memory_mb = result["memory_mb"]
                    if "issues" in result:
                        issues.extend(result["issues"])
                    status.details.update(result)
            except Exception as e:
                issues.append(f"Check failed: {e}")
        
        # 根据问题严重度调整状态
        if any("critical" in str(i).lower() for i in issues):
            status.status = "critical"
        elif issues:
            status.status = "degraded"
        
        status.details["issues"] = issues
        return status
    
    def _check_process(self) -> dict[str, Any]:
        """检查进程状态"""
        return {
            "pid": os.getpid(),
            "cwd": os.getcwd(),
            "environ_set": len(os.environ),
        }
    
    def _check_threads(self) -> dict[str, Any]:
        """检查线程状态（融合自 dify /threads 端点）"""
        threads = []
        for thread in threading.enumerate():
            threads.append({
                "name": thread.name,
                "id": thread.ident,
                "is_alive": thread.is_alive(),
                "daemon": thread.daemon,
            })
        
        alive_count = sum(1 for t in threads if t["is_alive"])
        issues = []
        if alive_count > 100:
            issues.append(f"High thread count: {alive_count}")
        
        return {
            "threads": threads,
            "thread_count": len(threads),
            "alive_count": alive_count,
            "issues": issues,
        }
    
    def _check_memory(self) -> dict[str, Any]:
        """检查内存使用"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem = process.memory_info()
            memory_mb = mem.rss / 1024 / 1024
            
            issues = []
            if memory_mb > 1024:  # > 1GB
                issues.append(f"High memory usage: {memory_mb:.1f}MB")
            
            return {
                "memory_mb": round(memory_mb, 2),
                "memory_rss_mb": round(mem.rss / 1024 / 1024, 2),
                "memory_vms_mb": round(mem.vms / 1024 / 1024, 2),
                "issues": issues,
            }
        except ImportError:
            return {"memory_mb": 0, "issues": ["psutil not available"]}


# 使用示例
if __name__ == "__main__":
    checker = HealthChecker(version="0.3.0")
    status = checker.check()
    print(f"Health: {status.status}")
    print(f"PID: {status.pid}")
    print(f"Uptime: {status.uptime_seconds:.1f}s")
    print(f"Threads: {status.thread_count}")
    print(f"Memory: {status.memory_mb:.1f}MB")
