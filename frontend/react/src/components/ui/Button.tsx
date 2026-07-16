import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'buy' | 'sell' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: 'bg-indigo-600 hover:bg-indigo-500 text-white',
  buy: 'bg-emerald-600 hover:bg-emerald-500 text-white',
  sell: 'bg-rose-600 hover:bg-rose-500 text-white',
  ghost: 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700',
}

/** Shared button styling — disabled state is greyed out and non-interactive
 * everywhere in the app, so a trade submit can't be double-clicked while a
 * request is in flight (see features/trading/useTradeExecution.ts). */
export function Button({ variant = 'primary', className = '', disabled, ...rest }: ButtonProps) {
  return (
    <button
      disabled={disabled}
      className={`py-2.5 px-4 rounded font-bold transition-colors active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    />
  )
}
