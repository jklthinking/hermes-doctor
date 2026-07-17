#!/usr/bin/env python3
"""Raven-like memory bridge helpers for Wave-7 PoC.

This module intentionally keeps a tiny surface:
- Memory record model compatible with Raven-style concepts (`text`, `score`, `metadata`).
- File-backed backend implementing recall/store/feedback/start/stop.

The design is deliberately conservative:
- No external dependencies
- No main agent flow changed
- Pure additive and fully removable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import uuid
from datetime import datetime, timezone


@dataclass(frozen=True)
class Memory:
    """One memory hit used by the PoC memory bridge."""

    text: str
    score: float = 0.0
    metadata: dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


def _normalize_text(value: str) -> str:
    return (value or "").strip().lower()


def _from_dict(raw: dict[str, Any]) -> Memory:
    if not isinstance(raw, dict):
        raw = {}
    return Memory(
        text=str(raw.get("text", "")),
        score=float(raw.get("score", 0.0) or 0.0),
        metadata=dict(raw.get("metadata", {})),
    )


class FileMemoryBackend:
    """Small PoC backend: persisted as one JSON record per line."""

    def __init__(self, store_path: Path) -> None:
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def _read_lines(self) -> list[dict[str, Any]]:
        if not self.store_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.store_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception as exc:
                    rows.append(
                        {
                            "_invalid_line": line_no,
                            "text": f"invalid json line: {exc}",
                            "score": 0.0,
                            "metadata": {"source": "memory_bridge", "line": line_no},
                        }
                    )
        return rows

    def _append(self, record: dict[str, Any]) -> None:
        with self.store_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def recall(
        self,
        query: str,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        top_k: int = 5,
    ) -> list[Memory]:
        q = _normalize_text(query)
        rows = self._read_lines()
        hits: list[tuple[float, Memory]] = []
        for row in rows:
            hit = _from_dict(row)
            hay = _normalize_text(hit.text)
            score = hit.score
            if q and q in hay:
                score += 1.0
            meta_user = row.get("metadata", {}).get("user_id")
            meta_agent = row.get("metadata", {}).get("agent_id")
            if user_id and meta_user and meta_user != user_id:
                continue
            if agent_id and meta_agent and meta_agent != agent_id:
                continue
            hits.append((score, hit))
        hits.sort(key=lambda pair: pair[0], reverse=True)
        hits = hits[:top_k]
        return [hit for _s, hit in hits]

    async def store(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        top_k: int | None = None,
    ) -> None:
        del top_k
        record = {
            "id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "user_id": user_id,
            "agent_id": agent_id,
            "messages": messages,
            "type": "store",
            "text": " ".join(m.get("content", "") for m in messages if isinstance(m, dict) and m.get("content")),
        }
        self._append(record)

    async def feedback(self, payload: dict[str, Any]) -> None:
        record = {
            "id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "feedback",
            "payload": payload,
        }
        self._append(record)


def make_backend(repo_root: Path) -> FileMemoryBackend:
    path = repo_root / "references" / "wave7_raven_memory_store.jsonl"
    return FileMemoryBackend(path)
