import { useState } from 'react'
import { useTradeExecution } from './useTradeExecution'
import { Button } from '../../components/ui/Button'
import { ApiError } from '../../lib/apiClient'
import type { CashDirection } from '../../lib/types'

export function CashTransferForm() {
  const [amount, setAmount] = useState('100')
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'error'; message: string } | null>(
    null,
  )

  const { cashTransferMutation } = useTradeExecution()
  const isSubmitting = cashTransferMutation.isPending

  async function handleTransfer(direction: CashDirection) {
    setFeedback(null)
    const value = Number(amount)
    if (!Number.isFinite(value) || value <= 0) {
      setFeedback({ tone: 'error', message: 'Enter an amount greater than zero.' })
      return
    }

    try {
      const result = await cashTransferMutation.mutateAsync({ direction, amount })
      setFeedback({
        tone: 'success',
        message: `${direction === 'CREDIT' ? 'Deposited' : 'Withdrew'} $${result.amount}. New balance: $${result.resulting_balance}.`,
      })
    } catch (err) {
      setFeedback({
        tone: 'error',
        message: err instanceof ApiError ? err.message : 'Transfer failed. Please try again.',
      })
    }
  }

  return (
    <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
      <label className="block text-xs text-slate-400 mb-1" htmlFor="cash-amount">
        Amount
      </label>
      <input
        id="cash-amount"
        type="number"
        min="1"
        step="0.01"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white outline-none focus:border-indigo-500 transition-colors mb-4"
      />

      {feedback && (
        <div
          className={`text-sm rounded p-2 mb-4 ${
            feedback.tone === 'success'
              ? 'bg-emerald-400/10 text-emerald-300 border border-emerald-400/30'
              : 'bg-rose-400/10 text-rose-300 border border-rose-400/30'
          }`}
        >
          {feedback.message}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Button variant="ghost" disabled={isSubmitting} onClick={() => handleTransfer('CREDIT')}>
          Deposit
        </Button>
        <Button variant="ghost" disabled={isSubmitting} onClick={() => handleTransfer('DEBIT')}>
          Withdraw
        </Button>
      </div>
    </div>
  )
}
