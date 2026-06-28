# -*- coding: utf-8 -*-
"""
白龙马医生-Hermes Doctor · Diagnostic Workflow Planner
AtomCollide-智械工坊 · 2026

planner→builder→postproc 三阶段管线。

功能:
  - DW1: 症状→诊断工作流自动规划
  - DW2: 诊断步骤链（带危险操作暂停确认）
  - DW3: 结构化诊断报告生成
  - DW4: 历史病例匹配（相似症状检索）

Usage:
    from diagnostic_planner import DiagnosticPlanner
    planner = DiagnosticPlanner()
    plan = planner.plan("飞书Bot收不到消息")
    report = planner.execute(plan)
"""

import json
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DiagnosticStep:
    """单个诊断步骤"""
    step_id: str
    name: str
    description: str
    command: str  # shell command or check description
    risk_level: str  # safe/caution/dangerous
    requires_confirmation: bool = False
    expected_output: str = ""
    remediation: str = ""
    status: str = "pending"  # pending/running/pass/fail/skip/blocked
    result: str = ""
    duration_ms: int = 0


@dataclass
class DiagnosticPlan:
    """诊断工作流计划"""
    plan_id: str
    symptom: str
    category: str
    steps: List[DiagnosticStep]
    created_at: str = ""
    confidence: float = 0.0
    estimated_duration_sec: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class CaseRecord:
    """历史病例"""
    case_id: str
    symptom: str
    root_cause: str
    resolution: str
    steps_taken: List[str]
    duration_sec: int
    success: bool
    timestamp: str


# ── 症状关键词→诊断模板映射 ──

SYMPTOM_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "gateway": {
        "keywords": ["gateway", "网关", "不响应", "无回复", "超时", "timeout"],
        "category": "Gateway故障",
        "steps": [
            {"name": "检查Gateway进程", "cmd": "ps aux | grep hermes | grep -v grep", "risk": "safe",
             "expected": "至少一个hermes进程运行中", "fix": "systemctl restart hermes-gateway"},
            {"name": "检查Gateway日志", "cmd": "tail -50 /var/log/hermes/gateway.log 2>/dev/null || journalctl -u hermes-gateway -n 50", "risk": "safe",
             "expected": "无ERROR/FATAL", "fix": "根据日志错误信息修复"},
            {"name": "检查端口占用", "cmd": "ss -tlnp | grep -E ':(8080|3000|5000)'", "risk": "safe",
             "expected": "Gateway端口正常监听", "fix": "检查端口冲突或防火墙规则"},
            {"name": "检查配置文件", "cmd": "cat ~/.hermes/config.yaml | head -50", "risk": "safe",
             "expected": "配置文件存在且格式正确", "fix": "修复YAML语法或缺失字段"},
        ],
    },
    "feishu": {
        "keywords": ["飞书", "feishu", "lark", "bot", "机器人", "群消息", "@mention"],
        "category": "飞书Bot故障",
        "steps": [
            {"name": "检查飞书Bot配置", "cmd": "cat ~/.hermes/config.yaml | grep -A 20 feishu", "risk": "safe",
             "expected": "app_id/app_secret配置正确", "fix": "检查飞书开放平台应用凭证"},
            {"name": "检查lark-cli认证", "cmd": "lark-cli auth +status 2>&1", "risk": "safe",
             "expected": "认证有效", "fix": "lark-cli auth +login"},
            {"name": "检查Gateway飞书连接", "cmd": "grep -i 'feishu\\|lark' /var/log/hermes/gateway.log | tail -20", "risk": "safe",
             "expected": "无连接错误", "fix": "检查网络/代理配置"},
            {"name": "检查群聊规则", "cmd": "cat ~/.hermes/config.yaml | grep -A 30 group_rules", "risk": "safe",
             "expected": "群聊规则配置正确", "fix": "检查respond_mode和require_mention"},
        ],
    },
    "cron": {
        "keywords": ["cron", "定时", "定时任务", "scheduled", "自动执行"],
        "category": "Cron任务故障",
        "steps": [
            {"name": "检查cron服务状态", "cmd": "systemctl status cron 2>/dev/null || service cron status", "risk": "safe",
             "expected": "cron服务运行中", "fix": "systemctl start cron"},
            {"name": "列出Hermes cron任务", "cmd": "hermes cron list 2>/dev/null || cat ~/.hermes/cron/*.yaml 2>/dev/null", "risk": "safe",
             "expected": "任务列表可读取", "fix": "检查cron配置文件"},
            {"name": "检查cron日志", "cmd": "grep -i cron /var/log/syslog | tail -20", "risk": "safe",
             "expected": "无执行失败记录", "fix": "根据日志修复具体错误"},
        ],
    },
    "memory": {
        "keywords": ["memory", "记忆", "MEMORY.md", "记忆膨胀", "上下文", "context"],
        "category": "记忆系统故障",
        "steps": [
            {"name": "检查MEMORY.md大小", "cmd": "wc -c ~/.hermes/MEMORY.md 2>/dev/null", "risk": "safe",
             "expected": "<10KB", "fix": "精简MEMORY.md，删除过时条目"},
            {"name": "检查记忆目录", "cmd": "ls -la ~/.hermes/memory/ 2>/dev/null | tail -10", "risk": "safe",
             "expected": "目录存在且有近期文件", "fix": "创建memory目录"},
            {"name": "检查fact_store", "cmd": "ls -la ~/.hermes/memory_store.db 2>/dev/null", "risk": "safe",
             "expected": "数据库文件存在", "fix": "重启hermes初始化数据库"},
        ],
    },
    "skill": {
        "keywords": ["skill", "技能", "插件", "plugin", "找不到", "not found"],
        "category": "技能系统故障",
        "steps": [
            {"name": "检查技能目录", "cmd": "ls ~/.hermes/skills/ | head -20", "risk": "safe",
             "expected": "技能目录存在且有内容", "fix": "安装缺失技能"},
            {"name": "检查SKILL.md格式", "cmd": "for f in ~/.hermes/skills/*/SKILL.md; do head -3 \"$f\"; echo '---'; done | head -30", "risk": "safe",
             "expected": "所有SKILL.md有YAML frontmatter", "fix": "修复格式错误的SKILL.md"},
            {"name": "检查技能依赖", "cmd": "grep -r 'required_commands' ~/.hermes/skills/*/SKILL.md | head -10", "risk": "safe",
             "expected": "依赖命令已安装", "fix": "安装缺失的命令行工具"},
        ],
    },
    "token": {
        "keywords": ["token", "消耗", "成本", "cost", "用量", "429", "rate limit"],
        "category": "Token/成本问题",
        "steps": [
            {"name": "检查当前provider配置", "cmd": "cat ~/.hermes/config.yaml | grep -A 10 provider", "risk": "safe",
             "expected": "provider配置正确", "fix": "检查API key和provider设置"},
            {"name": "检查最近错误日志", "cmd": "grep -i '429\\|rate.limit\\|quota' /var/log/hermes/gateway.log | tail -10", "risk": "safe",
             "expected": "无429错误", "fix": "等待rate limit重置或切换provider"},
            {"name": "检查Token守卫", "cmd": "ps aux | grep -i token.guardian", "risk": "safe",
             "expected": "Token守卫运行中", "fix": "启动Token守卫夜间模式"},
        ],
    },
    "performance": {
        "keywords": ["慢", "slow", "卡顿", "延迟", "latency", "性能"],
        "category": "性能问题",
        "steps": [
            {"name": "检查系统资源", "cmd": "free -h && echo '---' && df -h / && echo '---' && uptime", "risk": "safe",
             "expected": "内存/磁盘/CPU正常", "fix": "清理磁盘/重启服务释放内存"},
            {"name": "检查进程数", "cmd": "ps aux | grep hermes | wc -l", "risk": "safe",
             "expected": "<10个hermes进程", "fix": "kill多余的hermes进程"},
            {"name": "检查网络延迟", "cmd": "curl -w '%{time_total}' -o /dev/null -s https://api.openai.com/v1/models 2>/dev/null", "risk": "safe",
             "expected": "<2秒", "fix": "检查网络/代理配置"},
        ],
    },
}


class DiagnosticPlanner:
    """诊断工作流规划器"""

    def __init__(self, history_path: Optional[str] = None):
        self.history_path = Path(history_path) if history_path else Path.home() / ".hermes" / "diagnostic_history.json"
        self._history: List[CaseRecord] = self._load_history()

    def _load_history(self) -> List[CaseRecord]:
        """加载历史病例"""
        if self.history_path.exists():
            try:
                data = json.loads(self.history_path.read_text(encoding="utf-8"))
                return [CaseRecord(**c) for c in data.get("cases", [])]
            except Exception:
                pass
        return []

    def _save_history(self):
        """保存历史病例"""
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"cases": [asdict(c) for c in self._history[-100:]]}  # Keep last 100
        self.history_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def plan(self, symptom: str) -> DiagnosticPlan:
        """
        根据症状描述规划诊断工作流。

        Args:
            symptom: 症状描述（自然语言）

        Returns:
            诊断计划
        """
        symptom_lower = symptom.lower()
        best_match = None
        best_score = 0

        for template_name, template in SYMPTOM_TEMPLATES.items():
            score = sum(1 for kw in template["keywords"] if kw in symptom_lower)
            if score > best_score:
                best_score = score
                best_match = template

        if best_match is None:
            # Generic diagnostic
            best_match = {
                "category": "通用诊断",
                "steps": [
                    {"name": "检查系统状态", "cmd": "uptime && free -h && df -h /", "risk": "safe",
                     "expected": "系统资源正常", "fix": "清理资源"},
                    {"name": "检查Hermes日志", "cmd": "tail -30 /var/log/hermes/gateway.log 2>/dev/null", "risk": "safe",
                     "expected": "无错误", "fix": "根据日志修复"},
                    {"name": "检查配置完整性", "cmd": "hermes doctor --quick 2>/dev/null || echo 'hermes doctor not available'", "risk": "safe",
                     "expected": "配置检查通过", "fix": "修复配置问题"},
                ],
            }

        steps = []
        for i, step_def in enumerate(best_match["steps"]):
            step = DiagnosticStep(
                step_id=f"D{i+1:03d}",
                name=step_def["name"],
                description=step_def.get("description", step_def["name"]),
                command=step_def["cmd"],
                risk_level=step_def.get("risk", "safe"),
                requires_confirmation=step_def.get("risk", "safe") == "dangerous",
                expected_output=step_def.get("expected", ""),
                remediation=step_def.get("fix", ""),
            )
            steps.append(step)

        plan = DiagnosticPlan(
            plan_id=f"DP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            symptom=symptom,
            category=best_match["category"],
            steps=steps,
            created_at=datetime.now(timezone.utc).isoformat(),
            confidence=min(0.95, 0.5 + best_score * 0.15),
            estimated_duration_sec=len(steps) * 5,
        )

        return plan

    def find_similar_cases(self, symptom: str, top_k: int = 3) -> List[CaseRecord]:
        """检索相似历史病例"""
        if not self._history:
            return []

        symptom_words = set(re.findall(r'\w+', symptom.lower()))
        scored = []
        for case in self._history:
            case_words = set(re.findall(r'\w+', case.symptom.lower()))
            overlap = len(symptom_words & case_words)
            if overlap > 0:
                scored.append((overlap, case))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    def record_case(self, symptom: str, root_cause: str, resolution: str,
                    steps_taken: List[str], duration_sec: int, success: bool):
        """记录诊断病例"""
        case = CaseRecord(
            case_id=f"CR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            symptom=symptom, root_cause=root_cause, resolution=resolution,
            steps_taken=steps_taken, duration_sec=duration_sec,
            success=success, timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._history.append(case)
        self._save_history()

    def format_plan(self, plan: DiagnosticPlan) -> str:
        """格式化诊断计划为可读文本"""
        lines = [
            f"🩺 诊断计划: {plan.plan_id}",
            f"📋 症状: {plan.symptom}",
            f"📂 分类: {plan.category}",
            f"🎯 置信度: {plan.confidence:.0%}",
            f"⏱️ 预计耗时: {plan.estimated_duration_sec}秒",
            "",
            "诊断步骤:",
        ]

        for step in plan.steps:
            risk_icon = {"safe": "🟢", "caution": "🟡", "dangerous": "🔴"}.get(step.risk_level, "⚪")
            confirm = " ⚠️ 需确认" if step.requires_confirmation else ""
            lines.append(f"  {risk_icon} [{step.step_id}] {step.name}{confirm}")
            lines.append(f"     命令: {step.command}")
            lines.append(f"     预期: {step.expected_output}")
            lines.append(f"     修复: {step.remediation}")
            lines.append("")

        # Check for similar historical cases
        similar = self.find_similar_cases(plan.symptom)
        if similar:
            lines.append("📚 相似历史病例:")
            for case in similar:
                status = "✅" if case.success else "❌"
                lines.append(f"  {status} {case.symptom} → {case.resolution[:60]}")

        return "\n".join(lines)


# ── CLI ──

if __name__ == "__main__":
    import sys
    symptom = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "飞书Bot收不到消息"
    planner = DiagnosticPlanner()
    plan = planner.plan(symptom)
    print(planner.format_plan(plan))
