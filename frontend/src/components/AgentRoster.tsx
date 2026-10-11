import { agentMeta, toolLabel } from '../agents'
import type { AgentSummary } from '../feed'
import { Avatar } from './Avatar'

const STATE_TEXT: Record<AgentSummary['state'], string> = {
  idle: 'Not called',
  working: 'Working…',
  done: 'Done',
  error: 'Hit a snag',
}

/** One card per agent: what it did on this ticket, in a line or two. Fills in live while a run goes. */
export function AgentRoster({ summaries }: { summaries: AgentSummary[] }) {
  return (
    <section className="panel">
      <h2 className="panel-title">What each agent did</h2>
      <div className="roster">
        {summaries.map((s) => {
          const meta = agentMeta(s.id)
          return (
            <article key={s.id} className={`roster-card agent-${s.id} is-${s.state}`}>
              <header>
                <Avatar agent={s.id} size={34} />
                <div>
                  <h3>{meta.label}</h3>
                  <span className="roster-state">
                    <span className="dot" /> {STATE_TEXT[s.state]}
                  </span>
                </div>
              </header>
              {s.state === 'idle' ? (
                <p className="muted small">{meta.role}</p>
              ) : (
                <>
                  {s.headline ? <p className="roster-line">{s.headline}</p> : <p className="muted small">Still thinking…</p>}
                  {s.chips.length > 0 && (
                    <div className="chips">
                      {s.chips.map((c) => (
                        <span key={c} className="chip">
                          {c}
                        </span>
                      ))}
                    </div>
                  )}
                  {s.asked.length > 0 && <p className="small muted">Asked: {s.asked.map((a) => agentMeta(a).label).join(', ')}</p>}
                  {s.tools.length > 0 && (
                    <p className="small muted">
                      Used: {s.tools.map((t) => `${toolLabel(t.tool)}${t.count > 1 ? ` ×${t.count}` : ''}`).join('; ')}
                    </p>
                  )}
                </>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
