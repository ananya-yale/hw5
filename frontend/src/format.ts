export function money(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '-'
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`
}

/** "+12s" style offset of an event from the start of its run. */
export function offset(iso: string, startIso: string): string {
  const s = Math.max(0, Math.round((Date.parse(iso) - Date.parse(startIso)) / 1000))
  return s < 60 ? `+${s}s` : `+${Math.floor(s / 60)}m${String(s % 60).padStart(2, '0')}s`
}

export function ticketTypeLabel(type: string): string {
  switch (type) {
    case 'customer_order':
      return 'Customer order'
    case 'rent_notice':
      return 'Rent notice'
    case 'price_override':
      return 'Discount request'
    default:
      return type
  }
}
