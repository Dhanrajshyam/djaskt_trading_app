import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Button } from '../../components/ui/Button'
import { useBrokerageLogin } from './useBrokerageLinks'
import { ApiError } from '../../lib/apiClient'

interface BrokerLoginModalProps {
  open: boolean
  onClose: () => void
  brokerageName: string
  displayName: string
}

/** Password + TOTP submitted straight to our own backend (not a third-party
 * OAuth redirect), so an in-app modal is the right fit — see
 * brokerage/api/schemas.py's BrokerLoginRequestSchema for the envelope this
 * mirrors ({ brokerage_name, user_credentials: {...} }). */
export function BrokerLoginModal({ open, onClose, brokerageName, displayName }: BrokerLoginModalProps) {
  const [password, setPassword] = useState('')
  const [totp, setTotp] = useState('')
  const [error, setError] = useState<string | null>(null)
  const loginMutation = useBrokerageLogin()

  function handleClose() {
    setPassword('')
    setTotp('')
    setError(null)
    onClose()
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      await loginMutation.mutateAsync({
        brokerage_name: brokerageName,
        user_credentials: { password, totp },
      })
      handleClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    }
  }

  return (
    <Modal open={open} onClose={handleClose} title={`Connect ${displayName}`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-rose-400/10 border border-rose-400/30 text-rose-300 text-sm rounded p-3">
            {error}
          </div>
        )}

        <div>
          <label className="block text-xs text-slate-400 mb-1" htmlFor="broker-password">
            Password
          </label>
          <input
            id="broker-password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-white outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1" htmlFor="broker-totp">
            TOTP
          </label>
          <input
            id="broker-totp"
            type="text"
            inputMode="numeric"
            required
            value={totp}
            onChange={(e) => setTotp(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-white outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        <Button type="submit" disabled={loginMutation.isPending} className="w-full">
          {loginMutation.isPending ? 'Connecting…' : 'Connect'}
        </Button>
      </form>
    </Modal>
  )
}
