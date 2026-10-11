import { useEffect, useRef, useState } from 'react'

/** Calls `fn` now and then every `ms` milliseconds (waiting for each call to finish first). */
export function usePoller(fn: () => Promise<unknown> | void, ms: number): void {
  const latest = useRef(fn)
  latest.current = fn
  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout>
    const tick = async () => {
      try {
        await latest.current()
      } finally {
        if (!stopped) timer = setTimeout(tick, ms)
      }
    }
    void tick()
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [ms])
}

/** Eases a number toward `target` so a balance visibly counts down instead of jumping. */
export function useAnimatedNumber(target: number, ms = 800): number {
  const [value, setValue] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    const start = performance.now()
    const begin = from.current
    let raf = 0
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      const eased = 1 - Math.pow(1 - t, 3)
      const v = begin + (target - begin) * eased
      from.current = v
      setValue(v)
      if (t < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return value
}
