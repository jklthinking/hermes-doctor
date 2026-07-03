"""Probe diagnostic runs for missing session and trace continuity."""
from __future__ import annotations

from typing import Iterable, Mapping


def probe_events(events: Iterable[Mapping[str, object]]) -> dict[str, object]:
    missing_session = []
    missing_trace = []
    for idx, event in enumerate(events):
        if not event.get("session_id"):
            missing_session.append(idx)
        if not event.get("trace_id"):
            missing_trace.append(idx)
    return {
        "events": idx + 1 if 'idx' in locals() else 0,
        "missing_session_indexes": missing_session,
        "missing_trace_indexes": missing_trace,
        "healthy": not missing_session and not missing_trace,
    }
