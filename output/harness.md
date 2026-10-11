# Campus Customs Harness

The reference sheet for the Campus Customs agent project: the database tables, the agents, the MCP tools they use, the backend API, the React dashboard, and the safety rules.

Working DB: `data/campus_customs_new.db` (copy of `data/campus_customs.db`, which is never modified). Snapshot "today" is 2026-08-31 (`desk.date_today`); it is the shop's "today" and the threshold for anything overdue. The working copy is reset to the original before every fresh run.

**How the pieces fit:** the React dashboard (`frontend/`) calls the FastAPI backend (`backend/main.py`), which runs the Pydantic AI agent team (`backend/`). The agents get every shop fact from the MCP server (`mcp_server/server.py`) over the working DB. Agents only *prepare* payments; a human approves them in the dashboard, and that is the only way cash changes.

**Where things are:** `output/audit_trail.json` (every agent step, appended), `output/desk_tickets.html` (expected vs actual, and the cash itemization), `output/resolved_tickets.json` (per-ticket results), `output/resolved_board.html` (screenshots of the board), `output/design.md` (dashboard design), `output/ticket_decisions.json` (the boss's latest decision per ticket, so the dashboard survives a backend restart), `AI_prompts.md` (every prompt, in order).

## tickets
Fields: `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`
- Why it matters: the work queue. Every agent starts from a ticket; `type` (`customer_order`, `rent_notice`, `price_override`) is the routing signal, and `sku`/`size`/`lease_id`/`invoice_id` point to the rows the agent must check.

## inventory
Fields: `sku`, `name`, `size`, `qty`, `location`
- Why it matters: ground truth for stock. An order agent checks `qty` per (sku, size) before promising anything and uses `location` for picking.

## pricing
Fields: `sku`, `unit_cost`, `list_price`
- Why it matters: gives margin (`list_price - unit_cost`), which any discount or price-override agent needs to stay profitable.

## vendors
Fields: `id`, `name`, `specialty`, `lead_days`
- Why it matters: who can restock or ship and how fast (`lead_days`), so agents can promise realistic delivery dates.

## invoices
Fields: `id`, `vendor_id`, `amount`, `due_date`, `status`, `description`
- Why it matters: money owed to vendors. Agents compare `due_date` to today and weigh `amount` against cash before paying anything.

## leases
Fields: `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`
- Why it matters: fixed recurring obligation. Rent notices link here, and a rent agent needs `monthly_rent` and `next_due` to plan cash.

## cash_accounts
Fields: `name`, `balance`, `date`
- Why it matters: the spending limit. Any agent that pays something must check the balance first so rent plus invoices don't overdraw it.

## payments
Fields: `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`
- Why it matters: the record of money out (empty after a reset). `kind` is `invoice`, `rent`, or `purchase_order`; `ref_id` ties a payment to an invoice, lease, or vendor, and `approved_by` records the human who authorized it.

## desk
Fields: `date_today`, `notes`
- Why it matters: gives agents the current date (so "overdue" and "due in 2 days" are computed consistently) and a place for the owner's notes.

## payment_proposals (added by the MCP server, working copy only)
Fields: `id`, `kind` (`invoice` | `rent` | `purchase_order`), `ref_id`, `vendor_id`, `sku`, `size`, `qty`, `amount`, `status` (`pending` -> `approved`/`rejected` -> `paid`), `blocked_by`, `proposed_by`, `ticket_id`, `created_on`, `approved_by`, `decided_on`, `note`
- Why it matters: the approval gate. Agents can only *prepare* a payment or purchase order here; a human approves it; only then can `pay_approved` move money. Pending/approved proposals also reserve cash so agents cannot over-commit. The table is created lazily and disappears on reset, so the original DB is never altered.

## Agent team

Built with Pydantic AI in `backend/`. Every agent runs on **gpt-6-luna through Portkey** (`backend/team.py`, `MODEL_NAME`; the key is read from the environment and never logged). Prompts are in `backend/prompts/<agent>.md`, output types in `backend/models.py`, one file per agent in `backend/`. Shop facts come **only** from the MCP server; each agent sees just the MCP tools listed below plus `ask_<teammate>` tools.

| Agent | File | Job | MCP tools it can use | Output |
|---|---|---|---|---|
| Boss | `backend/boss.py` | Reads the ticket, delegates, makes the final decision | `list_open_tickets` | `BossDecision` |
| Inventory | `backend/inventory.py` | Stock by SKU+size, shortfalls, vendors that can restock | `check_stock_and_restock_vendors`, `get_order_fulfillment_blockers` | `InventoryReport` |
| Accounting | `backend/accounting.py` | Cash, invoices, margins; prepares payments/purchase orders for human approval | `get_cash_and_open_invoices`, `get_margin_for_discount`, `propose_payment`, `propose_purchase_order` (no tool that pays) | `AccountingReport` |
| Facilities | `backend/facilities.py` | Leases, rent, shop-space logistics | `check_rent_affordability` | `FacilitiesReport` |
| Customer Service | `backend/customer_service.py` | Drafts replies; can never send | `list_open_tickets` | `CustomerServiceReport` (drafts) |

**Delegation (full connectivity).** All five agents can ask each other. The only hidden option is asking someone who is already waiting on you (so specialists cannot call the boss while the boss is waiting on them). Token-saving guards: no ping-pong loops; max depth 2 and 8 delegations per ticket; delegates return small structured reports; identical delegation requests and identical MCP reads are answered from cache (cleared by any write); one shared budget per ticket (30 model requests / 150k tokens); low reasoning effort. A typical ticket uses 10-13 model requests (about 15-20k input tokens).

**Result of the real run (Question 9):** all three tickets were run through the dashboard and resolved. Rent for ticket 102 ($2,400.00), then invoice 501 ($840.00) and an $8.00 purchase order for ticket 101 were each approved and paid by a human; ticket 103 ended in a human decision and moved no money. Checking went from $3,400.00 to $152.00 (`output/desk_tickets.html`, Cash tab; `output/resolved_tickets.json`).

**Run it:** through the API below (the dashboard uses it), or from the command line with `venv\Scripts\python.exe backend\run_tickets.py` (resets the DB and runs each open ticket; it can only prepare payments, never approve or pay them).

**Audit trail:** every loop step of every agent (agent start/end, model response with token counts, tool call with arguments, tool result, delegation, final output, errors) is appended to `output/audit_trail.json`, tagged with `run_id`, `ticket_id`, agent, depth, and who delegated. The file is appended to, never wiped; database resets, human approvals, and payments are logged too.

## Backend API routes

`backend/main.py` (FastAPI). Start it from `backend/` with `uvicorn main:app --reload --port 8000`; it serves `http://localhost:8000` (interactive docs at `/docs`) and allows the React dev server on `localhost:5173` / `localhost:3000`. Shop facts come from the MCP server; agents run only when `POST /tickets/{id}/run` is called.

- `GET http://localhost:8000/tickets` - the 3 tickets with status `open` or `resolved`, their prepared payments, and the boss's last decision.
- `POST http://localhost:8000/tickets/{ticket_id}/run` - runs the agent team on that ticket (agents only prepare payments) and returns the boss's decision, drafts, and token usage.
- `GET http://localhost:8000/events?after=&limit=&ticket_id=` - recent agent events (what agents said, tools they used); pass the returned `next_after` as `after` to poll for new ones.
- `POST http://localhost:8000/tickets/{ticket_id}/resolve` - body `{"approver": "<name>", "note": "<optional decision>"}`; a human closes a ticket that ends in a decision instead of a payment (like the discount request). Moves no money; refused (409) while payments for the ticket are still waiting.
- `GET http://localhost:8000/proposals?status=` - payments and purchase orders the agents prepared, waiting for a human.
- `POST http://localhost:8000/proposals/{proposal_id}/approve` - body `{"approver": "<name>"}`; records the human approval and pays it. The only route that changes cash; refuses (409) if cash would go negative or a purchase order's vendor still has an unpaid invoice.
- `POST http://localhost:8000/proposals/{proposal_id}/reject` - body `{"approver": "<name>"}`; records a rejection, no money moves.
- `GET http://localhost:8000/cash` - current checking balance from `cash_accounts`, plus how much is reserved by unpaid proposals.
- `POST http://localhost:8000/reset` - resets the database to its original values for a fresh run (refused while an agent run is in progress; the audit trail is kept).

## React dashboard

`frontend/` (React + Vite + TypeScript). Start the backend first (`uvicorn main:app --reload --port 8000` from `backend/`), then in `frontend/` run `npm install` once and `npm run dev`; that opens the desk at `http://localhost:5173`, which is the origin the backend allows. Design choices (layout, how each agent reads, how resolved tickets and cash look, and why) are in `output/design.md`.

What the desk does, and the route behind each part:
- **Ticket list** (left): the 3 tickets with a status pill: open, agents working, needs your approval, needs your call, or resolved (`GET /tickets`).
- **Run** (middle): pick a ticket and press "Start the agent team" (`POST /tickets/{id}/run`).
- **Live feed and agent cards** (middle): who asked whom, which tools ran, and what each agent said, polled while a run is going; plus a card per agent summarizing what it did (`GET /events`).
- **Decision and drafts** (middle): the boss's decision and the reply drafts, marked "Draft - not sent".
- **Checking balance** (right): counts down after a paid approval, with the amount held for pending approvals (`GET /cash`).
- **Waiting for you** (right): each prepared payment or purchase order with Approve & pay / Reject, after a confirmation and with the approver's name (`GET /proposals`, `POST /proposals/{id}/approve|reject`).
- **Mark resolved** (middle): a human closes a ticket that ends in a decision rather than a payment, with an optional note (`POST /tickets/{id}/resolve`).
- **Fresh run** (top): resets the database (`POST /reset`).

A ticket shows **resolved** only when every payment prepared for it is approved and paid, or a human closed it. A finished run that is still waiting on a person says so.

## MCP tools

Defined in `mcp_server/server.py` (FastMCP, over `data/campus_customs_new.db`). Connected via `.mcp.json`; the first three were smoke-tested in `output/mcp_smoke.json`. Read tools open the DB read-only; only the money tools write.

### Ticket tools (original three)

#### `get_order_fulfillment_blockers(ticket_id)`
- Reads: `tickets`, `inventory`, `pricing`, `invoices`, `vendors`, `desk`
- Unlocks: ticket 101
- Why: Tauhid's order for `CC-TEE-WHITE` size S is short 1 unit, and this tool follows the ticket's `invoice_id` to the overdue $840 reprint invoice (3 days overdue) and Bulldog Print Co's 5-day lead time, which shows what is blocking the order.

#### `check_rent_affordability(lease_id)`
- Reads: `leases`, `cash_accounts`, `invoices`, `desk`
- Unlocks: ticket 102
- Why: the email says rent is due in 2 days, and this tool shows the $3,400 balance covers the $2,400 rent but leaves only $160 once the open $840 invoice is also paid.

#### `get_margin_for_discount(sku, size, qty)`
- Reads: `pricing`, `inventory`
- Unlocks: ticket 103
- Why: the club wants 20 `CC-HOOD-NAVY` size M at a discount, and this tool caps any offer at the 62.07% break-even, shows $720 profit at list, and flags that only 8 are in stock (short 12); the database has no discount policy.

### Team and backend tools (added in Questions 5 and 7)

#### `list_all_tickets()`
- Reads: `tickets`, `desk`
- Used by: the backend (`GET /tickets`). Returns every ticket with its `open`/`resolved` status. A ticket becomes `resolved` when `pay_approved` pays the last payment prepared for it, or when a human closes it with `resolve_ticket`.

#### `list_payment_proposals(status?)`
- Reads: `payment_proposals`
- Used by: the backend (`GET /proposals`, and to look up a proposal before approving it). Not offered to any agent.

#### `list_open_tickets()`
- Reads: `tickets`, `desk`
- Used by: Boss, Customer Service. Returns every open ticket plus `date_today`, so the boss can read the queue and customer service can address the right person.

#### `check_stock_and_restock_vendors(sku, size, qty)`
- Reads: `inventory`, `pricing`, `vendors`, `invoices`, `desk`
- Used by: Inventory (tickets 101, 103). Returns stock, shortfall, estimated restock cost, and every vendor with `lead_days` and `can_ship_new_product_now` (false while the vendor has an unpaid open invoice, e.g. Bulldog Print Co and invoice 501).

#### `get_cash_and_open_invoices()`
- Reads: `cash_accounts`, `invoices`, `vendors`, `payments`, `payment_proposals`, `desk`
- Used by: Accounting. Returns the balance, open invoices with days overdue (vs `date_today`), past payments, and `available_after_commitments` (balance minus cash already reserved by unpaid proposals).

#### `propose_payment(kind, ref_id, proposed_by, ticket_id?)`
- Reads: `invoices` or `leases`, `cash_accounts`. Writes: `payment_proposals`
- Used by: Accounting (invoice 501 for ticket 101, rent for ticket 102). Prepares a `pending` proposal; the amount comes from the DB, duplicates return the existing proposal, and it refuses to prepare anything the free cash cannot cover. Moves no money. The agent runner overwrites `proposed_by` and `ticket_id` with the real calling agent and the ticket being worked, so an agent can't fake either.

#### `propose_purchase_order(vendor_id, sku, size, qty, proposed_by, ticket_id?)`
- Reads: `vendors`, `pricing`, `inventory`, `invoices`. Writes: `payment_proposals`
- Used by: Accounting (ticket 101 restock). Prepares a `pending` order priced at `unit_cost x qty` (no vendor quotes exist), flagged with `blocked_by` invoice ids if the vendor has unpaid invoices. Moves no money.

#### `resolve_ticket(ticket_id, resolved_by, approval_code)`
- Writes: `tickets`
- Used by: the backend's resolve route only (human-only, same approval code as the payment tools; not offered to any agent). Marks an open ticket `resolved` when no money is involved. Refuses if the ticket isn't open or still has pending/approved payments.

#### `record_human_approval(proposal_id, approver, approved, approval_code)`
- Writes: `payment_proposals`
- Used by: the backend's approve/reject routes only. No agent is offered this tool, and it refuses without the approval code, which only the backend process holds. A plain `.mcp.json` connection has no code, so approvals are disabled there.

#### `pay_approved(proposal_id, approval_code)`
- Writes: `cash_accounts`, `payments`, `invoices` (marks `paid`) or `leases` (moves `next_due` forward one month), `payment_proposals`
- The only tool that moves money, and human-only: it needs the same approval code, so no agent can call it (accounting has no pay tool) and the backend's approve route is the only caller. Refuses unless the proposal is `approved`; refuses if the checking balance is below the amount (no negative balances); refuses a purchase order while the vendor still has open invoices. On success it does all updates in one transaction, records the human approver in `payments.approved_by`, and marks the ticket `resolved` once nothing else is waiting on it.

## Safety guardrails

What a real business would want before letting agents talk to customers and touch money, and how this build covers it:

1. **Humans approve every payment.** Agents can only prepare proposals. The approve route is the only way cash changes: it needs a human's name, and the MCP tools it uses (`record_human_approval`, `pay_approved`) refuse without a code that only the backend process holds and no agent is offered. *Real-world add-on: a second approver above a dollar limit.*
2. **Hard cash floor in code, not in the prompt.** Proposals and `pay_approved` both refuse when free cash is too low, so the balance can never go negative no matter what an agent says. Pending proposals reserve cash, so two agents cannot spend the same dollars.
3. **Amounts come from the database.** Agents choose *what* to pay, never *how much*; an agent cannot invent an amount or a payee.
4. **Drafts only.** The team has no email, phone, or vendor-contact tool, so nothing can be sent. Customer-facing drafts must leave out internal figures (cash, margins, vendor invoices, approvals) and may not promise dates, discounts, or payments that are not decided.
5. **Least privilege per agent.** Each agent sees only its own MCP tools (e.g. customer service cannot see money tools; only accounting can propose payments). The Portkey key stays out of the MCP server's environment and out of every agent's context and logs.
6. **No made-up facts.** Prompts require tool-sourced facts only; tools return an explicit error for missing rows; there is no invented discount policy (any discount is flagged for the owner).
7. **Full audit trail.** Every step, tool call, result, delegation, human decision, and payment is appended to `output/audit_trail.json`, which is never wiped.
8. **Bounded cost and loops.** Shared per-ticket request/token budget, a delegation depth and count cap, and no asking a teammate who is already waiting on you.
9. **Clean test data.** Full runs start from a reset database, so test payments cannot leak into the real books.
10. **Closing a ticket is a human act too.** Agents cannot mark anything resolved; `resolve_ticket` needs the same approval code as the payment tools, and refuses while payments for the ticket are still waiting.
11. **Reasons are shown, not hidden.** When a payment is refused (not enough cash, vendor still blocked by an unpaid invoice), the dashboard shows the reason on the card and the attempt is logged.

Known limits: approval is a button click with a typed name, not real identity verification (anyone at the keyboard could type any name); an agent's *recommendations* (like a discount idea) are only as good as the model's judgement, which is why a human reviews them; purchase-order amounts use our own unit cost because the database has no vendor quotes.
