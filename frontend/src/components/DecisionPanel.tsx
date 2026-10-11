import type { Decision } from '../types'
import { Avatar } from './Avatar'

const STATUS_TEXT: Record<Decision['status'], string> = {
  ready_pending_human_approval: 'Ready, waiting for your approval',
  resolved: 'Resolved',
  blocked: 'Blocked',
  needs_info: 'Needs your call',
}

/** The boss's final decision for the ticket, plus the reply drafts (never sent). */
export function DecisionPanel({ decision }: { decision: Decision }) {
  // A decision recovered from older records may leave out its optional lists.
  const questions = decision.open_questions ?? []
  const drafts = decision.drafts ?? []
  return (
    <section className="panel decision">
      <h2 className="panel-title">The boss's decision</h2>
      <div className="decision-head">
        <Avatar agent="boss" size={40} />
        <span className={`pill decision-${decision.status}`}>{STATUS_TEXT[decision.status]}</span>
      </div>
      <p className="bubble">{decision.decision}</p>
      <p className="muted">{decision.rationale}</p>
      {questions.length > 0 && (
        <div className="note warn">
          <strong>For you to decide:</strong>
          <ul>
            {questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </div>
      )}
      {drafts.length > 0 && (
        <>
          <h3 className="sub-title">Reply drafts</h3>
          {drafts.map((d, i) => (
            <div className="letter" key={i}>
              <div className="letter-stamp">Draft · not sent</div>
              <div className="letter-to">To: {d.to}</div>
              <div className="letter-subject">{d.subject}</div>
              <p>{d.body}</p>
            </div>
          ))}
        </>
      )}
    </section>
  )
}
