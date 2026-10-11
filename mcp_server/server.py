"""Campus Customs MCP server.

Tools over data/campus_customs_new.db. Every value returned comes from the
database; if a row is missing, the tool says so instead of guessing.

Most tools are read-only. Money only moves through a three-step gate:
  1. propose_payment / propose_purchase_order  -> a *pending* proposal (no money moves)
  2. record_human_approval                     -> a human approves/rejects (needs the
                                                  approval code; never given to agents)
  3. pay_approved                              -> executes ONLY an approved proposal,
                                                  and refuses if cash would go negative
"""

import hmac
import os
import sqlite3
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

# CAMPUS_DB_PATH lets tests point the server at a throwaway copy; normal use is the working DB.
DB_PATH = Path(os.environ.get("CAMPUS_DB_PATH") or Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db")

mcp = FastMCP("campus-customs")

# Created lazily in the working copy (never in the original DB), so a reset to
# the original database also clears every proposal.
PROPOSALS_DDL = """
CREATE TABLE IF NOT EXISTS payment_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,            -- 'invoice' | 'rent' | 'purchase_order'
    ref_id INTEGER NOT NULL,       -- invoice id, lease id, or vendor id (purchase_order)
    vendor_id INTEGER,
    sku TEXT,
    size TEXT,
    qty INTEGER,
    amount REAL NOT NULL,
    status TEXT NOT NULL,          -- pending | approved | rejected | paid
    blocked_by TEXT,               -- comma-separated open invoice ids (purchase_order only)
    proposed_by TEXT,
    created_on TEXT,               -- desk.date_today when proposed
    approved_by TEXT,
    decided_on TEXT,
    note TEXT,
    ticket_id INTEGER              -- ticket whose run prepared it (stamped by the agent runner)
)
"""


def _ensure_proposals(conn: sqlite3.Connection) -> None:
    """Create the proposals table if needed, adding newer columns to an older copy."""
    conn.execute(PROPOSALS_DDL)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(payment_proposals)")}
    if "ticket_id" not in cols:
        conn.execute("ALTER TABLE payment_proposals ADD COLUMN ticket_id INTEGER")


def _code_error(approval_code: str) -> dict | None:
    """None if the code is valid; otherwise the error to return. Used by every human-only tool."""
    expected = os.environ.get("CAMPUS_APPROVAL_CODE", "")
    if not expected:
        return _error("Disabled: this server has no CAMPUS_APPROVAL_CODE configured.")
    if not hmac.compare_digest(approval_code.encode(), expected.encode()):
        return _error("Invalid approval code. Nothing was changed.")
    return None


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_rw() -> sqlite3.Connection:
    """Writable connection with manual transaction control (used only by money tools)."""
    conn = sqlite3.connect(DB_PATH.as_posix(), isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _has_proposals(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='payment_proposals'"
        ).fetchone()
        is not None
    )


def _committed(conn: sqlite3.Connection, exclude_id: int | None = None) -> list[sqlite3.Row]:
    """Proposals that are not yet paid and still reserve cash (pending or approved)."""
    if not _has_proposals(conn):
        return []
    return conn.execute(
        "SELECT * FROM payment_proposals WHERE status IN ('pending','approved') AND id != ? ORDER BY id",
        (exclude_id if exclude_id is not None else -1,),
    ).fetchall()


def _add_month(iso: str) -> str:
    d = date.fromisoformat(iso)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, monthrange(year, month)[1])).isoformat()


def _today(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT date_today FROM desk").fetchone()
    return row["date_today"] if row else None


def _error(message: str) -> dict:
    return {"found": False, "error": message}


@mcp.tool
def get_order_fulfillment_blockers(ticket_id: int) -> dict:
    """Ticket 101: why a customer order can't ship yet, and what is blocking it.

    Reads tickets, inventory, pricing, invoices, vendors, and desk. Starting
    from the ticket's SKU, size, and qty, it returns the stock shortfall, the
    list price of the order, and, if the ticket links an invoice, that
    invoice's amount, status, days overdue, and the vendor's lead time.
    """
    with _connect() as conn:
        ticket = conn.execute(
            "SELECT id, type, requester, subject, sku, size, qty, invoice_id "
            "FROM tickets WHERE id = ?",
            (ticket_id,),
        ).fetchone()
        if ticket is None:
            return _error(f"No ticket with id={ticket_id}")
        if ticket["sku"] is None or ticket["size"] is None or ticket["qty"] is None:
            return _error(f"Ticket {ticket_id} is not an order (no sku/size/qty)")

        stock = conn.execute(
            "SELECT name, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (ticket["sku"], ticket["size"]),
        ).fetchone()
        if stock is None:
            return _error(f"No inventory row for sku={ticket['sku']!r}, size={ticket['size']!r}")
        price = conn.execute(
            "SELECT list_price FROM pricing WHERE sku = ?", (ticket["sku"],)
        ).fetchone()

        result = {
            "found": True,
            "ticket_id": ticket["id"],
            "requester": ticket["requester"],
            "sku": ticket["sku"],
            "product_name": stock["name"],
            "size": ticket["size"],
            "qty_requested": ticket["qty"],
            "qty_on_hand": stock["qty"],
            "shortfall": max(0, ticket["qty"] - stock["qty"]),
            "order_total_at_list": (
                round(price["list_price"] * ticket["qty"], 2) if price else None
            ),
            "linked_invoice": None,
        }

        if ticket["invoice_id"] is not None:
            inv = conn.execute(
                "SELECT i.id, i.amount, i.due_date, i.status, i.description, "
                "v.name AS vendor_name, v.lead_days "
                "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (ticket["invoice_id"],),
            ).fetchone()
            if inv is not None:
                today = _today(conn)
                days_overdue = None
                if today is not None:
                    delta = (date.fromisoformat(today) - date.fromisoformat(inv["due_date"])).days
                    days_overdue = max(0, delta)
                result["date_today"] = today
                result["linked_invoice"] = {
                    **dict(inv),
                    "days_overdue": days_overdue,
                }
    return result


@mcp.tool
def check_rent_affordability(lease_id: int) -> dict:
    """Ticket 102: can the shop cover this rent and its open vendor invoices?

    Reads leases, cash_accounts, invoices, and desk. Returns the rent, days
    until it is due, the checking balance, the total of open invoices, and the
    cash left after rent alone and after rent plus every open invoice.
    """
    with _connect() as conn:
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due "
            "FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return _error(f"No lease with id={lease_id}")
        today = _today(conn)
        if today is None:
            return _error("desk table has no date_today")
        cash = conn.execute(
            "SELECT balance, date FROM cash_accounts WHERE name = 'checking'"
        ).fetchone()
        if cash is None:
            return _error("No 'checking' row in cash_accounts")
        open_invoices = conn.execute(
            "SELECT id, amount, due_date FROM invoices WHERE status = 'open' ORDER BY due_date"
        ).fetchall()

    rent = lease["monthly_rent"]
    invoices_total = sum(r["amount"] for r in open_invoices)
    after_rent = cash["balance"] - rent
    after_all = after_rent - invoices_total
    return {
        "found": True,
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": rent,
        "next_due": lease["next_due"],
        "date_today": today,
        "days_until_due": (date.fromisoformat(lease["next_due"]) - date.fromisoformat(today)).days,
        "checking_balance": cash["balance"],
        "balance_as_of": cash["date"],
        "open_invoices": [dict(r) for r in open_invoices],
        "open_invoices_total": invoices_total,
        "cash_after_rent": after_rent,
        "cash_after_rent_and_open_invoices": after_all,
        "can_cover_rent": after_rent >= 0,
        "can_cover_rent_and_open_invoices": after_all >= 0,
    }


@mcp.tool
def get_margin_for_discount(sku: str, size: str, qty: int) -> dict:
    """Ticket 103: how much room a bulk-discount request leaves, and whether stock covers it.

    Reads pricing and inventory. Returns unit cost, list price, per-unit
    margin, the break-even discount percent (the ceiling for any offer), the
    total profit at list price for qty units, and the stock shortfall. The
    database has no discount policy, so none is returned.
    """
    with _connect() as conn:
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        if price is None:
            return _error(f"No pricing row for sku={sku!r}")
        stock = conn.execute(
            "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        if stock is None:
            return _error(f"No inventory row for sku={sku!r}, size={size!r}")

    cost, list_price = price["unit_cost"], price["list_price"]
    margin = list_price - cost
    return {
        "found": True,
        "sku": sku,
        "size": size,
        "qty_requested": qty,
        "unit_cost": cost,
        "list_price": list_price,
        "margin_per_unit": round(margin, 2),
        "break_even_discount_percent": round(margin / list_price * 100, 2),
        "total_profit_at_list": round(margin * qty, 2),
        "qty_on_hand": stock["qty"],
        "shortfall": max(0, qty - stock["qty"]),
    }


@mcp.tool
def list_all_tickets() -> dict:
    """List every ticket, open or resolved, with its status. (Dashboard/backend use.)

    Reads tickets and desk. A ticket becomes 'resolved' when every payment
    prepared for it has been paid by a human-approved payment.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, "
            "status, notes, created_at FROM tickets ORDER BY id"
        ).fetchall()
        return {"found": True, "date_today": _today(conn), "tickets": [dict(r) for r in rows]}


@mcp.tool
def list_payment_proposals(status: str | None = None) -> dict:
    """List prepared payments/purchase orders (any status, or one status), newest last.

    Reads payment_proposals. (Dashboard/backend use; shows what is waiting for a human.)
    """
    with _connect() as conn:
        if not _has_proposals(conn):
            return {"found": True, "proposals": []}
        rows = conn.execute(
            "SELECT * FROM payment_proposals WHERE (? IS NULL OR status = ?) ORDER BY id", (status, status)
        ).fetchall()
        return {"found": True, "proposals": [_proposal_dict(r) for r in rows]}


@mcp.tool
def list_open_tickets() -> dict:
    """List every open ticket (the work queue) plus the shop's 'today'.

    Reads tickets and desk. Each ticket has its type, requester, subject, and
    the sku/size/qty/lease_id/invoice_id it points at.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, "
            "status, notes, created_at FROM tickets WHERE status = 'open' ORDER BY id"
        ).fetchall()
        return {"found": True, "date_today": _today(conn), "tickets": [dict(r) for r in rows]}


def _vendor_open_invoices(conn: sqlite3.Connection, vendor_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY id",
        (vendor_id,),
    ).fetchall()


@mcp.tool
def check_stock_and_restock_vendors(sku: str, size: str, qty: int = 1) -> dict:
    """Stock check for one SKU+size, the shortfall for qty units, and who could restock it.

    Reads inventory, pricing, vendors, invoices, and desk. Lists every vendor
    with its specialty, lead time, and whether it can ship new product right
    now: a vendor with any unpaid open invoice cannot. Judging which vendor's
    specialty fits the product is left to the caller; the database has no
    SKU-to-vendor mapping.
    """
    with _connect() as conn:
        stock = conn.execute(
            "SELECT name, qty, location FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        if stock is None:
            return _error(f"No inventory row for sku={sku!r}, size={size!r}")
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        today = _today(conn)
        shortfall = max(0, qty - stock["qty"])
        vendors = []
        for v in conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id"):
            open_inv = _vendor_open_invoices(conn, v["id"])
            vendors.append(
                {
                    **dict(v),
                    "open_invoice_ids": [r["id"] for r in open_inv],
                    "open_invoice_total": round(sum(r["amount"] for r in open_inv), 2),
                    "can_ship_new_product_now": len(open_inv) == 0,
                }
            )
    unit_cost = price["unit_cost"] if price else None
    return {
        "found": True,
        "date_today": today,
        "sku": sku,
        "product_name": stock["name"],
        "size": size,
        "location": stock["location"],
        "qty_requested": qty,
        "qty_on_hand": stock["qty"],
        "shortfall": shortfall,
        "unit_cost": unit_cost,
        "restock_cost_estimate": round(unit_cost * shortfall, 2) if unit_cost is not None and shortfall else 0.0,
        "restock_cost_basis": "pricing.unit_cost x shortfall (the database has no vendor quotes)",
        "vendors": vendors,
    }


@mcp.tool
def get_cash_and_open_invoices() -> dict:
    """The shop's money picture: checking balance, open invoices, and cash already spoken for.

    Reads cash_accounts, invoices, vendors, payments, payment_proposals, and
    desk. Invoices are 'overdue' when due_date is before desk.date_today.
    Pending/approved proposals count as committed cash, so
    available_after_commitments is what is genuinely free to propose against.
    """
    with _connect() as conn:
        today = _today(conn)
        cash = conn.execute(
            "SELECT balance, date FROM cash_accounts WHERE name = 'checking'"
        ).fetchone()
        if cash is None:
            return _error("No 'checking' row in cash_accounts")
        invoices = []
        for r in conn.execute(
            "SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date, i.description "
            "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.status = 'open' ORDER BY i.due_date"
        ):
            days = (date.fromisoformat(today) - date.fromisoformat(r["due_date"])).days
            invoices.append({**dict(r), "days_overdue": max(0, days), "is_overdue": days > 0})
        payments = [dict(r) for r in conn.execute("SELECT * FROM payments ORDER BY id")]
        committed = _committed(conn)
    committed_total = round(sum(r["amount"] for r in committed), 2)
    return {
        "found": True,
        "date_today": today,
        "checking_balance": cash["balance"],
        "balance_as_of": cash["date"],
        "open_invoices": invoices,
        "open_invoices_total": round(sum(i["amount"] for i in invoices), 2),
        "payments_made": payments,
        "unpaid_proposals": [
            {k: r[k] for k in ("id", "kind", "ref_id", "amount", "status")} for r in committed
        ],
        "committed_total": committed_total,
        "available_after_commitments": round(cash["balance"] - committed_total, 2),
    }


def _proposal_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["blocked_by_invoice_ids"] = (
        [int(x) for x in d["blocked_by"].split(",")] if d.get("blocked_by") else []
    )
    d.pop("blocked_by", None)
    return d


def _insert_proposal(conn: sqlite3.Connection, fields: dict) -> dict:
    """Shared tail of both propose_* tools. Caller holds a BEGIN IMMEDIATE transaction."""
    balance = conn.execute(
        "SELECT balance FROM cash_accounts WHERE name = 'checking'"
    ).fetchone()["balance"]
    available = balance - sum(r["amount"] for r in _committed(conn))
    if fields["amount"] > available + 1e-9:
        return {
            "found": True,
            "created": False,
            "reason": (
                f"Not enough free cash: needs ${fields['amount']:.2f} but only ${available:.2f} "
                f"is free (balance ${balance:.2f} minus cash already committed to other proposals)."
            ),
            "amount_needed": fields["amount"],
            "available_after_commitments": round(available, 2),
        }
    cur = conn.execute(
        "INSERT INTO payment_proposals (kind, ref_id, vendor_id, sku, size, qty, amount, status, "
        "blocked_by, proposed_by, created_on, note, ticket_id) VALUES (?,?,?,?,?,?,?,'pending',?,?,?,?,?)",
        (
            fields["kind"], fields["ref_id"], fields.get("vendor_id"), fields.get("sku"),
            fields.get("size"), fields.get("qty"), fields["amount"], fields.get("blocked_by"),
            fields["proposed_by"], fields["today"], fields.get("note"), fields.get("ticket_id"),
        ),
    )
    row = conn.execute("SELECT * FROM payment_proposals WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {
        "found": True,
        "created": True,
        "proposal": _proposal_dict(row),
        "cash_after_if_paid": round(balance - fields["amount"], 2),
        "next_step": "NOT PAID. A human must approve this proposal before pay_approved can run.",
    }


@mcp.tool
def propose_payment(
    kind: Literal["invoice", "rent"], ref_id: int, proposed_by: str, ticket_id: int | None = None
) -> dict:
    """Prepare (not make) a payment for human approval: a vendor invoice or a rent payment.

    ref_id is the invoice id (kind='invoice') or lease id (kind='rent'). The
    amount always comes from the database, never from the caller. Creates a
    'pending' proposal and moves no money. If an unpaid proposal for the same
    item already exists it is returned instead of making a duplicate. Refuses
    to prepare a payment the shop cannot cover.
    """
    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _ensure_proposals(conn)
        today = _today(conn)
        for r in _committed(conn):
            if r["kind"] == kind and r["ref_id"] == ref_id:
                conn.execute("COMMIT")
                return {"found": True, "created": False, "already_proposed": True,
                        "proposal": _proposal_dict(r)}
        if kind == "invoice":
            inv = conn.execute(
                "SELECT id, vendor_id, amount, status FROM invoices WHERE id = ?", (ref_id,)
            ).fetchone()
            if inv is None:
                conn.execute("ROLLBACK")
                return _error(f"No invoice with id={ref_id}")
            if inv["status"] != "open":
                conn.execute("ROLLBACK")
                return _error(f"Invoice {ref_id} is '{inv['status']}', not open; nothing to pay")
            fields = {"kind": "invoice", "ref_id": ref_id, "vendor_id": inv["vendor_id"],
                      "amount": inv["amount"]}
        else:
            lease = conn.execute(
                "SELECT id, monthly_rent FROM leases WHERE id = ?", (ref_id,)
            ).fetchone()
            if lease is None:
                conn.execute("ROLLBACK")
                return _error(f"No lease with id={ref_id}")
            fields = {"kind": "rent", "ref_id": ref_id, "amount": lease["monthly_rent"]}
        result = _insert_proposal(
            conn, {**fields, "proposed_by": proposed_by, "today": today, "ticket_id": ticket_id}
        )
        conn.execute("COMMIT" if result.get("created") else "ROLLBACK")
        return result
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


@mcp.tool
def propose_purchase_order(
    vendor_id: int, sku: str, size: str, qty: int, proposed_by: str, ticket_id: int | None = None
) -> dict:
    """Prepare (not place) a purchase order to restock a SKU+size, for human approval.

    The amount is qty x pricing.unit_cost (the database has no vendor quotes).
    Creates a 'pending' proposal and moves no money. If the vendor has unpaid
    open invoices the proposal is still prepared, but it is marked as blocked
    by those invoices: the vendor will not ship, and pay_approved will refuse
    it, until they are paid. Refuses to prepare an order the shop cannot cover.
    """
    if qty <= 0:
        return _error("qty must be positive")
    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _ensure_proposals(conn)
        today = _today(conn)
        vendor = conn.execute("SELECT id, name FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            conn.execute("ROLLBACK")
            return _error(f"No vendor with id={vendor_id}")
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        stock = conn.execute(
            "SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        if price is None or stock is None:
            conn.execute("ROLLBACK")
            return _error(f"No pricing/inventory row for sku={sku!r}, size={size!r}")
        for r in _committed(conn):
            if (r["kind"] == "purchase_order" and r["vendor_id"] == vendor_id
                    and r["sku"] == sku and r["size"] == size):
                conn.execute("COMMIT")
                return {"found": True, "created": False, "already_proposed": True,
                        "proposal": _proposal_dict(r)}
        blocking = [str(r["id"]) for r in _vendor_open_invoices(conn, vendor_id)]
        result = _insert_proposal(conn, {
            "kind": "purchase_order", "ref_id": vendor_id, "vendor_id": vendor_id, "sku": sku,
            "size": size, "qty": qty, "amount": round(price["unit_cost"] * qty, 2),
            "blocked_by": ",".join(blocking) or None, "proposed_by": proposed_by, "today": today,
            "ticket_id": ticket_id,
        })
        conn.execute("COMMIT" if result.get("created") else "ROLLBACK")
        return result
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


@mcp.tool
def record_human_approval(proposal_id: int, approver: str, approved: bool, approval_code: str) -> dict:
    """HUMAN-ONLY: record a person's approve/reject decision on a pending proposal.

    Requires the approval code, which only the human-facing approval step
    knows. It is never given to any agent, and agents are not offered this
    tool. If the server was started without a configured code (for example a
    plain .mcp.json connection), approval is disabled and this always refuses.
    """
    if (bad := _code_error(approval_code)) is not None:
        return bad
    if not approver.strip():
        return _error("approver (the human's name) is required")
    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if not _has_proposals(conn):
            conn.execute("ROLLBACK")
            return _error(f"No proposal with id={proposal_id}")
        row = conn.execute("SELECT * FROM payment_proposals WHERE id = ?", (proposal_id,)).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            return _error(f"No proposal with id={proposal_id}")
        if row["status"] != "pending":
            conn.execute("ROLLBACK")
            return _error(f"Proposal {proposal_id} is '{row['status']}', not pending")
        conn.execute(
            "UPDATE payment_proposals SET status = ?, approved_by = ?, decided_on = ? WHERE id = ?",
            ("approved" if approved else "rejected", approver.strip(), _today(conn), proposal_id),
        )
        conn.execute("COMMIT")
        updated = conn.execute("SELECT * FROM payment_proposals WHERE id = ?", (proposal_id,)).fetchone()
        return {"found": True, "proposal": _proposal_dict(updated)}
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


@mcp.tool
def pay_approved(proposal_id: int, approval_code: str) -> dict:
    """HUMAN-ONLY: execute a payment a human has already approved. The only tool that moves money.

    Needs the approval code (held only by the backend's approve route; never
    given to any agent, and agents are not offered this tool). Refuses unless the proposal's status is 'approved'. Also refuses if the
    checking balance is below the amount (no negative balances), if a
    purchase order's vendor still has unpaid open invoices, or if an invoice
    is no longer open. On success it, in one transaction: lowers
    cash_accounts.balance, records a payments row (with the approver), marks
    an invoice 'paid' or moves a lease's next_due forward one month, and marks
    the proposal 'paid'. When that leaves a ticket with no pending/approved
    proposals, the ticket is marked 'resolved'.
    """
    if (bad := _code_error(approval_code)) is not None:
        return bad
    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if not _has_proposals(conn):
            conn.execute("ROLLBACK")
            return _error(f"No proposal with id={proposal_id}")
        p = conn.execute("SELECT * FROM payment_proposals WHERE id = ?", (proposal_id,)).fetchone()
        if p is None:
            conn.execute("ROLLBACK")
            return _error(f"No proposal with id={proposal_id}")

        def refuse(reason: str) -> dict:
            conn.execute("ROLLBACK")
            return {"found": True, "paid": False, "refused": True, "reason": reason,
                    "proposal_status": p["status"]}

        if p["status"] != "approved":
            return refuse(f"Proposal {proposal_id} is '{p['status']}'; only human-approved proposals can be paid.")
        today = _today(conn)
        if p["kind"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (p["ref_id"],)).fetchone()
            if inv is None or inv["status"] != "open":
                return refuse(f"Invoice {p['ref_id']} is not open; nothing to pay.")
        elif p["kind"] == "purchase_order":
            still_open = [r["id"] for r in _vendor_open_invoices(conn, p["vendor_id"])]
            if still_open:
                return refuse(
                    f"Vendor {p['vendor_id']} still has unpaid open invoice(s) {still_open}; "
                    "it will not ship new product until they are paid."
                )
        balance = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name = 'checking'"
        ).fetchone()["balance"]
        if p["amount"] > balance + 1e-9:
            return refuse(
                f"Insufficient cash: ${p['amount']:.2f} needed but checking has ${balance:.2f}. "
                "Balances cannot go negative."
            )
        new_balance = round(balance - p["amount"], 2)
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = 'checking'", (new_balance, today)
        )
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES (?,?,?,?,?,?)",
            (p["kind"], p["ref_id"], p["amount"], "checking", today, p["approved_by"]),
        )
        if p["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (p["ref_id"],))
        elif p["kind"] == "rent":
            nd = conn.execute("SELECT next_due FROM leases WHERE id = ?", (p["ref_id"],)).fetchone()
            conn.execute(
                "UPDATE leases SET next_due = ? WHERE id = ?", (_add_month(nd["next_due"]), p["ref_id"])
            )
        conn.execute("UPDATE payment_proposals SET status = 'paid' WHERE id = ?", (proposal_id,))
        ticket_resolved = False
        if p["ticket_id"] is not None:
            left = conn.execute(
                "SELECT COUNT(*) AS n FROM payment_proposals WHERE ticket_id = ? "
                "AND status IN ('pending','approved')", (p["ticket_id"],),
            ).fetchone()["n"]
            if left == 0:
                conn.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (p["ticket_id"],))
                ticket_resolved = True
        conn.execute("COMMIT")
        return {
            "found": True, "paid": True, "proposal_id": proposal_id, "payment_id": cur.lastrowid,
            "kind": p["kind"], "ref_id": p["ref_id"], "amount": p["amount"],
            "approved_by": p["approved_by"], "paid_at": today, "new_checking_balance": new_balance,
            "ticket_id": p["ticket_id"], "ticket_resolved": ticket_resolved,
        }
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


@mcp.tool
def resolve_ticket(ticket_id: int, resolved_by: str, approval_code: str) -> dict:
    """HUMAN-ONLY: mark an open ticket resolved when no money is involved (or it is already settled).

    For tickets that end in a human decision rather than a payment (for example a
    discount request). Needs the approval code, so no agent can call it. Refuses if
    the ticket is not open, or if it still has pending/approved payments: those are
    settled by approving or rejecting them. Moves no money.
    """
    if (bad := _code_error(approval_code)) is not None:
        return bad
    if not resolved_by.strip():
        return _error("resolved_by (the human's name) is required")
    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")
        t = conn.execute("SELECT id, status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            conn.execute("ROLLBACK")
            return _error(f"No ticket with id={ticket_id}")
        if t["status"] != "open":
            conn.execute("ROLLBACK")
            return {"found": True, "resolved": False, "reason": f"Ticket {ticket_id} is already '{t['status']}'."}
        waiting = []
        if _has_proposals(conn):
            waiting = [r["id"] for r in conn.execute(
                "SELECT id FROM payment_proposals WHERE ticket_id = ? AND status IN ('pending','approved')",
                (ticket_id,),
            )]
        if waiting:
            conn.execute("ROLLBACK")
            return {"found": True, "resolved": False,
                    "reason": f"Payments {waiting} for this ticket are still waiting; approve or reject them first."}
        conn.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (ticket_id,))
        conn.execute("COMMIT")
        return {"found": True, "resolved": True, "ticket_id": ticket_id, "resolved_by": resolved_by.strip(),
                "resolved_on": _today(conn)}
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run()
