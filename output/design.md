# Campus Customs Desk: design notes

The dashboard lives in `frontend/` (React + Vite + TypeScript) and talks to the backend at `http://localhost:8000`. This file explains what we chose and why, in plain words.

## The feel: organized, but whimsical

We wanted a place that feels like a tidy desk you'd actually want to sit at: calm enough to trust with money, playful enough that watching an agent team work is fun instead of stressful.

- **Clean pastel palette.** A warm cream "desk mat" background with a faint dot grid, white cards, soft shadows, rounded corners. Pastels keep it friendly; Yale-ish navy is used only for text and the main button, so the one thing you're meant to press always stands out. Pastel lavender, mint, butter, sky, rose, and peach are each given a job (below) instead of being decoration.
- **Bulldogs because we love Yale.** A small hand-drawn bulldog is the logo and the boss's avatar. A sleepy bulldog appears wherever a panel is empty ("Nothing to approve. Good dog."). Paw prints mark panel titles, light up one after another while agents are working, and are stamped on resolved tickets. We kept it to those spots on purpose: enough to make the desk ours, not so much that it turns into clip art.
- **Reduced motion is respected.** Animations (paw trail, the balance count-down, the stamp) switch off for anyone who asks their system for less motion.

## Layout: three columns, left to right = "what", "how", "so what"

| Column | Holds | Why |
|---|---|---|
| Left | The three tickets | The queue is the starting point, so it is always visible and one click selects a ticket. |
| Middle | The selected ticket: header and Start button, a row of agent cards, the live feed, the boss's decision and reply drafts | This is where attention goes while a run happens, so the story reads top to bottom: what was asked, who did what, what they said, what was decided. |
| Right | Checking balance, then "Waiting for you" (approvals) | Money and human decisions are kept together and out of the way of the agents' chatter, so you can watch the feed and still see the balance move. |

On narrow screens the columns stack. The side columns stay in view as you scroll the middle one.

## How agents read differently

Each agent has one pastel colour, one avatar, and a different way of showing up in the feed, so you can tell who is speaking before you read a word:

- **Boss (lavender, bulldog avatar):** roomy speech bubbles with larger bold text, because the boss makes the decisions and everything else supports them.
- **Inventory (mint) and Facilities (sky):** compact work-log lines with a coloured spine: a tool chip, the arguments, and a one-line result you can click open to see the raw data.
- **Accounting (butter):** ledger-paper rows with a dashed border and monospace numbers, because it is the agent that deals in dollars.
- **Customer Service (rose):** soft notes, and its replies appear as little letters stamped "Draft - not sent", so nobody mistakes a draft for something that went out.
- **Delegations** ("Boss asks Inventory: ...") are dashed, lighter rows that show the handoff without competing with the work.

Tool calls use friendly names ("Checking cash and open invoices") with the result in one sentence ("$3,400.00 in checking, $3,400.00 free after holds, 1 open invoice"). The raw JSON is one click away for anyone who wants to audit it.

Above the feed, **"What each agent did"** gives every agent a card with its state (not called, working, done), a short summary in its own words, a few fact chips (e.g. "0 on hand", "invoice $840.00 prepared"), who it asked, and which tools it used. Agents that were never called stay faded, so you can see at a glance who was needed for this ticket.

## How resolved tickets show up, and why

A ticket card changes with its state: open (plain), agents working (animated paw trail), needs your approval (peach), needs your call (butter), resolved (mint with a tilted "Resolved" stamp). The ticket page header turns mint and says why it is resolved.

**A ticket that ends in a decision (like the discount request) has a human way out too:** when the boss says "needs your call", a "Mark resolved" button opens a small confirmation where you can jot what you decided. It records your name and note in the audit trail, moves no money, and refuses while payments for that ticket are still waiting.

**Resolved is deliberately strict.** A finished run is not the same as a finished ticket. A ticket is marked resolved only when every payment prepared for it has been approved and paid by a human (or you closed it yourself because it ended in a decision rather than a payment). A ticket whose run is done but is still waiting on a person says so instead: "Needs your approval" or "Needs your call". We did this because a green check on a ticket whose payment hasn't happened would be a small lie, and in a money workflow that kind of lie is expensive. The stamp lands at the moment the last payment goes through, so it also feels like a reward for the human's work.

## How cash shows up, and why

- **One big number**, always visible at the top of the right column, because the whole point of the human-in-the-loop design is protecting that number.
- **It counts down, and a "-$840.00" chip appears** for a few seconds, with a soft pulse around the card. Money only ever leaves in this project, so the drop is the one important event and gets exactly one clear moment, then calms down again.
- **A "held for approvals" bar** shows how much of the balance is already spoken for by prepared-but-unpaid proposals, next to "free to plan with". It explains why agents may be told they can't afford something that the raw balance would cover.
- **The balance can't go below $0**, and the page says so. Each approval card also shows what checking would be after paying. If that would be negative the card says it will be refused, before anyone clicks.

## Approving money: a human, on purpose

- Agents never pay; the page makes that visible. "Waiting for you" lists each prepared payment or purchase order with the amount big, who prepared it, which ticket it belongs to, and any warning (for example a vendor that won't ship until an invoice is paid).
- You type your name once ("Approving as"); it is remembered and recorded as the approver. The buttons stay disabled until you do.
- **Approve & pay** asks one more question ("Pay $840.00?") before it moves money. Reject is a one-click-plus-confirm decision too. If the backend refuses (not enough cash, vendor still blocked), the reason is shown on the card in plain language and nothing breaks.
- When a run finishes with payments waiting, the panel pulses, a toast says so, and the page scrolls it into view: the "prompt" the human needs.
- Paid items move to a small "Paid so far" list, which is how you can see where the money went.

## Live feed: what happens while a run goes

The page asks the backend for new events about once a second while a run is going, and every few seconds otherwise. It only shows the latest run for the selected ticket and ignores anything from before the last database reset, so a "Fresh run" really does feel fresh. Long results are collapsed; the feed scrolls itself while a run is active and stays put when you scroll back to read.

## Things we chose not to do

- No chat box: the agents work from tickets, so the desk shows work happening, not a conversation with you.
- No sending anything: reply drafts are shown but there is no send button, matching the backend rule that drafts stay drafts.
- No auto-approval, ever, and no "approve all" button.

## How it was checked

We drove the real dashboard in a headless browser against the real backend API, with the language-model calls swapped for a replay of events recorded in an earlier real run, so no tokens were spent. We ran all three tickets, approved the payments (including the purchase order that has to wait for its vendor's invoice), watched the balance go from $3,400.00 to $152.00, saw tickets 101 and 102 stamped resolved and 103 left at "Needs your call", and tried a fresh run. A live run with the real agents has not been done from the dashboard.
