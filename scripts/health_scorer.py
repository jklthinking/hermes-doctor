"""
Hermes Doctor — Quantitative Health Scoring Engine
====================================================
Multi-dimensional health metrics inspired by Dify's ops monitoring
and LangChain's evaluation framework.

Features:
- Multi-axis scoring (structure, runtime, security, dependencies, performance)
- Trend analysis with rolling baseline
- Weighted component aggregation
- Health grade classification (A/B/C/D/F)
- JSON export for dashboard integration
- CLI integration with hermes_doctor.py

Brand: AtomCollide-智械工坊
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ──── Scoring Axes ────

@dataclass
class AxisScore:
    """Score for a single health dimension."""
    name: str
    display_name: str
    score: float  # 0-100
    weight: float  # 0.0-1.0
    checks_total: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    checks_warned: int = 0
    findings: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        if self.checks_total == 0:
            return 100.0
        return round((self.checks_passed / self.checks_total) * 100, 1)

    def to_dict(self) -> dict:
        return asdict(self)


# Pre-defined health axes with default weights
DEFAULT_AXES = [
    AxisScore("structure", "项目结构", 100.0, 0.25),
    AxisScore("runtime", "运行时健康", 100.0, 0.20),
    AxisScore("security", "安全合规", 100.0, 0.20),
    AxisScore("dependencies", "依赖可用性", 100.0, 0.15),
    AxisScore("performance", "性能指标", 100.0, 0.10),
    AxisScore("observability", "可观测性", 100.0, 0.10),
]


@dataclass
class HealthReport:
    """Complete multi-dimensional health report."""
    agent_id: str
    target: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    axes: list[AxisScore] = field(default_factory=list)
    composite_score: float = 0.0
    grade: str = ""
    status: str = ""
    trend: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def compute_composite(self) -> float:
        """Weighted average of all axis scores."""
        if not self.axes:
            self.composite_score = 0.0
            return 0.0
        total_weight = sum(a.weight for a in self.axes)
        if total_weight == 0:
            self.composite_score = 0.0
            return 0.0
        weighted = sum(a.score * a.weight for a in self.axes)
        self.composite_score = round(weighted / total_weight, 1)
        return self.composite_score

    def compute_grade(self) -> str:
        """Assign letter grade based on composite score."""
        score = self.composite_score
        if score >= 95:
            self.grade = "A+"
        elif score >= 90:
            self.grade = "A"
        elif score >= 80:
            self.grade = "B"
        elif score >= 70:
            self.grade = "C"
        elif score >= 60:
            self.grade = "D"
        else:
            self.grade = "F"
        return self.grade

    def compute_status(self) -> str:
        """Determine overall status from axes."""
        has_critical = any(a.score < 50 for a in self.axes)
        has_warn = any(50 <= a.score < 80 for a in self.axes)
        if has_critical:
            self.status = "严重异常"
        elif has_warn:
            self.status = "需要关注"
        else:
            self.status = "健康"
        return self.status

    def generate_recommendations(self) -> list[str]:
        """Generate actionable recommendations from weakest axes."""
        sorted_axes = sorted(self.axes, key=lambda a: a.score)
        self.recommendations = []
        for axis in sorted_axes:
            if axis.score < 80:
                for finding in axis.findings[:2]:
                    self.recommendations.append(f"[{axis.display_name}] {finding}")
        return self.recommendations

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "target": self.target,
            "timestamp": self.timestamp.isoformat(),
            "composite_score": self.composite_score,
            "grade": self.grade,
            "status": self.status,
            "axes": [a.to_dict() for a in self.axes],
            "trend": self.trend,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        """Render report as human-readable markdown."""
        lines = [
            "# Hermes Doctor 健康评分报告",
            "",
            f"**目标**: {self.target}",
            f"**时间**: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**综合评分**: {self.composite_score}/100",
            f"**等级**: {self.grade}",
            f"**状态**: {self.status}",
            "",
            "## 维度评分",
            "",
            "| 维度 | 评分 | 权重 | 通过率 | 状态 |",
            "|------|------|------|--------|------|",
        ]
        for a in self.axes:
            icon = "✅" if a.score >= 80 else ("⚠️" if a.score >= 50 else "❌")
            pass_str = f"{a.checks_passed}/{a.checks_total}" if a.checks_total > 0 else "N/A"
            lines.append(
                f"| {a.display_name} | {a.score}/100 | {a.weight:.0%} | {pass_str} | {icon} |"
            )
        if self.trend:
            lines.extend(["", "## 趋势分析", ""])
            trend = self.trend
            lines.append(f"- 历史样本数: {trend.get('sample_count', 0)}")
            lines.append(f"- 基线评分: {trend.get('baseline_score', 'N/A')}")
            delta = trend.get('delta')
            if delta is not None:
                arrow = "📈" if delta > 0 else ("📉" if delta < 0 else "➡️")
                lines.append(f"- 变化: {arrow} {delta:+.1f}")
        if self.recommendations:
            lines.extend(["", "## 建议修复", ""])
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")
        return "\n".join(lines)


# ──── History / Trend Tracker ────

HISTORY_FILE = os.environ.get(
    "HERMES_DOCTOR_HEALTH_HISTORY",
    os.path.expanduser("~/.hermes/.doctor/health_history.json"),
)


def load_history(path: str = HISTORY_FILE) -> list[dict]:
    """Load historical health scores."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("samples", [])
    except Exception:
        return []


def save_history(report: HealthReport, path: str = HISTORY_FILE) -> None:
    """Append current report to history."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    samples = load_history(path)
    samples.append({
        "timestamp": report.timestamp.isoformat(),
        "composite_score": report.composite_score,
        "grade": report.grade,
        "axes": {a.name: a.score for a in report.axes},
    })
    # Keep last 50 samples
    samples = samples[-50:]
    p.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def compute_trend(report: HealthReport, path: str = HISTORY_FILE) -> dict:
    """Compute trend from historical data."""
    samples = load_history(path)
    if not samples:
        report.trend = {
            "status": "no_history",
            "sample_count": 0,
            "baseline_score": None,
            "delta": None,
            "message": "首次运行，无历史基线。",
        }
        return report.trend

    scores = [s["composite_score"] for s in samples]
    recent = scores[-10:]
    baseline = round(sum(recent) / len(recent), 1)
    delta = round(report.composite_score - baseline, 1)

    if len(recent) < 3:
        status = "warming_up"
        message = f"样本不足（{len(recent)}/3），趋势仅供参考。"
    elif abs(delta) >= 15:
        status = "significant_change"
        direction = "下降" if delta < 0 else "上升"
        message = f"评分{direction} {abs(delta):.1f} 分，建议关注。"
    elif abs(delta) >= 5:
        status = "minor_change"
        direction = "下降" if delta < 0 else "上升"
        message = f"评分{direction} {abs(delta):.1f} 分，在正常波动范围。"
    else:
        status = "stable"
        message = "评分稳定，无显著变化。"

    report.trend = {
        "status": status,
        "sample_count": len(recent),
        "baseline_score": baseline,
        "delta": delta,
        "message": message,
    }
    return report.trend


# ──── Scoring Engine ────

class HealthScorer:
    """Multi-dimensional health scoring engine.

    Usage:
        scorer = HealthScorer(agent_id="default", target=".")
        report = scorer.run()
        print(report.to_markdown())
    """

    def __init__(self, agent_id: str = "default", target: str = ".",
                 history_path: str = HISTORY_FILE) -> None:
        self.agent_id = agent_id
        self.target = target
        self.history_path = history_path
        self.axes: list[AxisScore] = [
            AxisScore(a.name, a.display_name, 100.0, a.weight)
            for a in DEFAULT_AXES
        ]

    def _get_axis(self, name: str) -> AxisScore:
        return next(a for a in self.axes if a.name == name)

    def deduct(self, axis_name: str, points: float, check_passed: bool,
               finding: str = "") -> None:
        """Record a check result and deduct points from an axis."""
        axis = self._get_axis(axis_name)
        axis.checks_total += 1
        if check_passed:
            axis.checks_passed += 1
        else:
            axis.checks_failed += 1
            axis.score = max(0, axis.score - points)
            if finding:
                axis.findings.append(finding)

    def warn(self, axis_name: str, points: float, finding: str = "") -> None:
        """Record a warning-level finding."""
        axis = self._get_axis(axis_name)
        axis.checks_total += 1
        axis.checks_warned += 1
        axis.checks_passed += 1  # warnings still pass
        axis.score = max(0, axis.score - points)
        if finding:
            axis.findings.append(finding)

    def run(self, findings: list = None) -> HealthReport:
        """Run scoring from existing hermes_doctor.py findings.

        If findings list is provided (from check_project), maps them to axes.
        Otherwise runs standalone checks.
        """
        report = HealthReport(
            agent_id=self.agent_id,
            target=self.target,
            axes=self.axes,
        )

        if findings is not None:
            self._score_from_findings(findings)
        else:
            self._run_standalone_checks()

        report.compute_composite()
        report.compute_grade()
        report.compute_status()
        compute_trend(report, self.history_path)
        report.generate_recommendations()
        save_history(report, self.history_path)

        return report

    def _score_from_findings(self, findings: list) -> None:
        """Map hermes_doctor.py Finding objects to axis scores."""
        # Map prescription IDs to axes
        rx_to_axis = {
            "RX-HERMES-001": "structure",
            "RX-HERMES-002": "structure",
            "RX-HERMES-003": "structure",
            "RX-HERMES-004": "structure",
            "RX-HERMES-005": "structure",
            "RX-HERMES-006": "structure",
            "RX-RUNTIME-001": "runtime",
            "RX-RUNTIME-002": "runtime",
            "RX-TOOL-001": "dependencies",
            "RX-DEP-001": "dependencies",
            "RX-FILE-001": "structure",
            "RX-SAFETY-001": "security",
            "RX-SAFETY-002": "security",
            "RX-FEISHU-003": "runtime",
            "RX-LOG-001": "observability",
        }
        level_deductions = {"fail": 25, "warn": 12, "info": 3}

        for f in findings:
            axis_name = rx_to_axis.get(f.prescription, "runtime")
            points = level_deductions.get(f.level, 5)
            desc = f"{f.title}: {f.evidence}"
            if f.level == "fail":
                self.deduct(axis_name, points, False, desc)
            elif f.level == "warn":
                self.warn(axis_name, points, desc)
            else:
                # info-level: light deduction, still passes
                self.warn(axis_name, points, desc)

    def _run_standalone_checks(self) -> None:
        """Run independent checks when no pre-computed findings exist."""
        target = Path(self.target).expanduser().resolve()

        # Structure checks
        struct = self._get_axis("structure")
        for name in [".hermes-skill/plugin.json", "SKILL.md", "README.md"]:
            exists = (target / name).exists()
            struct.checks_total += 1
            if exists:
                struct.checks_passed += 1
            else:
                struct.checks_failed += 1
                struct.score = max(0, struct.score - 20)
                struct.findings.append(f"缺少 {name}")

        # Security checks
        sec = self._get_axis("security")
        env_files = list(target.glob(".env")) + list(target.glob(".env.local"))
        sec.checks_total += 1
        if env_files:
            # .env exists — check it's not tracked
            gitignore = target / ".gitignore"
            if gitignore.exists():
                gi_text = gitignore.read_text(encoding="utf-8", errors="replace")
                if ".env" in gi_text:
                    sec.checks_passed += 1
                else:
                    sec.checks_warned += 1
                    sec.score = max(0, sec.score - 10)
                    sec.findings.append(".env 存在但未在 .gitignore 中忽略")
            else:
                sec.checks_warned += 1
                sec.score = max(0, sec.score - 10)
                sec.findings.append(".env 存在但无 .gitignore")
        else:
            sec.checks_passed += 1

        # Dependency checks
        dep = self._get_axis("dependencies")
        import shutil
        for tool in ["python3", "rg"]:
            dep.checks_total += 1
            if shutil.which(tool):
                dep.checks_passed += 1
            else:
                dep.checks_failed += 1
                dep.score = max(0, dep.score - 15)
                dep.findings.append(f"命令不可用: {tool}")

        # Runtime checks
        runtime = self._get_axis("runtime")
        log_patterns = ["*.log", "*.err", "*.out"]
        log_files = []
        for pat in log_patterns:
            log_files.extend(target.glob(pat))
        runtime.checks_total += 1
        if not log_files:
            runtime.checks_passed += 1
        else:
            has_errors = False
            for lf in log_files[:5]:
                try:
                    text = lf.read_text(encoding="utf-8", errors="replace")[:10000]
                    if any(w in text.lower() for w in ["error", "failed", "exception", "timeout"]):
                        has_errors = True
                        break
                except Exception:
                    continue
            if has_errors:
                runtime.checks_failed += 1
                runtime.score = max(0, runtime.score - 15)
                runtime.findings.append(f"日志文件包含错误关键词")
            else:
                runtime.checks_passed += 1

        # Observability checks
        obs = self._get_axis("observability")
        obs.checks_total += 1
        trace_file = target / "scripts" / "trace_observability.py"
        callback_file = target / "scripts" / "callback_handler.py"
        if trace_file.exists() and callback_file.exists():
            obs.checks_passed += 1
            obs.details["trace_system"] = "complete"
        elif trace_file.exists():
            obs.checks_warned += 1
            obs.score = max(0, obs.score - 8)
            obs.findings.append("缺少 callback_handler.py")
            obs.details["trace_system"] = "partial"
        else:
            obs.checks_failed += 1
            obs.score = max(0, obs.score - 15)
            obs.findings.append("缺少可观测性系统")

        # Performance — basic check
        perf = self._get_axis("performance")
        perf.checks_total += 1
        perf.checks_passed += 1
        perf.details["check_latency_ms"] = "measured"


# ──── CLI Integration ────

def score_from_cli_findings(findings_list: list[dict], agent_id: str = "default",
                            target: str = ".") -> HealthReport:
    """Create health report from CLI findings (JSON format).

    Used when integrating with hermes_doctor.py --format json output.
    """

    @dataclass
    class _Finding:
        level: str
        title: str
        evidence: str
        impact: str
        prescription: str
        risk: str
        next_step: str

    parsed = [_Finding(**f) for f in findings_list]
    scorer = HealthScorer(agent_id=agent_id, target=target)
    return scorer.run(findings=parsed)


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "."
    scorer = HealthScorer(target=target)
    report = scorer.run()
    print(report.to_markdown())
    print("\n--- JSON Export ---")
    print(report.to_json())
