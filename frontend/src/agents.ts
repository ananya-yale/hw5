// How each agent looks and reads on the desk. One pastel colour per agent, so you can tell
// who is speaking before reading a word. Colours live in styles.css (--agent-<id>).

export type AgentId = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface AgentMeta {
  id: AgentId
  label: string
  role: string
  icon: string // emoji; the boss gets the bulldog face instead (see Avatar)
}

export const AGENTS: AgentMeta[] = [
  { id: 'boss', label: 'Boss', role: 'Reads the ticket, delegates, decides', icon: '🐾' },
  { id: 'inventory', label: 'Inventory', role: 'Stock, shortfalls, restock vendors', icon: '📦' },
  { id: 'accounting', label: 'Accounting', role: 'Cash, invoices, prepares payments', icon: '🧾' },
  { id: 'facilities', label: 'Facilities', role: 'Lease, rent, shop space', icon: '🔑' },
  { id: 'customer_service', label: 'Customer Service', role: 'Drafts replies (never sends)', icon: '✉️' },
]

const BY_ID = new Map<string, AgentMeta>(AGENTS.map((a) => [a.id, a]))

export function agentMeta(id: string): AgentMeta {
  return BY_ID.get(id) ?? { id: id as AgentId, label: id, role: '', icon: '•' }
}

export const TOOL_LABELS: Record<string, string> = {
  list_open_tickets: 'Reading the ticket queue',
  get_order_fulfillment_blockers: 'Checking what blocks the order',
  check_rent_affordability: 'Checking if rent is affordable',
  get_margin_for_discount: 'Checking the discount margin',
  check_stock_and_restock_vendors: 'Checking stock and restock vendors',
  get_cash_and_open_invoices: 'Checking cash and open invoices',
  propose_payment: 'Preparing a payment for approval',
  propose_purchase_order: 'Preparing a purchase order for approval',
}

export function toolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? tool
}
