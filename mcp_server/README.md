# Campus Customs MCP Server

A [FastMCP](https://gofastmcp.com) server that gives the Campus Customs agent team (and the ticket tools from Question 3) access to the shop data, so they can work the open support tickets without guessing.

**Database:** `data/campus_customs_new.db` (the working copy of `campus_customs.db`). Every value a tool returns comes from the database; a missing row gives an explicit error, never a guess. Reads open the DB read-only; only the money tools (`propose_*`, `record_human_approval`, `pay_approved`) write. Set `CAMPUS_DB_PATH` to point the server at a throwaway copy for testing.

**Run:** launched over stdio via `.mcp.json` at the project root (`venv/Scripts/python.exe mcp_server/server.py`). The agent team (`backend/`) starts its own copy of the server the same way. Smoke-test evidence for the first three tools is in `output/mcp_smoke.json`.

## Tools (13)

### Read tools

| Tool | Reads | Used for | What it does |
|---|---|---|---|
| `get_order_fulfillment_blockers(ticket_id)` | `tickets`, `inventory`, `pricing`, `invoices`, `vendors`, `desk` | ticket 101 | Stock shortfall for the order, its list-price total, and the linked vendor invoice's amount, status, days overdue, and the vendor's lead time. |
| `check_rent_affordability(lease_id)` | `leases`, `cash_accounts`, `invoices`, `desk` | ticket 102 | Rent, days until due, checking balance, open invoice total, and cash left after rent and after rent plus open invoices. |
| `get_margin_for_discount(sku, size, qty)` | `pricing`, `inventory` | ticket 103 | Unit cost, list price, per-unit margin, break-even discount percent, total profit at list for `qty` units, and the stock shortfall. |
| `list_open_tickets()` | `tickets`, `desk` | Boss, Customer Service | Every open ticket plus `date_today`. |
| `list_all_tickets()` | `tickets`, `desk` | backend | Every ticket, open or resolved, with its status. |
| `list_payment_proposals(status?)` | `payment_proposals` | backend | Prepared payments/purchase orders, optionally one status. |
| `check_stock_and_restock_vendors(sku, size, qty)` | `inventory`, `pricing`, `vendors`, `invoices`, `desk` | Inventory | Stock, shortfall, estimated restock cost, and every vendor with its lead time and whether it can ship now (it cannot while it has an unpaid open invoice). |
| `get_cash_and_open_invoices()` | `cash_accounts`, `invoices`, `vendors`, `payments`, `payment_proposals`, `desk` | Accounting | Checking balance, open invoices with days overdue, past payments, and cash still free after unpaid proposals. |

### Money tools (the approval gate)

Money moves in three steps, and only the last one changes the books:

1. `propose_payment` / `propose_purchase_order` prepare a **pending** proposal (nothing is paid).
2. A human approves or rejects it with `record_human_approval`.
3. `pay_approved` pays only an approved proposal.

| Tool | Writes | What it does |
|---|---|---|
| `propose_payment(kind, ref_id, proposed_by, ticket_id?)` | `payment_proposals` | Prepares a payment for an open vendor invoice (`kind='invoice'`) or a lease's rent (`kind='rent'`). The amount comes from the database. Returns the existing proposal if one is already unpaid; refuses if free cash cannot cover it. |
| `propose_purchase_order(vendor_id, sku, size, qty, proposed_by, ticket_id?)` | `payment_proposals` | Prepares a restock order priced at `unit_cost x qty` (there are no vendor quotes). Flags it as blocked by any open invoices the vendor has. Refuses if free cash cannot cover it. |
| `record_human_approval(proposal_id, approver, approved, approval_code)` | `payment_proposals` | Human-only. Records an approve/reject decision. Needs the `CAMPUS_APPROVAL_CODE` the server was started with, which only the backend (`backend/main.py`) knows; with no code configured (e.g. a plain `.mcp.json` connection) it always refuses. |
| `resolve_ticket(ticket_id, resolved_by, approval_code)` | `tickets` | Human-only. Marks an open ticket resolved when it ends in a decision rather than a payment (e.g. a discount request). Refuses if the ticket isn't open or still has pending/approved payments. Moves no money. |
| `pay_approved(proposal_id, approval_code)` | `cash_accounts`, `payments`, `invoices` or `leases`, `payment_proposals` | Human-only (same approval code) and the only tool that moves money. Refuses unless the proposal is approved, if checking would go negative, if an invoice is no longer open, or if a purchase order's vendor still has unpaid invoices. On success, in one transaction: lowers the balance, adds a `payments` row with the approver, marks the invoice `paid` (or moves the lease's `next_due` forward a month), marks the proposal `paid`, and marks the ticket `resolved` once none of its proposals are still pending or approved. |

`payment_proposals` is created in the working copy on first use and is not part of the original database, so resetting the database to `campus_customs.db` clears every proposal.
