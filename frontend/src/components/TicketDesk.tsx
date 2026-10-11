import { useEffect, useState } from 'react'
import { buildFeed, summarizeAgents } from '../feed'
import { ticketTypeLabel } from '../format'
import type { AgentEvent, Ticket } from '../types'
import { AgentFeed } from './AgentFeed'
import { AgentRoster } from './AgentRoster'
import { PawPrint, PawTrail } from './Bulldog'
import { DecisionPanel } from './DecisionPanel'
import { StatusPill, ticketState } from './TicketList'

interface Props {
  ticket: Ticket
  events: AgentEvent[] // this ticket's latest run only
  runningId: number | null
  otherRunning: boolean
  onRun: () => void
  onResolve: () => void
}

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(t)
  }, [])
  return <span>{Math.max(0, Math.round((now - since) / 1000))}s</span>
}

export function TicketDesk({ ticket, events, runningId, otherRunning, onRun, onResolve }: Props) {
  const state = ticketState(ticket, runningId)
  const running = state === 'running'
  const [startedAt, setStartedAt] = useState<number | null>(null)
  useEffect(() => {
    setStartedAt(running ? Date.now() : null)
  }, [running, ticket.id])

  const feed = buildFeed(events)
  const summaries = summarizeAgents(events, ticket.last_decision)
  const ran = events.length > 0
  const label = ran ? 'Run the agent team again' : 'Start the agent team'
  const request = [ticket.sku && `SKU ${ticket.sku}`, ticket.size && `size ${ticket.size}`, ticket.qty && `qty ${ticket.qty}`, ticket.lease_id && `lease #${ticket.lease_id}`, ticket.invoice_id && `invoice #${ticket.invoice_id}`].filter(Boolean)

  return (
    <div className="desk">
      <section className={`panel ticket-header state-${state}`}>
        <div className="ticket-header-top">
          <div>
            <span className="mini-tag">{ticketTypeLabel(ticket.type)}</span>
            <h1>
              <PawPrint size={22} /> #{ticket.id} · {ticket.subject}
            </h1>
            <p className="from">
              From <strong>{ticket.requester}</strong>
            </p>
          </div>
          <StatusPill state={state} />
        </div>
        {ticket.notes && <blockquote>{ticket.notes}</blockquote>}
        {request.length > 0 && (
          <div className="chips">
            {request.map((r) => (
              <span key={String(r)} className="chip">
                {r}
              </span>
            ))}
          </div>
        )}
        <div className="run-row">
          {state === 'resolved' ? (
            <p className="resolved-note">
              <PawPrint size={16} />{' '}
              {ticket.proposals.some((p) => p.status === 'paid')
                ? 'Resolved: every payment for this ticket is approved and paid.'
                : 'Resolved by you: no payment was needed.'}
            </p>
          ) : (
            <button className="btn primary big" disabled={running || otherRunning} onClick={onRun}>
              {running ? (
                <>
                  <PawTrail /> Agents working{startedAt && <> · <Elapsed since={startedAt} /></>}
                </>
              ) : (
                label
              )}
            </button>
          )}
          {otherRunning && !running && <span className="muted small">Another ticket is running. One at a time keeps the cash plan honest.</span>}
          {state === 'needs_approval' && <span className="muted small">Run finished. Approve the payments on the right to resolve it.</span>}
          {state === 'needs_input' && (
            <>
              <button className="btn ghost big" onClick={onResolve}>
                Mark resolved
              </button>
              <span className="muted small">Run finished. The boss needs your call (see below); close it once you've decided.</span>
            </>
          )}
        </div>
      </section>

      <AgentRoster summaries={summaries} />
      <AgentFeed items={feed} startTime={events[0]?.time ?? null} running={running} />
      {ticket.last_decision && <DecisionPanel decision={ticket.last_decision} />}
    </div>
  )
}
