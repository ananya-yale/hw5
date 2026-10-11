# AI Prompts Log — Homework 5

Log of the prompts given to Claude for each question. Each entry has the initial prompt, then any follow-up prompts with a short note on why the follow-up was needed.

---

## General Instructions

> ok also general instructions for this assignment - we'll use my PORTKEY_API_KEY for AI calls (don't ever give away my API key or put it anywhere it can be found). we will use only gpt-6-luna through portkey for agents (don't make any agents yet, we'll do that later).

---

## Question 1: Vibe coder prompts

**Initial prompt:**

> we need to log everything i ask you to do. make AI_prompts.md and keep it update as we work. for questions 1-11 include question numbers, titles, and log my initial prompts, then log any follow ups i give you and a quick note on why a follow up was needed. this task is question #1 and is titled Vibe coder prompts. oh also i think we need a venv for all the python stuff for this assignment so make a venv too

**Follow-ups:** None so far.

---

## Question 2: Study the Campus Customs database

**Initial prompt:**

> problem 2 is called "Study the Campus Customs database." in our folder we have data/campus_customs.db. look through every table and give me a brief, very succinct summary of what the tables cover. copy that file to data/campus_customs_new.db. in later problems, we'll update this new working copy. 
>
> study the 3 open tickets so we understand how they link to other tables and tell me 
>
> start output/harness.md. in it, list each field and a short line on why the table matters for the agents we'll make later. we'll update the harness again later too

**Follow-ups:** None so far. (Note: the prompt's second paragraph ended mid-sentence at "tell me", so I summarized the ticket links and asked what else to report.)

---

## Question 3: Build the MCP server

**Initial prompt:**

> problem 3 is "Build the MCP server." write me an MCP server and put it in mcp_server/ using FastMCP. we'll use it to work with data/campus_customs_new.db. we will not be actually connecting or running the MCP server in this problem. for now, write 3 tools we know we'll need for the tickets in the database into the server. keep the names clear and never invent any data (only use data actually in the database)
>
> in output/harness.md, list the 3 MCP tools and include which table each reads, which ticket it helps unlock (101, 102, or 103), and one line on why that tool works for that particular ticket. the tools should be laser focused on solving problems that we need for each ticket, not just general stuff. 
>
> write a short mcp_server/README.md file explaining what the MCP server is for, which db file it uses, and its 3 tools

**Follow-ups:**

1. > ok the last tool you made is good but i'm worried the other 2 are too basic. my prof specifically said a tool that reads inventory would score low bc it's basic and vague. got any other good ideas?

   *Why needed:* my first `check_stock` and `get_rent_due` tools each read a single table, so they were too basic and vague for the grading criteria. The follow-up asks for ideas for richer, ticket-specific tools.

2. > yeah actually make the changes for all 3, i like the addition to the last tool. and yes, then update all the files from question 3 as necessary

   *Why needed:* this approved the proposed multi-table tools (fulfillment blockers, rent affordability, and the stock/profit addition to the discount tool). I rewrote `server.py` and updated `README.md` and `harness.md` to match.

---

## Question 4: Add the MCP server to vibe coder and test each tool

**Initial prompt:**

> problem 4 is called "Add the MCP server to vibe coder and test each tool." add the MCP server to this project so we can call the tools when we need to. save the connection in .mcp.json at the project root. 
>
> once we're connected, test each of my 3 MCP tools (did we already do this?). save evidence in output/mcp_smoke.json. for each tool include: 
>
> * my prompt i asked you
> * the tool name
> * the tool output (must match values in data/campus_customs_new.db)

**Follow-ups:**

1. > ok what do i need to do to restart the session so the MCP stuff works?

   *Why needed:* `.mcp.json` is only loaded when a session starts, so the tools weren't callable in the current chat. The follow-up asks how to reload it.

   **A new session was required.** The previous session started before `.mcp.json` existed, so the `campus-customs` server could not be connected there. The fix was to start a fresh session with the Homework 5 folder, where `.mcp.json` lives, as the project. The prompts below were given in that new session, which had no memory of the earlier conversation, so I re-read `AI_prompts.md` to catch up.

2. > ok i'm starting a new session so that my MCP server in homework 5 will work

   *Why needed:* the new session was opened from the Homework 4 folder with Homework 5 only added as an extra directory. Project MCP servers load only from the primary working directory, so this setup would not have picked up `.mcp.json`.

3. > no, i want to run directly from Homework 5 folder

   *Why needed:* I offered to work around the setup, but the MCP server only loads when the session's primary folder is Homework 5. I moved the session's working directory to Homework 5, after which the three `campus-customs` tools showed up as available.

4. > read AI_prompts.md

   *Why needed:* the new session had no context from the earlier one, so this gave me the log of the assignment so far.

5. > no, read output/mcp_smoke.json - the smoke test results should already be there

   *Why needed:* I had offered to re-run the three tool tests, but the evidence was already saved. I read the file instead and confirmed all three tool outputs matched `data/campus_customs_new.db`.

6. > ok, we're technically on question 4 still so i need you to be logging my prompts and updating AI_prompts.md as we go. make it clear that we needed to start a new session to make sure the MCP stuff would work. otherwise, i think we're done with question 4.

   *Why needed:* the session-restart prompts above are part of Question 4, so they had to be logged here. This also marks Question 4 as complete.

---

## Question 5: Build the agent team and grow the MCP tools

**Initial prompt:**

> question 5 is titled "Build the agent team and grow the MCP tools." build an agentic team for campus customs with Pydantic AI. the team should have a boss, inventory agent, accounting agent, facilities agent, and customer service agent. include prompts, models, and agent loops so they can delegate work to each other with full connectivity and efficiently (don't burn tokens unnecessarily). put agent prompts in backend/prompts/ using one file per agent. data types go in backend/models.py, and agent files go in backend/
>
> use my PORTKEY_API_KEY (never give it away) and only gpt-6-luna for every agent.
>
> prompts for each agent are below:
>
> * Boss: reads tickets and delegates work to other agents. makes final decisions
> * Inventory: uses SKU and size of inventory to check stock, identify shortfalls, and identify vendors that can restock
> * Accounting: records cash and invoices, checks margins, and preps payment/purchase orders for human users to give approval for
> * Facilities: manages the shop space logistics (leases, rent, etc)
> * Customer Service: drafts messages to respond to customers
> * all agents can work together if needed
>
> General rules for the agents to abide by - they won't all be relevant for every agent, but figure out where these fit in:
>
> * desk.date_today is our shop's "today" and should be the threshold for overdue things
> * use the vendors table for vendor lead times
> * vendors don't ship new products while there are still unpaid open invoices
> * human approval is necessary for all payments. this is very important. if we do make a payment, update the relevant table.
> * if there isn't enough cash, the pay tool must refuse - we can't have negative balances. (if we don't have a pay tool yet, write one into the MCP server)
> * no money is coming in in this assignment, only cash going out
> * before a full run to resolve tickets, reset the database to original values
> * never email customers or call real vendors. drafts are drafts only
>
> all tools the agents need will be written into MCP server so they can be used for open tickets. shop facts need to come from the MCP server over data/campus_customs_new.db, no inventing a shop-tools layer that bypasses MCP.
>
> agents will append to output/audit_trail.json as they run. for each agent-loop step, record enough so we can audit later and don't wipe the file after each run.
>
> list each agent and each MCP tool we have made in output/harness.md. include a short safety section with the guardrails a real business would care about when letting agents work with customers and money. (and tell me what you come up with)
>
> update mcp_server/README.md so the tool list matches what we have created by this point

**Follow-ups:**

1. > ok problem 6 is called "Plan the three tickets." you weren't supposed to actually run anything lol so we're going to pretend you didn't.

   *Why needed:* in Question 5 I ran the agent team on all three tickets, but the prompt only asked me to build it. The runs are treated as not having happened; the Question 6 plan is written as if the agents have never been run.

---

## Question 6: Plan the three tickets

**Initial prompt:**

> ok problem 6 is called "Plan the three tickets." you weren't supposed to actually run anything lol so we're going to pretend you didn't. we're going to write down what i would expect the agents to do if we ran them on each open ticket. make output/desk_tickets.html a double clickable page with one tab per ticket (101, 102, 103). add empty cash and reflection tabs for later problems.
>
> for each ticket, fill in an Expected section and leave a blank Actual session we'll fill in after the agents run.
>
> for each Expected section, we'll write in my own words who the boss should call first and why, all the agent delegations i'd expect, and which MCP tools i'd expect that run to use.
>
> so that i can write out my Expected section thoughts, give me a quick summary of the agents structure and MCP tools we've made, as well as the open tickets and the problems they pose

**Follow-ups:**

1. > below are my thoughts to slot into the html page you made: [Expected-section notes for tickets 101 and 102, and the start of 103, which was cut off with "wait stop"]

   *Why needed:* the first message was a partial draft of the Expected notes. I stopped and asked how to proceed instead of editing the page.

2. > below are my thoughts to slot into the html page you made: [the full Expected-section notes for tickets 101, 102, and 103: who the boss calls first and why, the delegations, and the MCP tools]

   *Why needed:* this was the complete version. I put each ticket's first-call reasoning, delegations, and expected tools into the Expected boxes of `output/desk_tickets.html` in the user's own wording. The Actual sections stay blank until the agents are run.

---

## Question 7: Backend routes

**Initial prompt:**

> ok problem 7 is called "Backend routes." in backend/main.py, use fastAPI and add routes that do the following:
>
> * Return the 3 tickets and tell me if open or resolved
> * When a ticket id is input, run my agent team on that ticket
> * Return recent agent events (what they said, what tools were used) so the board can refresh
> * After a human clicks approve, approve a payment or purchase (this route should be the only way to actually change cash - agents only prepare the pay)
> * Give the current checking balance from cash_accounts
> * Reset the database to original values when we do a fresh run
>
> stop i'm not done

**Follow-ups:**

1. > ok so do what i sent above, but also make sure we can start the server from the backend/ folder with uvicorn main:app --reload --port 8000
   >
   > i want the backend to be turned on from http://localhost:8000 so the frontend dashboard can call our routes.
   >
   > list each route in one line in output/harness.md (what URL and what it does)
   > for context, we're going to do a react frontend dashboard in the next problem

   *Why needed:* the first message was cut off ("stop i'm not done") so I waited. This completed it: how to start the server, the port the dashboard will call, and the harness.md route list.

---

## Question 8: React dashboard

**Initial prompt:**

> problem 8 is called "React dashboard." make a frontend dashboard in frontend/ with react + vite + typescript. it should call the routes we just built. the dashboard must:
>
> * list all 3 tickets
> * let you pick a ticket and start the agent team on it
> * show what each agent is saying and doing while it runs
> * mark a ticket resolved when the run is finished
> * show a brief summary of what each agent did on the ticket
> * let a human approve a pay or purchase when prompted
> * show the checking balance (should drop after an approved pay)
>
> also we want the dashboard to look good! implement some design decisions that make it look like a good, clean desk/dashboard. use a variety of pastel colors and include some tasteful bulldog symbols where it makes sense.
>
> connect my front end to the backend at http://localhost:8000. on the back end, allow the Vite page origin (probably http://localhost:5173) so the browser can call our routes. the board should start with npm run dev
>
> that should open the react desk in my browser so i can pick tickets and watch my agents go
>
> write output/design.md to summarize what we chose for the layout, how agents read differently, how resolved tickets and cash show up and why! include the human elements (aka we chose pastel clean aesthetic because we want to be organized but whimsical and bulldogs because we love yale)

**Follow-ups:** None so far.

---

## Question 9: Resolve the tickets

**Initial prompt:**

> ok, problem 9 is "Resolve the tickets." reset the working database data/campus_customs_new.db so we start clean. then i'm going to run all 3 tickets until they are resolved.
>
> in output/desk_tickets.html, fill in the Actual section from this run. keep my section from before intact so the 2 can be compared.
>
> in the cash section of output/desk_tickets.html, itemize the money like so:
>
> * Starting checking balance (after reset)
> * for each ticket how cash changed when that ticket resolved and why (which pay / purchase, dollar amount)
> * ending checking balance - must match cash_accounts in the working database
>
> don't mess up any math.
>
> also save output/resolved_tickets.json: for each ticket, the id, final status, short outcome, what each agent contributed, and any human approvals
> save output/resolved_board.html: a double clickable page with a screenshot of my react board for each resolved ticket (all 3 tickets)
>
> append my real runs to output/audit_trail.json. finish output/harness.md so it covers tables, MCP tools, my agents, the API routes, the dashboard, and safety rules.

**Follow-ups:**

1. > we need a way to resolve ticket 103

   *Why needed:* ticket 103 ends in a human decision (the discount) with no payment, and the dashboard only marked a ticket resolved once its payments were paid, so 103 could never be resolved. I added a human-only "resolve" path: a new MCP tool, a `POST /tickets/{id}/resolve` backend route, and a "Mark resolved" button with an optional decision note.

2. > launch the website it's not working for me. then i'll resolve 103

   *Why needed:* the page was blank. When I restored the boss's decisions after restarting the backend, the saved copies were missing a couple of optional fields and the decision panel crashed on them. I re-saved them in full, made the panel tolerate missing fields, added an error screen so a crash can't blank the page again, and relaunched.

3. > ok, done

   *Why needed:* the user had resolved ticket 103 in the dashboard, so I built the Question 9 deliverables from the real run: the Actual sections and cash itemization in `desk_tickets.html`, `resolved_tickets.json`, `resolved_board.html`, and the finished `harness.md`.

---

## Question 10: Reflection

**Initial prompt:**

> problem 10 is called "Reflection." we're going to fill in the Reflection tab of the output/desk_tickets.html. we need my own words for this generally but you can make it flow better and add insights from the multiple runs we did so i don't forget. here it is:
>
> * the agents did well on ticket 102, which was most straightforward. ticket 101 required another invoice to be resolved, which was a little unclear from running the agents but easy to figure out from running the agents more than once. for 103, we had to adjust the instructions and have a button that users can click to resolve manually because we don't have enough cash to streamline the resolving.
> * for ticket 101, the boss called agents in a different order than i was expecting. across all the tickets, the boss had more of a role than i expected since the boss had to check who to delegate to next in between steps. for ticket 102, i thought accounting agent would use pay_proposal which it did not. my understanding of what pay_approved does was slightly off. for ticket 103, the boss delegated to accounting first instead of inventory, to ask about margin and discount ceilings. this was ultimately not that useful as we hadn't actually set discount rules, but the agents did a good job of flagging that and we made a new version of the flow that allowed me to make a judgment call at the end and mark the ticket as resolved.
> * i would merge some of the accounting agent's tools and capabilities with the boss in the future because the boss so frequently had to check with that agent before delegating. it would be effective for the boss to be able to check ceilings/cash balance and leave the accounting agent to do the rest of its tasks.
> * 3 new problems the agents could be used for: 1) pay utility bills; 2) proactively flag where more stock will be needed soon (if stock is below a certain threshold, for example), and 3) source vendors to proactively add more stock
> * 3 problems the agents could not solve right now: 1) predicting demand for specific items with any kind of statistical rigor - we'd need historical data and statistical tools for the agents to do that; 2) sending auto emails when customers inquire about items that are clearly out of stock - we'd need to connect agents to email for that; 3) as we saw in this exercise, the agents can't make judgment calls on bulk discount rates. if we gave the agents rules for bulk discounts (can price at $X level for every Y orders) and allowed them to approve new prices dynamically, they could do so

**Follow-ups:** None so far.

---

## Question 11: Submit to Github

**Initial prompt:**

> problem 11 is called "Submit to Github." let's push this to a public github repo so graders can clone it. i want the repo url to be in output/github_url.txt
>
> don't push my real .env to the repo. make sure you include the original and copied database files under data/ so graders can see everything.
>
> the files should look like the tree image i added to this message. README should explain to copy the original DB to the woring copy for a clean run, start MCP server, start FastAPI backend, start the React board, reset the DB before a full 3-ticket run.
>
> the github url we'll use is this: https://github.com/ananya-yale/hw5.git
>
> tell me what other info you need from me to do this
>
> *(attached: an image of the expected folder tree)*

**Follow-ups:**

1. > use the github noreply email, i'll sign in when it pops up

   *Why needed:* I had asked what else was needed before publishing. The answers were to author the commit with GitHub's private noreply address instead of the Yale email, and that the user would complete GitHub's sign-in prompt during the push.
