// Small hand-drawn SVG bulldog bits. They are used sparingly: the logo, the boss's avatar,
// empty states, and paw prints on the "resolved" stamp and the "running" animation.

interface FaceProps {
  size?: number
  sleeping?: boolean
  className?: string
}

export function BulldogFace({ size = 48, sleeping = false, className }: FaceProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Bulldog">
      <path d="M13 22c-8-2-8 14-2 18 4-2 6-8 6-14z" fill="#c99a6e" />
      <path d="M51 22c8-2 8 14 2 18-4-2-6-8-6-14z" fill="#c99a6e" />
      <rect x="13" y="15" width="38" height="33" rx="16" fill="#f3d9bf" />
      <path d="M20 21q4-3 8-1M36 20q4-2 8 1" fill="none" stroke="#d9b48f" strokeWidth="1.6" strokeLinecap="round" />
      <ellipse cx="32" cy="38" rx="15" ry="10" fill="#fbeedd" />
      <rect x="26.5" y="30" width="11" height="7" rx="3.5" fill="#3b3b4f" />
      {sleeping ? (
        <g fill="none" stroke="#3b3b4f" strokeWidth="1.8" strokeLinecap="round">
          <path d="M20.5 26q3 2.6 6 0" />
          <path d="M37.5 26q3 2.6 6 0" />
        </g>
      ) : (
        <g fill="#3b3b4f">
          <circle cx="23.5" cy="26" r="2.6" />
          <circle cx="40.5" cy="26" r="2.6" />
          <circle cx="24.3" cy="25.2" r="0.8" fill="#fff" />
          <circle cx="41.3" cy="25.2" r="0.8" fill="#fff" />
        </g>
      )}
      <path d="M32 37v3m0 0c-3 4-8 3-10-1m10 1c3 4 8 3 10-1" fill="none" stroke="#3b3b4f" strokeWidth="1.8" strokeLinecap="round" />
      <rect x="35.6" y="41" width="2.6" height="3.4" rx="1.1" fill="#fff" stroke="#e5d3bd" strokeWidth="0.5" />
      <path d="M15 50q17 9 34 0v5q-17 9-34 0z" fill="#355c9a" />
      <circle cx="32" cy="57.5" r="2.4" fill="#ffe08a" stroke="#d9b64f" strokeWidth="0.8" />
    </svg>
  )
}

export function PawPrint({ size = 16, className }: { size?: number; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
      <ellipse cx="12" cy="16.5" rx="5.2" ry="4.2" />
      <ellipse cx="5.2" cy="10.4" rx="2.1" ry="2.7" transform="rotate(-18 5.2 10.4)" />
      <ellipse cx="9.6" cy="5.8" rx="2.1" ry="2.8" transform="rotate(-6 9.6 5.8)" />
      <ellipse cx="14.4" cy="5.8" rx="2.1" ry="2.8" transform="rotate(6 14.4 5.8)" />
      <ellipse cx="18.8" cy="10.4" rx="2.1" ry="2.7" transform="rotate(18 18.8 10.4)" />
    </svg>
  )
}

/** Three paw prints that light up one after another: the "agents are working" indicator. */
export function PawTrail() {
  return (
    <span className="paw-trail" aria-label="Working">
      <PawPrint size={14} />
      <PawPrint size={14} />
      <PawPrint size={14} />
    </span>
  )
}
