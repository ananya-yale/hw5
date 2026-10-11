import { useCallback, useMemo, useRef, useState } from 'react'
import {
  API_URL,
  ApiError,
  approveProposal,
  getCash,
  getEvents,
  getProposals,
  getTickets,
  rejectProposal,
  resetDatabase,
  resolveTicket,
  runTicket,
} from './api'
import { ApprovalQueue } from './components/ApprovalQueue'
import { BulldogFace } from './components/Bulldog'
import { CashCard } from './components/CashCard'
import { ConfirmModal, Toasts, type Toast } from './components/Overlays'
import { TicketDesk } from './components/TicketDesk'
import { TicketList } from './components/TicketList'
import { money } from './format'
import { usePoller } from './hooks'
import type { AgentEvent, Cash, Proposal, Ticket } from './types'

type Confirm = { kind: 'approve' | 'reject'; p: Proposal } | { kind: 'resolve'; ticketId: number } | { kind: 'reset' } | null

const message = (e: unknown) => (e instanceof Error ? e.message : String(e))

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [runningId, setRunningId] = useState<number | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [approver, setApprover] = useState(() => localStorage.getItem('approverName') ?? '')
  const [confirm, setConfirm] = useState<Confirm>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [working, setWorking] = useState(false)
  const [cardErrors, setCardErrors] = useState<Record<number, string>>({})
  const [attention, setAttention] = useState(false)
  const [resolveNote, setResolveNote] = useState('')
  const cursor = useRef<number | null>(null)
  const toastId = useRef(0)

  const toast = useCallback((tone: Toast['tone'], text: string) => {
    const id = ++toastId.current
    setToasts((t) => [...t, { id, tone, text }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6500)
  }, [])

  const refreshCore = useCallback(async () => {
    try {
      const [t, p, c] = await Promise.all([getTickets(), getProposals(), getCash()])
      setTickets(t.tickets)
      setProposals(p.proposals)
      setCash(c)
      setError(null)
      setSelectedId((cur) => cur ?? t.tickets[0]?.id ?? null)
      return p.proposals
    } catch (e) {
      setError(message(e))
      return null
    }
  }, [])

  const refreshEvents = useCallback(async () => {
    try {
      const r = await getEvents(cursor.current)
      cursor.current = r.next_after
      // Two overlapping polls can return the same events, so only keep ones we haven't stored yet.
      if (r.events.length)
        setEvents((prev) => {
          const last = prev.length ? prev[prev.length - 1].index : -1
          const fresh = r.events.filter((e) => e.index > last)
          return fresh.length ? [...prev, ...fresh].slice(-3000) : prev
        })
    } catch {
      /* the core poll already reports a lost connection */
    }
  }, [])

  const busy = runningId !== null || tickets.some((t) => t.running)
  usePoller(refreshCore, busy ? 1500 : 3000)
  usePoller(refreshEvents, busy ? 800 : 3000)

  // This ticket's latest run: events after the last database reset, from its last run_start on.
  const ticketEvents = useMemo(() => {
    if (selectedId === null) return []
    let floor = -1
    for (const e of events) if (e.step === 'database_reset') floor = e.index
    const mine = events.filter((e) => e.index > floor && e.ticket_id === selectedId)
    let start = -1
    mine.forEach((e, i) => {
      if (e.step === 'run_start') start = i
    })
    return start < 0 ? [] : mine.slice(start)
  }, [events, selectedId])

  const selected = tickets.find((t) => t.id === selectedId) ?? null
  const waiting = proposals.filter((p) => p.status === 'pending' || p.status === 'approved')

  const onRun = async () => {
    if (selectedId === null) return
    const id = selectedId
    setRunningId(id)
    try {
      await runTicket(id)
      toast('good', `The team finished ticket #${id}.`)
    } catch (e) {
      toast('bad', `Run failed: ${message(e)}`)
    } finally {
      setRunningId(null)
      const latest = await refreshCore()
      await refreshEvents()
      const pending = (latest ?? []).filter((p) => p.ticket_id === id && p.status === 'pending')
      if (pending.length > 0) {
        toast('info', `${pending.length} payment${pending.length === 1 ? ' is' : 's are'} waiting for your approval.`)
        setAttention(true)
        setTimeout(() => setAttention(false), 9000)
        document.getElementById('approvals')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      }
    }
  }

  const onApproverChange = (name: string) => {
    setApprover(name)
    localStorage.setItem('approverName', name)
  }

  const doConfirm = async () => {
    if (!confirm) return
    setWorking(true)
    try {
      if (confirm.kind === 'resolve') {
        try {
          await resolveTicket(confirm.ticketId, approver.trim(), resolveNote.trim())
          toast('good', `Ticket #${confirm.ticketId} is resolved.`)
          setResolveNote('')
        } catch (e) {
          toast('bad', `Couldn't resolve it: ${message(e)}`)
        }
      } else if (confirm.kind === 'reset') {
        await resetDatabase()
        setCardErrors({})
        toast('info', 'Fresh run: the database is back to its original numbers.')
      } else {
        const { p } = confirm
        setBusyId(p.id)
        setCardErrors((c) => ({ ...c, [p.id]: '' }))
        try {
          if (confirm.kind === 'approve') {
            const r = await approveProposal(p.id, approver.trim())
            toast('good', `Paid ${money(r.amount)}. Checking is now ${money(r.new_checking_balance)}.`)
            if (r.ticket_resolved && r.ticket_id) toast('good', `Ticket #${r.ticket_id} is resolved.`)
          } else {
            await rejectProposal(p.id, approver.trim())
            toast('info', `Rejected: ${money(p.amount)} will not be paid.`)
          }
        } catch (e) {
          setCardErrors((c) => ({ ...c, [p.id]: message(e) }))
          if (e instanceof ApiError && e.status === 409) toast('bad', message(e))
          else toast('bad', `That didn't go through: ${message(e)}`)
        } finally {
          setBusyId(null)
        }
      }
    } catch (e) {
      toast('bad', message(e))
    } finally {
      setWorking(false)
      setConfirm(null)
      await refreshCore()
      await refreshEvents()
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <BulldogFace size={46} />
          <div>
            <h1>Campus Customs Desk</h1>
            <p>Yale merch · your agent team</p>
          </div>
        </div>
        <div className="topbar-right">
          {waiting.length > 0 && (
            <button className="badge-button" onClick={() => document.getElementById('approvals')?.scrollIntoView({ behavior: 'smooth' })}>
              {waiting.length} to approve
            </button>
          )}
          <span className={`conn ${error ? 'down' : 'up'}`}>
            <span className="dot" /> {error ? 'Backend offline' : 'Backend connected'}
          </span>
          <button className="btn ghost" onClick={() => setConfirm({ kind: 'reset' })} disabled={busy}>
            Fresh run
          </button>
        </div>
      </header>

      {error && (
        <div className="banner">
          <BulldogFace size={34} sleeping />
          <div>
            <strong>{error}.</strong> Start it from the <code>backend/</code> folder with{' '}
            <code>uvicorn main:app --reload --port 8000</code>. This page will reconnect by itself ({API_URL}).
          </div>
        </div>
      )}

      <main className="layout">
        <aside className="col-left">
          <TicketList tickets={tickets} selectedId={selectedId} runningId={runningId} onSelect={setSelectedId} />
        </aside>

        <section className="col-main">
          {selected ? (
            <TicketDesk
              ticket={selected}
              events={ticketEvents}
              runningId={runningId}
              otherRunning={busy && runningId !== selected.id && !selected.running}
              onRun={onRun}
              onResolve={() => (approver.trim() ? setConfirm({ kind: 'resolve', ticketId: selected.id }) : toast('info', 'Type your name under "Approving as" first.'))}
            />
          ) : (
            <div className="panel empty big">
              <BulldogFace size={90} sleeping />
              <p>{error ? 'Waiting for the backend…' : 'Pick a ticket to get started.'}</p>
            </div>
          )}
        </section>

        <aside className="col-right">
          <CashCard cash={cash} />
          <ApprovalQueue
            proposals={proposals}
            cash={cash}
            approver={approver}
            onApproverChange={onApproverChange}
            busyId={busyId}
            errors={cardErrors}
            highlight={attention}
            onApprove={(p) => setConfirm({ kind: 'approve', p })}
            onReject={(p) => setConfirm({ kind: 'reject', p })}
          />
        </aside>
      </main>

      {confirm?.kind === 'approve' && (
        <ConfirmModal title={`Pay ${money(confirm.p.amount)}?`} confirmLabel="Yes, approve & pay" busy={working} onConfirm={doConfirm} onCancel={() => setConfirm(null)}>
          <p>
            This takes <strong>{money(confirm.p.amount)}</strong> out of checking, recorded as approved by <strong>{approver.trim()}</strong>. Nothing is sent to anyone; it only updates the shop's books.
          </p>
        </ConfirmModal>
      )}
      {confirm?.kind === 'reject' && (
        <ConfirmModal title="Reject this one?" confirmLabel="Reject" tone="danger" busy={working} onConfirm={doConfirm} onCancel={() => setConfirm(null)}>
          <p>
            No money moves. The {money(confirm.p.amount)} stays in checking and your name ({approver.trim()}) is recorded on the decision.
          </p>
        </ConfirmModal>
      )}
      {confirm?.kind === 'resolve' && (
        <ConfirmModal title={`Resolve ticket #${confirm.ticketId}?`} confirmLabel="Mark resolved" busy={working} onConfirm={doConfirm} onCancel={() => setConfirm(null)}>
          <p>No money moves. This closes the ticket as resolved, recorded under your name ({approver.trim()}).</p>
          <label className="resolve-note">
            <span>What did you decide? (optional)</span>
            <textarea value={resolveNote} onChange={(e) => setResolveNote(e.target.value)} maxLength={500} rows={3} placeholder="e.g. Offered the club the 8 hoodies we have at 10% off" />
          </label>
        </ConfirmModal>
      )}
      {confirm?.kind === 'reset' && (
        <ConfirmModal title="Start a fresh run?" confirmLabel="Reset" tone="danger" busy={working} onConfirm={doConfirm} onCancel={() => setConfirm(null)}>
          <p>
            This puts the shop's database back to its original numbers: checking back to the start, no payments, every ticket open again. The audit trail is kept.
          </p>
        </ConfirmModal>
      )}

      <Toasts toasts={toasts} onDismiss={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
    </div>
  )
}
