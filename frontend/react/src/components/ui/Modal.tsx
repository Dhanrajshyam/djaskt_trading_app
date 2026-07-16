import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}

/** Lightweight in-app modal — first one in the codebase, hand-rolled to
 * match Card/Badge/Button's style rather than pulling in a dialog library. */
export function Modal({ open, onClose, title, children }: ModalProps) {
  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
      onClick={onClose}
    >
      <div
        className="bg-slate-900 border border-slate-800 rounded-xl p-6 w-full max-w-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-white">{title}</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  )
}
