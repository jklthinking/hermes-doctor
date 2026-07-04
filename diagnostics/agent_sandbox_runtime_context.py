"""Sandbox runtime context builder for diagnosis-first agent health checks."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Any

SECRET_MARKERS = ("token", "secret", "password", "api_key", "authorization")


@dataclass
class SandboxRuntimeContext:
    workspace: str
    profile: str
    toolsets: list[str] = field(default_factory=list)
    network_enabled: bool = False
    writable_paths: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)

    def redacted_environment(self) -> dict[str, str]:
        redacted: dict[str, str] = {}
        for key, value in self.environment.items():
            if any(marker in key.lower() for marker in SECRET_MARKERS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = value
        return redacted


def build_sandbox_info(context: SandboxRuntimeContext) -> dict[str, Any]:
    return {
        "workspace": context.workspace,
        "profile": context.profile,
        "toolsets": sorted(set(context.toolsets)),
        "network_enabled": context.network_enabled,
        "writable_paths": sorted(context.writable_paths),
        "environment": context.redacted_environment(),
    }


def diagnose_runtime_context(info: Mapping[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    workspace = Path(str(info.get("workspace", "")))
    if not workspace.is_absolute():
        findings.append({"code": "workspace_not_absolute", "severity": "medium"})
    if info.get("network_enabled") and "web" not in set(info.get("toolsets") or []):
        findings.append({"code": "network_without_web_toolset", "severity": "low"})
    for path in info.get("writable_paths") or []:
        if str(path) in {"/", "/root", "/root/.hermes"}:
            findings.append({"code": "overbroad_writable_path", "severity": "high"})
    return findings


def sandbox_health_endpoint_payload(context: SandboxRuntimeContext) -> dict[str, Any]:
    info = build_sandbox_info(context)
    findings = diagnose_runtime_context(info)
    return {"ok": not any(f["severity"] == "high" for f in findings), "sandbox": info, "findings": findings}
