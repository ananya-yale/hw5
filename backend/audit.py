"""Append-only audit trail for the agent team: output/audit_trail.json.

The file is one JSON list. Every agent-loop step is added to a per-ticket
buffer by `record()` and written out by `flush()`. Flushing re-reads the file
and appends, so history from earlier runs is never wiped. The write goes to a
temp file and is renamed over the original, so a crash mid-write cannot corrupt
past history; if the file is ever found corrupt it is renamed aside (not
deleted) before a fresh list is started.

Entries hold tool arguments and results (shop data) but never credentials:
the Portkey key is only ever read into the HTTP client and the human approval
code never reaches any agent or log.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import AgentDeps, TicketRun

ROOT = Path(__file__).resolve().parent.parent
# CAMPUS_AUDIT_PATH lets tests write to a throwaway file; normal use is output/audit_trail.json.
AUDIT_PATH = Path(os.environ.get("CAMPUS_AUDIT_PATH") or ROOT / "output" / "audit_trail.json")

MAX_ARGS_CHARS = 800
MAX_RESULT_CHARS = 2000

_lock = threading.Lock()


def clip(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def record(run: TicketRun, deps: AgentDeps | None, step_type: str, actor: str | None = None, **details: Any) -> None:
    """Buffer one audit entry. `deps` is None for run-level / human / system steps (see `actor`)."""
    run.seq += 1
    entry = {
        "run_id": run.run_id,
        "seq": run.seq,
        "time": now_iso(),
        "ticket_id": run.ticket_id,
        "agent": deps.agent if deps else (actor or "system"),
        "depth": deps.depth if deps else 0,
        "delegated_by": deps.delegated_by if deps else None,
        "step": step_type,
    }
    entry.update({k: v for k, v in details.items() if v is not None})
    run.audit_buffer.append(entry)


def flush(run: TicketRun) -> None:
    """Append the buffered entries to the audit file and clear the buffer."""
    if not run.audit_buffer:
        return
    append_entries(run.audit_buffer)
    run.audit_buffer = []


def append_entries(entries: list[dict]) -> None:
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        rows: list = []
        if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size > 0:
            try:
                loaded = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
                rows = loaded if isinstance(loaded, list) else [loaded]
            except json.JSONDecodeError:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                AUDIT_PATH.replace(AUDIT_PATH.with_name(f"audit_trail.corrupt-{stamp}.json"))
        rows.extend(entries)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(AUDIT_PATH)


def read_entries() -> list[dict]:
    """All audit entries, oldest first. Safe to call while a run is writing."""
    with _lock:
        if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
            return []
        try:
            loaded = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return loaded if isinstance(loaded, list) else [loaded]
