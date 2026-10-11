"""Campus Customs backend API (FastAPI) for the dashboard.

Start it from the backend/ folder:

    uvicorn main:app --reload --port 8000        (then open http://localhost:8000/docs)

One `Team` (the agents plus a single connection to the MCP server) is created when
the server starts and shared by every request. All shop facts here come from the
MCP server, and money only moves in `approve`: agents prepare payments, a human
clicks approve, and this module is the only thing that holds the approval code
the MCP server requires for `record_human_approval` and `pay_approved`.
"""

from __future__ import annotations

import asyncio
import secrets
import sys
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, Query, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

import audit  # noqa: E402
from db import load_decisions, reset_database, save_decision  # noqa: E402
from models import ApprovalRequest, ResolveRequest, TeamSession, TicketRun  # noqa: E402
from team import Team  # noqa: E402

# Origins the React dev server is likely to use.
FRONTEND_ORIGINS = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:3000", "http://127.0.0.1:3000",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The approval code lives only in this process's memory. It is handed to the MCP server so the
    # human-only tools can check it, and it is never given to an agent or written anywhere.
    code = secrets.token_hex(16)
    async with Team(approval_code=code) as team:
        app.state.team = team
        app.state.approval_code = code
        app.state.run_lock = asyncio.Lock()    # one agent run at a time
        app.state.money_lock = asyncio.Lock()  # one approval/payment at a time
        app.state.running_ticket = None
        app.state.decisions = load_decisions()  # ticket_id -> last BossDecision (as JSON); survives restarts
        yield


app = FastAPI(title="Campus Customs backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"],
)


# --------------------------------------------------------------------------- helpers


async def _mcp(request: Request, tool: str, args: dict | None = None) -> dict:
    result = await request.app.state.team.call_mcp_direct(tool, args or {})
    if isinstance(result, dict) and result.get("found") is False:
        raise HTTPException(status_code=404, detail=result.get("error", "not found"))
    return result


def _log_human(step: str, ticket_id: Optional[int] = None, **details: Any) -> None:
    """Write a human/backend action (approval, payment, reset) to the audit trail."""
    run = TicketRun(run_id="api-" + uuid.uuid4().hex[:8], ticket_id=ticket_id, session=TeamSession(),
                    usage=None, limits=None, max_delegations=0, max_depth=0)
    audit.record(run, None, step, actor="human", **details)
    audit.flush(run)


def _describe(e: dict) -> str:
    """One readable line for the board: what an agent said or which tool it used."""
    who, step = e.get("agent", "?"), e.get("step", "")
    if step == "agent_start":
        return f"{who} started: {e.get('request', '')}"
    if step == "delegation":
        return f"{who} asked {e.get('to')}: {e.get('request', '')}"
    if step == "delegation_cache_hit":
        return f"{who} re-asked {e.get('to')} (answered from cache)"
    if step == "tool_call":
        return f"{who} used tool {e.get('tool')} {e.get('args', '')}"
    if step == "tool_result":
        return f"{e.get('tool')} returned: {e.get('result', '')[:300]}"
    if step == "model_text":
        return f"{who} said: {e.get('text', '')}"
    if step == "final_output":
        return f"{who} gave its answer: {e.get('args', '')[:400]}"
    if step == "agent_end":
        return f"{who} finished"
    if step == "agent_error":
        return f"{who} hit an error: {e.get('error', '')}"
    if step == "run_start":
        return f"run started for ticket {e.get('ticket_id')}"
    if step == "run_end":
        return f"run ended for ticket {e.get('ticket_id')}: {e.get('outcome', '')}"
    if step == "human_decision":
        return f"{e.get('approver')} {'approved' if e.get('approved') else 'rejected'} proposal {e.get('proposal_id')}"
    if step == "payment_attempt":
        return f"payment attempt for proposal {e.get('proposal_id')}: {e.get('result', '')[:300]}"
    if step == "ticket_resolved":
        note = f': "{e.get("note")}"' if e.get("note") else ""
        return f"{e.get('approver')} marked ticket {e.get('ticket_id')} resolved{note}"
    if step == "database_reset":
        return "database reset to original values"
    return f"{who}: {step}"


# --------------------------------------------------------------------------- routes


@app.get("/tickets")
async def list_tickets(request: Request) -> dict:
    """The tickets with status open/resolved, their prepared payments, and the boss's last decision."""
    data = await _mcp(request, "list_all_tickets")
    proposals = (await _mcp(request, "list_payment_proposals"))["proposals"]
    by_ticket: dict[int, list] = defaultdict(list)
    for p in proposals:
        by_ticket[p.get("ticket_id")].append(p)
    tickets = [
        {
            **t,
            "proposals": by_ticket.get(t["id"], []),
            "last_decision": request.app.state.decisions.get(t["id"]),
            "running": request.app.state.running_ticket == t["id"],
        }
        for t in data["tickets"]
    ]
    return {"date_today": data["date_today"], "tickets": tickets}


@app.post("/tickets/{ticket_id}/run")
async def run_ticket(ticket_id: int, request: Request) -> dict:
    """Run the agent team on one ticket. Agents only prepare payments; nothing is paid."""
    state = request.app.state
    tickets = (await _mcp(request, "list_all_tickets"))["tickets"]
    ticket = next((t for t in tickets if t["id"] == ticket_id), None)
    if ticket is None:
        raise HTTPException(404, f"No ticket with id={ticket_id}")
    if ticket["status"] == "resolved":
        raise HTTPException(409, f"Ticket {ticket_id} is already resolved")
    if state.run_lock.locked():
        raise HTTPException(409, f"An agent run is already in progress (ticket {state.running_ticket})")
    async with state.run_lock:
        state.running_ticket = ticket_id
        try:
            decision = await state.team.run_ticket(ticket_id)
        finally:
            state.running_ticket = None
    run = state.team.last_run
    usage = {"requests": run.usage.requests, "input_tokens": run.usage.input_tokens,
             "output_tokens": run.usage.output_tokens}
    if decision is None:
        raise HTTPException(502, {"error": state.team.last_outcome, "run_id": run.run_id, "usage": usage})
    state.decisions[ticket_id] = decision.model_dump(mode="json")
    save_decision(ticket_id, state.decisions[ticket_id])
    return {"ticket_id": ticket_id, "run_id": run.run_id, "decision": state.decisions[ticket_id],
            "delegations": run.delegations, "usage": usage}


@app.post("/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: int, body: ResolveRequest, request: Request) -> dict:
    """A human closes a ticket that ends in a decision, not a payment (e.g. the discount request).

    Refused (409) if the ticket still has payments waiting; settle those with approve/reject first.
    Moves no money.
    """
    state = request.app.state
    async with state.money_lock:
        result = await _mcp(request, "resolve_ticket", {
            "ticket_id": ticket_id, "resolved_by": body.approver, "approval_code": state.approval_code,
        })
        if not result.get("resolved"):
            raise HTTPException(409, result.get("reason") or result.get("error") or "Could not resolve")
        _log_human("ticket_resolved", ticket_id, approver=body.approver, note=body.note or None)
    return {**result, "note": body.note}


@app.get("/events")
async def recent_events(
    after: Optional[int] = Query(None, description="Return only events after this index (from next_after)"),
    limit: int = Query(50, ge=1, le=500),
    ticket_id: Optional[int] = Query(None, description="Only events for this ticket"),
) -> dict:
    """Recent agent events (what they said, which tools they used) for the board to poll.

    First call: omit `after` to get the latest `limit` events. Then pass the returned `next_after`
    on each refresh to get only what is new.
    """
    indexed = [(i, e) for i, e in enumerate(audit.read_entries())]
    if ticket_id is not None:
        indexed = [(i, e) for i, e in indexed if e.get("ticket_id") == ticket_id]
    if after is not None:
        indexed = [(i, e) for i, e in indexed if i > after][:limit]
    else:
        indexed = indexed[-limit:]
    events = [{"index": i, "message": _describe(e), **e} for i, e in indexed]
    next_after = events[-1]["index"] if events else (after if after is not None else -1)
    return {"events": events, "next_after": next_after}


@app.get("/proposals")
async def list_proposals(
    request: Request, status: Optional[str] = Query(None, description="pending | approved | rejected | paid"),
) -> dict:
    """Payments and purchase orders the agents prepared, waiting for (or past) a human decision."""
    return await _mcp(request, "list_payment_proposals", {"status": status})


async def _decide(request: Request, proposal_id: int, body: ApprovalRequest, approve: bool) -> dict:
    state = request.app.state
    code = state.approval_code
    async with state.money_lock:
        proposals = (await _mcp(request, "list_payment_proposals"))["proposals"]
        p = next((x for x in proposals if x["id"] == proposal_id), None)
        if p is None:
            raise HTTPException(404, f"No proposal with id={proposal_id}")
        if p["status"] == "pending":
            rec = await _mcp(request, "record_human_approval", {
                "proposal_id": proposal_id, "approver": body.approver, "approved": approve,
                "approval_code": code,
            })
            _log_human("human_decision", p.get("ticket_id"), proposal_id=proposal_id, kind=p["kind"],
                       amount=p["amount"], approver=body.approver, approved=approve)
            p = rec["proposal"]
        elif not (approve and p["status"] == "approved"):
            # An already-approved proposal may be re-approved to retry a payment that was refused
            # (e.g. a purchase order that was waiting on a vendor invoice). Nothing else is allowed.
            raise HTTPException(409, f"Proposal {proposal_id} is '{p['status']}', not pending")
        if not approve:
            return {"proposal": p, "approved": False, "paid": False}

        result = await _mcp(request, "pay_approved", {"proposal_id": proposal_id, "approval_code": code})
        _log_human("payment_attempt", p.get("ticket_id"), proposal_id=proposal_id,
                   result=audit.clip({k: v for k, v in result.items() if k != "approval_code"}, 800))
        if not result.get("paid"):
            raise HTTPException(409, {
                "approved": True, "paid": False, "proposal_id": proposal_id,
                "reason": result.get("reason") or result.get("error"),
                "note": "Your approval is recorded; approve again once the blocker is cleared to retry.",
            })
        return {"approved": True, **result}


@app.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: int, body: ApprovalRequest, request: Request) -> dict:
    """A human clicked approve: record the approval and pay it. The ONLY route that changes cash.

    Refuses (409) if cash would go negative, or if a purchase order's vendor still has an unpaid
    invoice (pay that invoice first, then approve the order again).
    """
    return await _decide(request, proposal_id, body, approve=True)


@app.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: int, body: ApprovalRequest, request: Request) -> dict:
    """A human clicked reject: record the decision. No money moves."""
    return await _decide(request, proposal_id, body, approve=False)


@app.get("/cash")
async def current_cash(request: Request) -> dict:
    """Current checking balance (cash_accounts), plus how much of it is reserved by unpaid proposals."""
    d = await _mcp(request, "get_cash_and_open_invoices")
    return {
        "account": "checking",
        "checking_balance": d["checking_balance"],
        "balance_as_of": d["balance_as_of"],
        "committed_total": d["committed_total"],
        "available_after_commitments": d["available_after_commitments"],
        "date_today": d["date_today"],
    }


@app.post("/reset")
async def reset(request: Request) -> dict:
    """Reset the database to its original values for a fresh run. The audit trail is kept."""
    state = request.app.state
    if state.run_lock.locked():
        raise HTTPException(409, f"Cannot reset while an agent run is in progress (ticket {state.running_ticket})")
    async with state.money_lock:
        reset_database()
        state.team.session.read_cache.clear()
        state.decisions.clear()
        _log_human("database_reset", source="data/campus_customs.db", target="data/campus_customs_new.db")
    return {"reset": True, **(await current_cash(request))}
