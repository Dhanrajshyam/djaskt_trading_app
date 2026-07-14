import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
}

/** Base dark card used throughout the app — matches the reference design's panels. */
export function Card({ children, className = '' }: CardProps) {
  return (
    <div className={`bg-slate-900 border border-slate-800 rounded-xl p-4 ${className}`}>
      {children}
    </div>
  )
}

interface CardHeaderProps {
  icon: ReactNode
  title: string
}

/** Standard card header: icon + title + bottom border, matching every panel in the reference. */
export function CardHeader({ icon, title }: CardHeaderProps) {
  return (
    <div className="flex items-center gap-2 mb-4 border-b border-slate-800 pb-2">
      {icon}
      <h2 className="font-semibold text-white">{title}</h2>
    </div>
  )
}
