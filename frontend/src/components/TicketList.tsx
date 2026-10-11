import { ticketTypeLabel } from '../format'
import type { Ticket } from '../types'
import { PawPrint, PawTrail } from './Bulldog'

export type TicketState = 'open' | 'running' | 'needs_approval' | 'needs_input' | 'resolved'

/**
 * What the desk shows for a ticket. "Resolved" is deliberately strict: the money side must be
 * finished (every prepared payment approved and paid), or the boss itself closed it with nothing
 * left to approve. A finished run that is still waiting on a person is shown as such.
 */
export function ticketState(t: Ticket, runningId: number | null): TicketState {
  if (t.running || runningId === t.id) return 'running'
  if (t.status === 'resolved') return 'resolved'
  if (t.proposals.some((p) => p.status === 'pending' || p.status === 'approved')) return 'needs_approval'
  const d = t.last_decision
  if (d) {
    if (d.status === 'resolved') return 'resolved'
    return 'needs_input'
  }
  return 'open'
}

const STATE_LABEL: Record<TicketState, string> = {
  open: 'Open',
  running: 'Agents working',
  needs_approval: 'Needs your approval',
  needs_input: 'Needs your call',
  resolved: 'Resolved',
}

export function StatusPill({ state }: { state: TicketState }) {
  return (
    <span className={`pill state-${state}`}>
      {state === 'running' ? <PawTrail /> : state === 'resolved' ? <PawPrint size={13} /> : <span className="dot" />}
      {STATE_LABEL[state]}
    </span>
  )
}

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  runningId: number | null
  onSelect: (id: number) => void
}

export function TicketList({ tickets, selectedId, runningId, onSelect }: Props) {
  return (
    <section className="panel">
      <h2 className="panel-title">
        <PawPrint size={16} /> Tickets
      </h2>
      <ul className="ticket-list">
        {tickets.map((t) => {
          const state = ticketState(t, runningId)
          return (
            <li key={t.id}>
              <button
                className={`ticket-card state-${state}${selectedId === t.id ? ' selected' : ''}`}
                onClick={() => onSelect(t.id)}
              >
                <span className="ticket-top">
                  <span className="ticket-id">#{t.id}</span>
                  <span className="ticket-type">{ticketTypeLabel(t.type)}</span>
                </span>
                <span className="ticket-subject">{t.subject}</span>
                <span className="ticket-who">{t.requester}</span>
                <StatusPill state={state} />
                {state === 'resolved' && <span className="stamp" aria-hidden="true">Resolved</span>}
              </button>
            </li>
          )
        })}
        {tickets.length === 0 && <li className="muted small">Fetching tickets…</li>}
      </ul>
    </section>
  )
}
