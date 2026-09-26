"""Local AI decision history (Phase 2.7): evidence, not action.

Appends one JSON line per analyzed process per sampler pass to
logs/ai_decisions.jsonl (bounded with rotation). Records contain NO
username or other personal data — only what explainability needs:
identity (pid/name/arch), model vote, calibrated confidence, familiarity,
safety decision, reason, backend, timestamp.

These are AI decisions/recommendations ONLY. Nothing here acts on any
process. Read back via tail() (/api/decisions).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "ai_decisions.jsonl"

MAX_LINES = 5000
KEEP_LINES = 3000

SCHEMA = ("timestamp", "pid", "process", "architecture", "model_class",
          "raw_confidence", "familiarity", "familiarity_level",
          "final_confidence", "safety_state", "recommendation", "reason",
          "backend")


def record(row: dict, backend: str) -> dict:
    """Build a log record from an enriched row. Pure function (testable)."""
    ai = row.get("ai") or {}
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pid": row.get("pid"),
        "process": row.get("name") or "?",
        "architecture": row.get("arch") or "Unknown",
        "model_class": ai.get("model_class"),
        "raw_confidence": ai.get("raw_confidence"),
        "familiarity": ai.get("familiarity"),
        "familiarity_level": ai.get("familiarity_level"),
        "final_confidence": ai.get("final_confidence"),
        "safety_state": ai.get("safety_state"),
        "recommendation": ai.get("recommendation"),
        "reason": ai.get("override_reason") or (ai.get("why") or [""])[-1],
        "backend": backend,
    }


def append(rows: list[dict], backend: str, top_n: int = 40) -> int:
    """Append records for the top-N rows. Returns lines written."""
    LOG_DIR.mkdir(exist_ok=True)
    recs = [record(r, backend) for r in rows[:top_n] if r.get("ai")]
    if not recs:
        return 0
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        for rec in recs:
            f.write(json.dumps(rec) + "\n")
    _rotate()
    return len(recs)


def _rotate() -> None:
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return
    if len(lines) > MAX_LINES:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines[-KEEP_LINES:])


def log_record(rec: dict) -> None:
    """Append one prebuilt record (e.g. a simulation event)."""
    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    _rotate()


def tail(limit: int = 50) -> list[dict]:
    """Most recent records (newest last). Safe on missing/corrupt log."""
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    out = []
    for line in lines[-max(1, min(limit, 500)):]:
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if all(k in rec for k in ("timestamp", "process", "safety_state")):
            out.append(rec)
    return out
