import { useEffect, useRef } from 'react'
import { agentMeta, toolLabel } from '../agents'
import { answerHeadline, chipsFor, type FeedItem } from '../feed'
import { offset } from '../format'
import type { Draft } from '../types'
import { Avatar } from './Avatar'
import { BulldogFace, PawTrail } from './Bulldog'

function Letter({ draft }: { draft: Draft }) {
  return (
    <div className="letter">
      <div className="letter-stamp">Draft · not sent</div>
      <div className="letter-to">To: {draft.to}</div>
      <div className="letter-subject">{draft.subject}</div>
      <p>{draft.body}</p>
    </div>
  )
}

function Item({ item, start }: { item: FeedItem; start: string }) {
  const t = <time>{offset(item.time, start)}</time>
  switch (item.kind) {
    case 'system':
      return (
        <li className="feed-system">
          {t}
          <span>{item.text}</span>
        </li>
      )
    case 'human':
      return (
        <li className={`feed-human tone-${item.tone}`}>
          {t}
          <span>{item.text}</span>
        </li>
      )
    case 'cache':
      return (
        <li className="feed-system">
          {t}
          <span>
            {agentMeta(item.agent).label} re-asked {agentMeta(item.to).label}; reused the earlier answer (saves tokens)
          </span>
        </li>
      )
    case 'delegation':
      return (
        <li className="feed-row feed-delegation">
          <Avatar agent={item.from} size={30} />
          <div className="feed-body">
            <div className="feed-head">
              <strong>{agentMeta(item.from).label}</strong>
              <span className="arrow">asks</span>
              <strong className={`agent-chip agent-${agentMeta(item.to).id}`}>{agentMeta(item.to).label}</strong>
              {t}
            </div>
            <p className="said">{item.text}</p>
          </div>
        </li>
      )
    case 'tool':
      return (
        <li className={`feed-row feed-tool agent-${agentMeta(item.agent).id}`}>
          <Avatar agent={item.agent} size={30} />
          <div className="feed-body">
            <div className="feed-head">
              <strong>{agentMeta(item.agent).label}</strong>
              <span className="tool-chip">{toolLabel(item.tool)}</span>
              {t}
            </div>
            {item.args && <div className="tool-args">{item.args}</div>}
            {item.done ? (
              <details className="tool-result">
                <summary>{item.summary}</summary>
                <pre>{prettyJson(item.raw)}</pre>
              </details>
            ) : (
              <div className="tool-wait">
                <PawTrail /> waiting for the shop's records…
              </div>
            )}
          </div>
        </li>
      )
    case 'say':
      return (
        <li className="feed-row">
          <Avatar agent={item.agent} size={30} />
          <div className="feed-body">
            <div className="feed-head">
              <strong>{agentMeta(item.agent).label}</strong> {t}
            </div>
            <p className="said">{item.text}</p>
          </div>
        </li>
      )
    case 'error':
      return (
        <li className="feed-row feed-error">
          <Avatar agent={item.agent} size={30} />
          <div className="feed-body">
            <div className="feed-head">
              <strong>{agentMeta(item.agent).label}</strong> hit a snag {t}
            </div>
            <p className="said">{item.text}</p>
          </div>
        </li>
      )
    case 'answer': {
      const meta = agentMeta(item.agent)
      const headline = answerHeadline(item.data, item.raw)
      const chips = chipsFor(meta.id, item.data)
      const drafts = Array.isArray(item.data?.drafts) ? (item.data?.drafts as Draft[]) : []
      return (
        <li className={`feed-row feed-answer agent-${meta.id}`}>
          <Avatar agent={item.agent} size={meta.id === 'boss' ? 38 : 30} />
          <div className="feed-body">
            <div className="feed-head">
              <strong>{meta.label}</strong>
              <span className="arrow">{meta.id === 'boss' ? 'decided' : 'reported back'}</span>
              {t}
            </div>
            {headline && <p className={meta.id === 'boss' ? 'bubble' : 'said'}>{headline}</p>}
            {chips.length > 0 && (
              <div className="chips">
                {chips.map((c) => (
                  <span key={c} className="chip">
                    {c}
                  </span>
                ))}
              </div>
            )}
            {drafts.map((d, i) => (
              <Letter key={i} draft={d} />
            ))}
          </div>
        </li>
      )
    }
  }
}

function prettyJson(raw: string | null): string {
  if (!raw) return ''
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

interface Props {
  items: FeedItem[]
  startTime: string | null
  running: boolean
}

export function AgentFeed({ items, startTime, running }: Props) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (running) end.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [items.length, running])

  return (
    <section className="panel feed-panel">
      <h2 className="panel-title">
        Live from the desk {running && <PawTrail />}
      </h2>
      {items.length === 0 ? (
        <div className="empty">
          <BulldogFace size={64} sleeping={!running} />
          <p>{running ? 'The boss is reading the ticket…' : 'No run yet. Start the agent team to watch them work.'}</p>
        </div>
      ) : (
        <ol className="feed">
          {items.map((it) => (
            <Item key={it.key} item={it} start={startTime ?? it.time} />
          ))}
        </ol>
      )}
      <div ref={end} />
    </section>
  )
}
