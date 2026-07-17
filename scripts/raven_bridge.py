#!/usr/bin/env python3
"""Wave-7 Raven bridge PoC.

Entry point for the minimal memory-bridge smoke check.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from memory_bridge import FileMemoryBackend, make_backend


DEFAULT_TOP_K = 3


async def run_smoke(repo_root: Path) -> int:
    backend = make_backend(repo_root)
    await backend.start()
    try:
        await backend.store(
            session_id="wave7-smoke",
            messages=[
                {"role": "user", "content": "Raven bridge smoke test"},
                {"role": "assistant", "content": "记忆桥接已接入"},
            ],
            user_id="wave7-user",
        )
        await backend.feedback(
            {
                "kind": "smoke-feedback",
                "ids": ["smoke-001"],
                "status": "ok",
            }
        )

        hits = await backend.recall(
            "Raven 桥接",
            user_id="wave7-user",
            top_k=DEFAULT_TOP_K,
        )

        payload = {
            "status": "ok",
            "repo": repo_root.name,
            "top_k": DEFAULT_TOP_K,
            "hit_count": len(hits),
            "hits": [
                {"text": h.text, "score": h.score, "metadata": h.metadata} for h in hits
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    finally:
        await backend.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Wave-7 Raven bridge smoke")
    parser.add_argument("--repo", default=str(Path.cwd()), help="repository root")
    parser.add_argument("--smoke", action="store_true", help="run smoke flow")
    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    if not args.smoke:
        print("请带 --smoke 运行。")
        return 0
    return asyncio.run(run_smoke(repo_root))


if __name__ == "__main__":
    raise SystemExit(main())
