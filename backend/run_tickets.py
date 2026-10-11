"""Command-line way to run the agent team on tickets (the dashboard uses the API in main.py instead).

    python backend/run_tickets.py                   reset DB, then run every open ticket
    python backend/run_tickets.py --tickets 101,103 only those tickets
    python backend/run_tickets.py --no-reset        keep the current working DB

Agents only PREPARE payments / purchase orders (pending proposals); no money moves. Approving and
paying is done by a human through the API (POST /proposals/{id}/approve in main.py).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit  # noqa: E402
from db import reset_database  # noqa: E402
from models import TeamSession, TicketRun  # noqa: E402
from team import Team  # noqa: E402


def _system_log(run_id: str, step: str, **details) -> None:
    run = TicketRun(run_id=run_id, ticket_id=None, session=TeamSession(), usage=None, limits=None,
                    max_delegations=0, max_depth=0)
    audit.record(run, None, step, **details)
    audit.flush(run)


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickets", help="comma-separated ticket ids (default: every open ticket)")
    ap.add_argument("--no-reset", action="store_true", help="do not reset the database first")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    if not args.no_reset:
        reset_database()
        print("Database reset to original values.")
        _system_log("session-" + uuid.uuid4().hex[:8], "database_reset", source="data/campus_customs.db",
                    target="data/campus_customs_new.db")

    # No approval code: the human-only tools stay disabled, so this runner can only prepare payments.
    async with Team() as team:
        if args.tickets:
            ids = [int(x) for x in args.tickets.split(",")]
        else:
            ids = [t["id"] for t in (await team.call_mcp_direct("list_open_tickets", {}))["tickets"]]
        for tid in ids:
            print(f"\n=== Ticket {tid} ===")
            decision = await team.run_ticket(tid)
            run = team.last_run
            u = run.usage
            print(f"[{u.requests} model requests, {u.input_tokens} in / {u.output_tokens} out tokens, "
                  f"{run.delegations} delegations, MCP cache hits so far: {team.session.cache_hits}]")
            if decision is None:
                print(f"Boss run failed: {team.last_outcome}")
                continue
            print(f"{decision.status}: {decision.decision}")
            for p in decision.pending_human_approvals:
                print(f"  prepared: #{p.proposal_id} {p.kind} ${p.amount:.2f} {p.note}")
            for d in decision.drafts:
                print(f"  DRAFT to {d.to}: {d.subject}")
    print("\nPayments are only prepared. Approve them from the dashboard / API (POST /proposals/{id}/approve).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
