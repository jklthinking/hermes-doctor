"""Hermes Doctor optional API service entrypoint.

The API is opt-in and independent from the existing one-click path.
Set FASTAPI-related deps before enabling:

  pip install fastapi uvicorn
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
from dataclasses import asdict
from typing import Any

from history_store import DoctorHistory, latest_runs, save_run

try:
    from fastapi import FastAPI
except Exception:
    FastAPI = None  # type: ignore

from doctor import ROOT, collect_run_report


def build_app() -> Any:
    if FastAPI is None:
        raise RuntimeError("请先安装 fastapi: pip install fastapi uvicorn")

    app = FastAPI(title="hermes-doctor api", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "hermes-doctor"}

    @app.get("/diag")
    def diag() -> dict[str, Any]:
        report = collect_run_report(ROOT)
        run_id = hashlib.sha1((str(ROOT) + report["checked_at"]).encode()).hexdigest()[:16]
        rec = save_run(
            run_id=run_id,
            passed=report["passed"],
            checks=report["checks"],
            db_path=os.getenv("HERMES_DOCTOR_HISTORY_DB", "~/.hermes_doctor_cache/doctor_history.sqlite3"),
        )
        return {
            "passed": report["passed"],
            "run_id": rec.run_id,
            "checked_at": rec.checked_at,
            "checks_total": rec.checks_total,
            "failed_checks": rec.failed_checks,
            "summary": rec.summary,
            "checks": report["checks"],
        }

    @app.get("/diag/latest")
    def diag_latest(limit: int = 10):
        return [asdict(item) for item in latest_runs(limit=limit, db_path=os.getenv("HERMES_DOCTOR_HISTORY_DB", "~/.hermes_doctor_cache/doctor_history.sqlite3"))]

    @app.post("/doctor/run")
    def run_smoke() -> dict[str, Any]:
        """Run smoke checks as lightweight webhook trigger."""
        try:
            cp = subprocess.run(
                ["python3", str(ROOT / "scripts/smoke.py")],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {"ok": True, "stdout": cp.stdout[-2000:]}
        except subprocess.CalledProcessError as exc:
            return {"ok": False, "stderr": (exc.stderr or "")[-2000:]}

    return app


def main() -> int:
    if FastAPI is None:
        raise RuntimeError("请先安装 fastapi: pip install fastapi uvicorn")

    parser = argparse.ArgumentParser(description="Hermes Doctor API 服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8740)
    args = parser.parse_args()

    import uvicorn

    app = build_app()
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
