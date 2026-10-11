// Shapes of what the backend (backend/main.py) returns.

export type ProposalKind = 'invoice' | 'rent' | 'purchase_order'
export type ProposalStatus = 'pending' | 'approved' | 'rejected' | 'paid'

export interface Proposal {
  id: number
  kind: ProposalKind
  ref_id: number
  vendor_id: number | null
  sku: string | null
  size: string | null
  qty: number | null
  amount: number
  status: ProposalStatus
  blocked_by_invoice_ids: number[]
  proposed_by: string | null
  ticket_id: number | null
  approved_by: string | null
  created_on: string | null
}

export interface Draft {
  to: string
  subject: string
  body: string
  status: 'draft_only'
}

export type DecisionStatus = 'ready_pending_human_approval' | 'resolved' | 'blocked' | 'needs_info'

export interface Decision {
  ticket_id: number
  status: DecisionStatus
  decision: string
  rationale: string
  pending_human_approvals: { proposal_id: number | null; kind: ProposalKind; amount: number; note: string }[]
  drafts: Draft[]
  open_questions: string[]
}

export interface Ticket {
  id: number
  type: 'customer_order' | 'rent_notice' | 'price_override' | string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: 'open' | 'resolved'
  notes: string | null
  created_at: string
  proposals: Proposal[]
  last_decision: Decision | null
  running: boolean
}

export interface TicketsResponse {
  date_today: string
  tickets: Ticket[]
}

export interface Cash {
  account: string
  checking_balance: number
  balance_as_of: string
  committed_total: number
  available_after_commitments: number
  date_today: string
}

export interface AgentEvent {
  index: number
  message: string
  run_id: string
  seq: number
  time: string
  ticket_id: number | null
  agent: string
  depth: number
  delegated_by: string | null
  step: string
  tool?: string
  args?: string
  result?: string
  request?: string
  to?: string
  text?: string
  call_id?: string
  error?: string
  outcome?: string
  output?: string
  approver?: string
  approved?: boolean
  proposal_id?: number
  note?: string
}

export interface EventsResponse {
  events: AgentEvent[]
  next_after: number
}

export interface RunResponse {
  ticket_id: number
  run_id: string
  decision: Decision
  delegations: number
  usage: { requests: number; input_tokens: number; output_tokens: number }
}

export interface PayResult {
  approved: boolean
  paid: boolean
  proposal_id: number
  kind: ProposalKind
  amount: number
  new_checking_balance: number
  ticket_id: number | null
  ticket_resolved: boolean
}
