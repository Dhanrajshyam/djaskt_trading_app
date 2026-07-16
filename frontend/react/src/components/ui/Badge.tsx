import type { ReactNode } from 'react'

type Tone = 'neutral' | 'warning' | 'success'

const TONE_CLASSES: Record<Tone, string> = {
  neutral: 'bg-slate-800 text-slate-300 border-slate-700',
  warning: 'bg-amber-400/10 text-amber-300 border-amber-400/30',
  success: 'bg-emerald-400/10 text-emerald-300 border-emerald-400/30',
}

/** Small pill label — used for the "Simulated data" / "Reference only" tags. */
export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full border font-medium ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  )
}
