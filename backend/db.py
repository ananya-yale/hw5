"""Working-database housekeeping shared by the API and the command-line runner."""

import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
# CAMPUS_DB_PATH matches the MCP server's override, so tests can use a throwaway working copy.
WORKING_DB = Path(os.environ.get("CAMPUS_DB_PATH") or ROOT / "data" / "campus_customs_new.db")


# The boss's last decision for each ticket, kept so the dashboard still shows it after a backend restart.
# It describes the current run of the database, so a reset clears it.
DECISIONS_PATH = Path(os.environ.get("CAMPUS_DECISIONS_PATH") or ROOT / "output" / "ticket_decisions.json")


def load_decisions() -> dict[int, dict]:
    try:
        return {int(k): v for k, v in json.loads(DECISIONS_PATH.read_text(encoding="utf-8")).items()}
    except (OSError, ValueError):
        return {}


def save_decision(ticket_id: int, decision: dict) -> None:
    decisions = load_decisions()
    decisions[ticket_id] = decision
    DECISIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DECISIONS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(decisions, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(DECISIONS_PATH)


def reset_database() -> None:
    """Restore the working DB to the original values.

    Also drops anything added to the working copy (payment proposals, payments,
    paid invoices, resolved tickets). The original DB is never modified.
    """
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    DECISIONS_PATH.unlink(missing_ok=True)
