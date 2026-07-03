"""Bridge preflight diagnostics for Feishu/Lark coding-agent runtimes."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Iterable, Literal

Status = Literal["pass", "warn", "fail"]

@dataclass(frozen=True)
class DiagnosticFinding:
    check: str
    status: Status
    message: str
    remediation: str = ""

class BridgePreflightDoctor:
    def check_agent_binary(self, binary: str) -> DiagnosticFinding:
        path = which(binary)
        if path:
            return DiagnosticFinding("agent-binary", "pass", path)
        return DiagnosticFinding("agent-binary", "fail", f"{binary} not found", f"install or configure {binary}")

    def check_workspace(self, workspace: str) -> DiagnosticFinding:
        path = Path(workspace).expanduser()
        if path.is_dir():
            return DiagnosticFinding("workspace", "pass", str(path.resolve()))
        return DiagnosticFinding("workspace", "fail", f"missing workspace: {path}", "bind an existing workspace with /cd or /ws")

    def check_lark_profile_dir(self, config_dir: str | None) -> DiagnosticFinding:
        if not config_dir:
            return DiagnosticFinding("lark-cli-profile", "warn", "profile-local lark-cli dir not set", "set LARKSUITE_CLI_CONFIG_DIR per bridge profile")
        path = Path(config_dir).expanduser()
        return DiagnosticFinding("lark-cli-profile", "pass" if path.exists() else "warn", str(path), "run bridge preflight to project lark-cli profile")

    def summarize(self, findings: Iterable[DiagnosticFinding]) -> dict:
        rows = list(findings)
        return {"pass": sum(f.status == "pass" for f in rows), "warn": sum(f.status == "warn" for f in rows), "fail": sum(f.status == "fail" for f in rows)}
