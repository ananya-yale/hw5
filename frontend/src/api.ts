import type {
  Cash,
  EventsResponse,
  PayResult,
  Proposal,
  RunResponse,
  TicketsResponse,
} from './types'

// The backend from output/harness.md. It allows this page's origin (http://localhost:5173).
export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** FastAPI errors come back as {detail: string | object | list}; turn any of them into one sentence. */
function detailToMessage(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d === 'object' && d && 'msg' in d ? String((d as { msg: unknown }).msg) : String(d))).join('; ')
  }
  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>
    return String(d.reason ?? d.error ?? d.note ?? JSON.stringify(d))
  }
  return 'Something went wrong'
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_URL}`)
  }
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? (body as { detail: unknown }).detail : body
    throw new ApiError(res.status, detailToMessage(detail))
  }
  return body as T
}

export const getTickets = () => request<TicketsResponse>('/tickets')
export const getCash = () => request<Cash>('/cash')
export const getProposals = () => request<{ proposals: Proposal[] }>('/proposals')
export const getEvents = (after: number | null, limit = 500) =>
  request<EventsResponse>(`/events?limit=${limit}${after === null ? '' : `&after=${after}`}`)
export const runTicket = (id: number) => request<RunResponse>(`/tickets/${id}/run`, { method: 'POST' })
export const approveProposal = (id: number, approver: string) =>
  request<PayResult>(`/proposals/${id}/approve`, { method: 'POST', body: JSON.stringify({ approver }) })
export const rejectProposal = (id: number, approver: string) =>
  request<{ approved: false; paid: false }>(`/proposals/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ approver }),
  })
export const resolveTicket = (id: number, approver: string, note: string) =>
  request<{ resolved: boolean; ticket_id: number }>(`/tickets/${id}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ approver, note }),
  })
export const resetDatabase = () => request<Cash & { reset: boolean }>('/reset', { method: 'POST' })
