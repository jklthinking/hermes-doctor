"""Persist lightweight diagnostic run history for Hermes Doctor optional APIs."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class DoctorHistory:
    run_id: str
    checked_at: str
    passed: bool
    checks_total: int
    failed_checks: int
    summary: str


def _ensure_parent(path: str | Path) -> Path:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def connect(path: str | Path = "~/.hermes_doctor_cache/doctor_history.sqlite3") -> sqlite3.Connection:
    db_path = _ensure_parent(Path(path).expanduser())
    conn = sqlite3.connect(db_path.as_posix())
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS doctor_runs (
            run_id TEXT PRIMARY KEY,
            checked_at TEXT NOT NULL,
            passed INTEGER NOT NULL,
            checks_total INTEGER NOT NULL,
            failed_checks INTEGER NOT NULL,
            summary TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def save_run(
    run_id: str,
    passed: bool,
    checks: list[dict[str, Any]],
    db_path: str | Path = "~/.hermes_doctor_cache/doctor_history.sqlite3",
) -> DoctorHistory:
    conn = connect(db_path)
    total = len(checks)
    failed = len([item for item in checks if not item.get("ok", False)])
    summary = ", ".join(item.get("name", "") for item in checks if not item.get("ok", False))[:180]
    if not summary:
        summary = "all_checks_passed"
    checked_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT OR REPLACE INTO doctor_runs
        (run_id, checked_at, passed, checks_total, failed_checks, summary)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, checked_at, 1 if passed else 0, total, failed, summary),
    )
    conn.commit()
    conn.close()
    return DoctorHistory(
        run_id=run_id,
        checked_at=checked_at,
        passed=passed,
        checks_total=total,
        failed_checks=failed,
        summary=summary,
    )


def latest_runs(limit: int = 10, db_path: str | Path = "~/.hermes_doctor_cache/doctor_history.sqlite3") -> list[DoctorHistory]:
    conn = connect(db_path)
    rows = conn.execute(
        """
        SELECT run_id, checked_at, passed, checks_total, failed_checks, summary
        FROM doctor_runs
        ORDER BY checked_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [
        DoctorHistory(
            run_id=row["run_id"],
            checked_at=row["checked_at"],
            passed=bool(row["passed"]),
            checks_total=row["checks_total"],
            failed_checks=row["failed_checks"],
            summary=row["summary"],
        )
        for row in rows
    ]
