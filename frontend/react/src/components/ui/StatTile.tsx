import type { ReactNode } from 'react'

interface StatTileProps {
  label: string
  value: string
  icon?: ReactNode
  valueClassName?: string
}

/** A single labeled number, e.g. "Available Cash: $50,000.00". */
export function StatTile({ label, value, icon, valueClassName = 'text-white' }: StatTileProps) {
  return (
    <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
      <div className="text-sm text-slate-400 mb-1">{label}</div>
      <div className={`text-2xl font-mono font-bold flex items-center gap-1.5 ${valueClassName}`}>
        {icon}
        {value}
      </div>
    </div>
  )
}
