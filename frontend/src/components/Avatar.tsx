import { agentMeta } from '../agents'
import { BulldogFace } from './Bulldog'

export function Avatar({ agent, size = 32 }: { agent: string; size?: number }) {
  const meta = agentMeta(agent)
  return (
    <span className={`avatar agent-${meta.id}`} style={{ width: size, height: size, fontSize: size * 0.5 }} title={meta.label}>
      {meta.id === 'boss' ? <BulldogFace size={size * 0.9} /> : meta.icon}
    </span>
  )
}

export function AgentChip({ agent }: { agent: string }) {
  const meta = agentMeta(agent)
  return <span className={`agent-chip agent-${meta.id}`}>{meta.label}</span>
}
