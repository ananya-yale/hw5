# Campus Customs: an agent team for a small Yale merch shop

A team of five AI agents (boss, inventory, accounting, facilities, customer service) works the shop's open support tickets. The agents get every shop fact from an **MCP server** over a small SQLite database, and they can only *prepare* payments. A human approves each payment in a **React dashboard**, and that approval is the only way cash changes. Built with Pydantic AI, FastMCP, FastAPI, and React + Vite + TypeScript. Every agent runs on `gpt-6-luna` through Portkey.

The three open tickets:

| Ticket | Problem |
|---|---|
| 101 | A customer wants a size S tee, but stock is 0 and the vendor won't ship while an overdue invoice is unpaid |
| 102 | Rent ($2,400) is due in 2 days |
| 103 | A student club wants 20 hoodies at a bulk discount, but only 8 are in stock and there is no discount policy |

## What's in the repo

```
hw5/
├── AI_prompts.md          every prompt given while building this, with follow-ups
├── requirements.txt       Python dependencies
├── .env.example           template for your Portkey key (copy to .env)
├── .gitignore
├── .mcp.json              registers the MCP server for Claude Code
├── README.md
├── data/
│   ├── campus_customs.db       the ORIGINAL database (never modified)
│   └── campus_customs_new.db   the WORKING copy the app reads and writes
├── mcp_server/
│   ├── server.py          FastMCP server: all the shop tools (13)
│   └── README.md          the tools, one by one
├── frontend/              React + Vite + TypeScript dashboard
├── backend/
│   ├── main.py            FastAPI routes the dashboard calls
│   ├── models.py          data types (agent outputs, request bodies, run state)
│   ├── team.py            the agent team: model, MCP connection, delegation, loop
│   ├── boss.py, inventory.py, accounting.py, facilities.py, customer_service.py
│   ├── audit.py, db.py, run_tickets.py
│   └── prompts/           one prompt file per agent
└── output/
    ├── harness.md             tables, MCP tools, agents, API routes, dashboard, safety rules
    ├── mcp_smoke.json        evidence from testing the first three MCP tools
    ├── desk_tickets.html     expected vs. actual for each ticket, cash itemization, reflection
    ├── design.md             dashboard design choices
    ├── resolved_tickets.json  final status and what each agent did, per ticket
    ├── resolved_board.html    screenshots of the board for each resolved ticket
    ├── audit_trail.json       every agent step from every run (append-only)
    └── github_url.txt
```

Start with `output/harness.md` for the full reference, and open `output/desk_tickets.html` and `output/resolved_board.html` in a browser to see the results.

## Setup (once)

You need Python 3.11+ (built with 3.14) and Node 20+ (built with 24).

```bash
# from the repo root
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt

cd frontend
npm install
cd ..
```

**Your Portkey key.** Copy `.env.example` to `.env` in the repo root and put your own key in it:

```
PORTKEY_API_KEY=your-portkey-api-key-here
```

`.env` is git-ignored. The key is only read into the model client; it is never logged, never sent to the MCP server, and never shown to an agent. Running the agents calls `gpt-6-luna` through Portkey, about 54k input tokens in total for the three tickets.

> **Windows paths:** `.mcp.json` points at `venv/Scripts/python.exe`. On macOS/Linux change it to `venv/bin/python`.

## Run it

### 1. Start from a clean database

`data/campus_customs.db` is the original and is never changed. The app works on a copy, `data/campus_customs_new.db`. The copy in the repo is in its **finished** state from the real run (all tickets resolved, checking at $152.00), so for a clean run copy the original over it:

```bash
# Windows (cmd)
copy /Y data\campus_customs.db data\campus_customs_new.db
# macOS / Linux / Git Bash
cp data/campus_customs.db data/campus_customs_new.db
```

The dashboard's **Fresh run** button (or `POST /reset`) does the same thing and also clears saved decisions.

### 2. MCP server

The MCP server (`mcp_server/server.py`) holds all the tools the agents use, over the working database. **You normally don't have to start it:** the FastAPI backend launches its own copy when it starts. To run it on its own, or to use it from Claude Code (which reads `.mcp.json`):

```bash
python mcp_server/server.py        # speaks MCP over stdio
```

Standalone or via `.mcp.json`, the money tools stay locked: they need an approval code that only the backend process holds.

### 3. FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

It serves `http://localhost:8000` (interactive docs at `http://localhost:8000/docs`) and allows the dashboard's origin, `http://localhost:5173`. Routes are listed in `output/harness.md`.

### 4. React board

In a second terminal:

```bash
cd frontend
npm run dev
```

This opens the desk at `http://localhost:5173`.

### 5. Reset, then run all three tickets

1. Press **Fresh run** (or copy the database as in step 1) so you begin at checking = $3,400.00 with every ticket open.
2. Type your name under **Approving as** (the approve buttons stay disabled until you do).
3. Pick a ticket and press **Start the agent team**. Watch the live feed and the agent cards.
4. When payments appear under **Waiting for you**, press **Approve & pay** and confirm. The checking balance counts down. A ticket turns **Resolved** once every payment for it is paid.
5. Ticket 103 ends in a judgment call (no discount policy exists), so the boss asks for your decision. Press **Mark resolved** and add a note about what you decided.

Notes on the flow: a purchase order can't be paid until its vendor's invoice is paid (approve invoice 501 first). In the real run, the three tickets ended with $2,400.00 (rent) + $840.00 (invoice 501) + $8.00 (purchase order) paid, leaving **$152.00**.

You can also run the agents from the command line (it resets the database first and only prepares payments):

```bash
python backend/run_tickets.py --tickets 101,102,103
```

## Safety rules, in short

- Agents only prepare payments; a human approves, and the approve route is the only way cash changes.
- Payments are refused if they would make the balance negative, and pending proposals reserve cash.
- Amounts come from the database, never from an agent.
- Replies to customers and landlords are drafts only. Nothing is ever sent.
- Each agent sees only its own tools; no agent can pay, approve, or resolve a ticket.
- Every agent step, tool call, approval, and payment is appended to `output/audit_trail.json`.

The full list is in `output/harness.md`.
