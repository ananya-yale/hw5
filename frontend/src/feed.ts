// Turns the raw audit events from GET /events into things the desk can show:
//   * a feed of readable steps (who asked whom, which tool ran and what it found, what each agent answered)
//   * a one-card-per-agent summary of what each agent did on the ticket
// Only the events of the ticket's latest run (after the last database reset) are used.

import { AGENTS, type AgentId } from './agents'
import { money, plural } from './format'
import type { AgentEvent, Decision } from './types'

type Obj = Record<string, unknown>

export type FeedItem =
  | { kind: 'system'; key: string; time: string; text: string }
  | { kind: 'delegation'; key: string; time: string; from: string; to: string; text: string }
  | {
      kind: 'tool'
      key: string
      time: string
      agent: string
      tool: string
      args: string
      done: boolean
      summary: string | null
      raw: string | null
    }
  | { kind: 'answer'; key: string; time: string; agent: string; data: Obj | null; raw: string }
  | { kind: 'say'; key: string; time: string; agent: string; text: string }
  | { kind: 'error'; key: string; time: string; agent: string; text: string }
  | { kind: 'human'; key: string; time: string; text: string; tone: 'good' | 'bad' | 'neutral' }
  | { kind: 'cache'; key: string; time: string; agent: string; to: string }

export function looseParse(s: string | undefined): Obj | null {
  if (!s) return null
  try {
    const v: unknown = JSON.parse(s)
    return v && typeof v === 'object' && !Array.isArray(v) ? (v as Obj) : null
  } catch {
    return null
  }
}

/** The audit log clips long values; if the JSON was cut off, still try to pull out the summary line. */
function looseSummary(raw: string): string | null {
  const m = /"summary"\s*:\s*"((?:[^"\\]|\\.)*)"/.exec(raw)
  return m ? m[1].replace(/\\"/g, '"').replace(/\\n/g, ' ') : null
}

const num = (v: unknown): number | null => (typeof v === 'number' ? v : null)
const str = (v: unknown): string | null => (typeof v === 'string' ? v : null)

function describeArgs(args: string | undefined): string {
  const o = looseParse(args)
  if (!o) return ''
  return Object.entries(o)
    .filter(([k]) => k !== 'proposed_by' && k !== 'ticket_id')
    .map(([k, v]) => `${k.replace(/_/g, ' ')} ${String(v)}`)
    .join(' · ')
}

/** One short human sentence for what a tool found. */
function describeResult(tool: string, raw: string): string {
  const o = looseParse(raw)
  if (!o) return raw.slice(0, 140)
  if (typeof o.error === 'string') return `Could not: ${o.error}`
  switch (tool) {
    case 'list_open_tickets':
      return `${plural((o.tickets as unknown[] | undefined)?.length ?? 0, 'open ticket')} in the queue`
    case 'get_cash_and_open_invoices':
      return `Checking ${money(num(o.checking_balance))} · ${money(num(o.available_after_commitments))} free after holds · ${plural((o.open_invoices as unknown[] | undefined)?.length ?? 0, 'open invoice')}`
    case 'check_stock_and_restock_vendors': {
      const vs = (o.vendors as Obj[] | undefined) ?? []
      const ready = vs.filter((v) => v.can_ship_new_product_now === true).length
      return `${num(o.qty_on_hand)} on hand · short ${num(o.shortfall)} · ${ready} of ${vs.length} vendors can ship now`
    }
    case 'check_rent_affordability':
      return `Rent ${money(num(o.monthly_rent))} due in ${num(o.days_until_due)} days · ${money(num(o.cash_after_rent))} left after rent`
    case 'get_margin_for_discount':
      return `Margin ${money(num(o.margin_per_unit))}/unit · break-even discount ${num(o.break_even_discount_percent)}% · ${num(o.qty_on_hand)} in stock`
    case 'get_order_fulfillment_blockers': {
      const inv = o.linked_invoice as Obj | null | undefined
      return `${num(o.qty_on_hand)} on hand, short ${num(o.shortfall)}${inv ? ` · invoice #${num(inv.id)} is ${num(inv.days_overdue)} days overdue` : ''}`
    }
    case 'propose_payment':
    case 'propose_purchase_order': {
      const p = o.proposal as Obj | undefined
      if (o.created === false && typeof o.reason === 'string') return `Refused: ${o.reason}`
      if (o.already_proposed && p) return `Already prepared as #${num(p.id)}`
      if (p) return `Prepared #${num(p.id)} · ${money(num(p.amount))} · waiting for a human to approve`
      return 'Done'
    }
    default:
      return raw.slice(0, 140)
  }
}

export function buildFeed(events: AgentEvent[]): FeedItem[] {
  const items: FeedItem[] = []
  const toolAt = new Map<string, number>() // call_id -> index in items
  for (const e of events) {
    const key = String(e.index)
    switch (e.step) {
      case 'run_start':
        items.push({ kind: 'system', key, time: e.time, text: 'The boss picked up the ticket' })
        break
      case 'run_end':
        items.push({ kind: 'system', key, time: e.time, text: e.outcome === 'completed' ? 'Run finished' : `Run ended: ${e.outcome}` })
        break
      case 'delegation':
        items.push({ kind: 'delegation', key, time: e.time, from: e.agent, to: e.to ?? '?', text: e.request ?? '' })
        break
      case 'delegation_cache_hit':
        items.push({ kind: 'cache', key, time: e.time, agent: e.agent, to: e.to ?? '?' })
        break
      case 'tool_call': {
        if (!e.tool || e.tool.startsWith('ask_')) break // delegations are shown by their own event
        toolAt.set(e.call_id ?? key, items.length)
        items.push({ kind: 'tool', key, time: e.time, agent: e.agent, tool: e.tool, args: describeArgs(e.args), done: false, summary: null, raw: null })
        break
      }
      case 'tool_result': {
        const at = toolAt.get(e.call_id ?? '')
        const item = at === undefined ? undefined : items[at]
        if (item && item.kind === 'tool') {
          item.done = true
          item.raw = e.result ?? ''
          item.summary = describeResult(item.tool, e.result ?? '')
        }
        break
      }
      case 'final_output': {
        const raw = e.args ?? ''
        items.push({ kind: 'answer', key, time: e.time, agent: e.agent, data: looseParse(raw), raw })
        break
      }
      case 'model_text':
        items.push({ kind: 'say', key, time: e.time, agent: e.agent, text: e.text ?? '' })
        break
      case 'agent_error':
        items.push({ kind: 'error', key, time: e.time, agent: e.agent, text: e.error ?? 'Something went wrong' })
        break
      case 'human_decision':
        items.push({
          kind: 'human',
          key,
          time: e.time,
          tone: e.approved ? 'good' : 'bad',
          text: `${e.approver} ${e.approved ? 'approved' : 'rejected'} proposal #${e.proposal_id}`,
        })
        break
      case 'ticket_resolved':
        items.push({
          kind: 'human',
          key,
          time: e.time,
          tone: 'good',
          text: `${e.approver} marked the ticket resolved${e.note ? `: "${e.note}"` : ''}`,
        })
        break
      case 'payment_attempt': {
        const ok = (e.result ?? '').includes('"paid": true')
        items.push({ kind: 'human', key, time: e.time, tone: ok ? 'good' : 'bad', text: ok ? `Payment for proposal #${e.proposal_id} went through` : `Payment for proposal #${e.proposal_id} was refused` })
        break
      }
      default:
        break
    }
  }
  return items
}

// --------------------------------------------------------------------------- per-agent summary

export interface AgentSummary {
  id: AgentId
  state: 'idle' | 'working' | 'done' | 'error'
  headline: string | null
  chips: string[]
  tools: { tool: string; count: number }[]
  asked: string[]
}

export function chipsFor(agent: AgentId, d: Obj | null): string[] {
  if (!d) return []
  const out: string[] = []
  switch (agent) {
    case 'inventory': {
      out.push(`${num(d.qty_on_hand)} on hand`, `short ${num(d.shortfall)}`)
      const opts = (d.restock_options as Obj[] | undefined) ?? []
      for (const v of opts.slice(0, 2)) out.push(`${str(v.name)}: ${v.can_ship_now ? 'can ship' : 'blocked'}, ${num(v.lead_days)}d`)
      break
    }
    case 'accounting': {
      if (num(d.checking_balance) !== null) out.push(`${money(num(d.checking_balance))} in checking`)
      for (const p of (d.proposals as Obj[] | undefined) ?? [])
        out.push(p.created ? `${String(p.kind).replace('_', ' ')} ${money(num(p.amount))} prepared` : `${String(p.kind).replace('_', ' ')} refused`)
      break
    }
    case 'facilities':
      out.push(`rent ${money(num(d.monthly_rent))}`, `due in ${num(d.days_until_due)} days`, d.rent_affordable_alone ? 'affordable' : 'not affordable')
      break
    case 'customer_service':
      out.push(plural(((d.drafts as unknown[] | undefined) ?? []).length, 'draft'), 'not sent')
      break
    default:
      break
  }
  return out.filter((c) => !c.includes('null'))
}

export function answerHeadline(data: Obj | null, raw: string): string | null {
  if (data) return str(data.decision) ?? str(data.summary)
  return looseSummary(raw)
}

export function summarizeAgents(events: AgentEvent[], decision: Decision | null): AgentSummary[] {
  return AGENTS.map((meta) => {
    const mine = events.filter((e) => e.agent === meta.id)
    const starts = mine.filter((e) => e.step === 'agent_start').length
    const ends = mine.filter((e) => e.step === 'agent_end').length
    const errored = mine.some((e) => e.step === 'agent_error')
    const toolCounts = new Map<string, number>()
    for (const e of mine) if (e.step === 'tool_call' && e.tool && !e.tool.startsWith('ask_')) toolCounts.set(e.tool, (toolCounts.get(e.tool) ?? 0) + 1)
    const asked = [...new Set(events.filter((e) => e.step === 'delegation' && e.agent === meta.id).map((e) => e.to ?? ''))].filter(Boolean)
    const lastFinal = [...mine].reverse().find((e) => e.step === 'final_output')
    const data = looseParse(lastFinal?.args)
    let headline: string | null = null
    if (meta.id === 'boss' && decision) headline = decision.decision
    else if (data) headline = str(data.summary) ?? str(data.decision)
    else if (lastFinal?.args) headline = looseSummary(lastFinal.args)
    const bossChips = meta.id === 'boss' && decision ? [decision.status.replaceAll('_', ' ')] : []
    return {
      id: meta.id,
      state: starts === 0 ? 'idle' : errored ? 'error' : ends >= starts ? 'done' : 'working',
      headline,
      chips: meta.id === 'boss' ? bossChips : chipsFor(meta.id, data),
      tools: [...toolCounts].map(([tool, count]) => ({ tool, count })),
      asked,
    }
  })
}
