import { useEffect, useRef, useState } from 'react'
import { money } from '../format'
import { useAnimatedNumber } from '../hooks'
import type { Cash } from '../types'

/**
 * The checking balance. Money only ever leaves in this project, so the card is calm by default and
 * makes one clear moment of the drop: the number counts down and a "-$840.00" chip appears.
 */
export function CashCard({ cash }: { cash: Cash | null }) {
  const balance = cash?.checking_balance ?? 0
  const shown = useAnimatedNumber(balance)
  const prev = useRef<number | null>(null)
  const [drop, setDrop] = useState<number | null>(null)

  useEffect(() => {
    if (!cash) return
    if (prev.current !== null && cash.checking_balance < prev.current - 0.004) {
      setDrop(prev.current - cash.checking_balance)
      const t = setTimeout(() => setDrop(null), 7000)
      prev.current = cash.checking_balance
      return () => clearTimeout(t)
    }
    if (prev.current !== null && cash.checking_balance > prev.current + 0.004) setDrop(null) // e.g. after a fresh run
    prev.current = cash.checking_balance
  }, [cash])

  if (!cash) {
    return (
      <section className="panel cash-card">
        <h2 className="panel-title">Checking</h2>
        <p className="muted small">Counting the coins…</p>
      </section>
    )
  }
  const held = Math.min(cash.committed_total, cash.checking_balance)
  const heldPct = cash.checking_balance > 0 ? (held / cash.checking_balance) * 100 : 0
  return (
    <section className={`panel cash-card${drop !== null ? ' dropped' : ''}`}>
      <h2 className="panel-title">Checking</h2>
      <div className="cash-amount" aria-live="polite">
        {money(shown)}
        {drop !== null && <span className="cash-drop">-{money(drop)}</span>}
      </div>
      <div className="cash-bar" role="img" aria-label={`${money(held)} of ${money(cash.checking_balance)} is held for pending approvals`}>
        <span style={{ width: `${heldPct}%` }} />
      </div>
      <dl className="cash-lines">
        <div>
          <dt>Held for approvals</dt>
          <dd>{money(cash.committed_total)}</dd>
        </div>
        <div>
          <dt>Free to plan with</dt>
          <dd>{money(cash.available_after_commitments)}</dd>
        </div>
      </dl>
      <p className="muted small">As of {cash.balance_as_of}. Money only goes out; the balance can never go below $0.</p>
    </section>
  )
}
