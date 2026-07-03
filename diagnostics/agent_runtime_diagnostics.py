"""Diagnostics for Hermes Agent runtime event flows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RuntimeIssue:
    severity: str
    code: str
    message: str


def diagnose_transition_drift(primary: dict[str, set[str]], secondary: dict[str, set[str]]) -> list[RuntimeIssue]:
    issues: list[RuntimeIssue] = []
    for state in sorted(set(primary) | set(secondary)):
        left = primary.get(state, set())
        right = secondary.get(state, set())
        if left != right:
            issues.append(RuntimeIssue("critical", "transition_drift", f"{state}: {sorted(left)} != {sorted(right)}"))
    return issues


def diagnose_pending_events(events: Iterable[dict], *, stale_after_seconds: int = 300) -> list[RuntimeIssue]:
    issues: list[RuntimeIssue] = []
    for event in events:
        idle = int(event.get("idle_seconds", 0))
        attempts = int(event.get("delivery_count", 1))
        event_id = event.get("id", "unknown")
        if idle >= stale_after_seconds:
            issues.append(RuntimeIssue("warning", "stale_pending_event", f"{event_id} idle for {idle}s"))
        if attempts >= 5:
            issues.append(RuntimeIssue("critical", "repeated_delivery", f"{event_id} delivered {attempts} times"))
    return issues


def diagnose_flow_log(item: dict) -> list[RuntimeIssue]:
    issues: list[RuntimeIssue] = []
    state = item.get("state")
    flow_log = item.get("flow_log") or []
    if state not in {"intake", "planning"} and not flow_log:
        issues.append(RuntimeIssue("critical", "missing_flow_log", "non-initial item has no flow log"))
    if state == "pending_confirmation" and not item.get("pending_confirmation"):
        issues.append(RuntimeIssue("critical", "missing_confirmation_payload", "pending confirmation without payload"))
    return issues
