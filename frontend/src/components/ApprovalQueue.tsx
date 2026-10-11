import { agentMeta } from '../agents'
import { money } from '../format'
import type { Cash, Proposal } from '../types'
import { BulldogFace, PawPrint } from './Bulldog'

function describe(p: Proposal): { title: string; detail: string } {
  switch (p.kind) {
    case 'invoice':
      return { title: `Pay vendor invoice #${p.ref_id}`, detail: p.vendor_id ? `Vendor #${p.vendor_id}` : 'Vendor invoice' }
    case 'rent':
      return { title: 'Pay rent', detail: `Lease #${p.ref_id}` }
    case 'purchase_order':
      return {
        title: 'Place purchase order',
        detail: `${p.qty} × ${p.sku}${p.size ? ` (${p.size})` : ''} from vendor #${p.vendor_id}`,
      }
  }
}

interface Props {
  proposals: Proposal[]
  cash: Cash | null
  approver: string
  onApproverChange: (name: string) => void
  busyId: number | null
  errors: Record<number, string>
  highlight: boolean
  onApprove: (p: Proposal) => void
  onReject: (p: Proposal) => void
}

export function ApprovalQueue({ proposals, cash, approver, onApproverChange, busyId, errors, highlight, onApprove, onReject }: Props) {
  const waiting = proposals.filter((p) => p.status === 'pending' || p.status === 'approved')
  const paid = proposals.filter((p) => p.status === 'paid')
  const noName = approver.trim() === ''
  return (
    <section className={`panel approvals${waiting.length > 0 && highlight ? ' attention' : ''}`} id="approvals">
      <h2 className="panel-title">
        <PawPrint size={16} /> Waiting for you
        {waiting.length > 0 && <span className="count-badge">{waiting.length}</span>}
      </h2>

      <label className="approver">
        <span>Approving as</span>
        <input value={approver} onChange={(e) => onApproverChange(e.target.value)} placeholder="Your name" maxLength={80} />
      </label>

      {waiting.length === 0 ? (
        <div className="empty">
          <BulldogFace size={56} sleeping />
          <p>Nothing to approve. Good dog.</p>
          <p className="muted small">Agents only prepare payments. You decide here.</p>
        </div>
      ) : (
        <ul className="proposal-list">
          {waiting.map((p) => {
            const { title, detail } = describe(p)
            const after = cash ? cash.checking_balance - p.amount : null
            const short = after !== null && after < 0
            // Invoices that blocked this order may have been paid since it was prepared.
            const blockers = p.blocked_by_invoice_ids.filter((id) => !paid.some((x) => x.kind === 'invoice' && x.ref_id === id))
            return (
              <li key={p.id} className={`proposal kind-${p.kind}`}>
                <div className="proposal-head">
                  <span className="proposal-title">{title}</span>
                  {p.ticket_id && <span className="mini-tag">Ticket #{p.ticket_id}</span>}
                </div>
                <div className="proposal-amount">{money(p.amount)}</div>
                <div className="muted small">{detail}</div>
                <div className="muted small">
                  Prepared by <span className={`agent-chip agent-${agentMeta(p.proposed_by ?? 'accounting').id}`}>{agentMeta(p.proposed_by ?? 'accounting').label}</span>
                </div>
                {blockers.length > 0 && (
                  <div className="note warn">Vendor won't ship until invoice #{blockers.join(', #')} is paid. Pay that first.</div>
                )}
                {after !== null && (
                  <div className={`note ${short ? 'bad' : 'soft'}`}>
                    {short ? `Not enough cash: this would leave ${money(after)}, so it will be refused.` : `Checking after paying: ${money(after)}`}
                  </div>
                )}
                {p.status === 'approved' && <div className="note soft">Already approved. Approve again to retry the payment.</div>}
                {errors[p.id] && <div className="note bad">{errors[p.id]}</div>}
                <div className="proposal-actions">
                  <button className="btn primary" disabled={noName || busyId !== null} onClick={() => onApprove(p)}>
                    {busyId === p.id ? 'Paying…' : 'Approve & pay'}
                  </button>
                  {p.status === 'pending' && (
                    <button className="btn ghost" disabled={noName || busyId !== null} onClick={() => onReject(p)}>
                      Reject
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
      {waiting.length > 0 && noName && <p className="note soft">Type your name above to enable the buttons.</p>}

      {paid.length > 0 && (
        <div className="paid">
          <h3>Paid so far</h3>
          <ul>
            {paid.map((p) => (
              <li key={p.id}>
                <span>{describe(p).title}</span>
                <strong>{money(p.amount)}</strong>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
