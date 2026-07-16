import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Button } from '../../components/ui/Button'
import { useCreateBrokerageLink } from './useBrokerageLinks'
import { ApiError } from '../../lib/apiClient'

interface LinkBrokerageModalProps {
  open: boolean
  onClose: () => void
  brokerageName: string
  displayName: string
}

/** Stores semi-stable identifiers (client_id, api_key) once, set up before
 * ever logging in — never a password/TOTP, which are submitted fresh at
 * login time via BrokerLoginModal and never stored (see
 * brokerage/api/schemas.py's UserBrokerageLinkCreateSchema docstring). */
export function LinkBrokerageModal({ open, onClose, brokerageName, displayName }: LinkBrokerageModalProps) {
  const [clientId, setClientId] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState<string | null>(null)
  const createLinkMutation = useCreateBrokerageLink()

  function handleClose() {
    setClientId('')
    setApiKey('')
    setError(null)
    onClose()
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      await createLinkMutation.mutateAsync({
        brokerage_name: brokerageName,
        user_brokerage_data: { client_id: clientId, api_key: apiKey },
      })
      handleClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    }
  }

  return (
    <Modal open={open} onClose={handleClose} title={`Link ${displayName}`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-rose-400/10 border border-rose-400/30 text-rose-300 text-sm rounded p-3">
            {error}
          </div>
        )}

        <div>
          <label className="block text-xs text-slate-400 mb-1" htmlFor="link-client-id">
            Client ID
          </label>
          <input
            id="link-client-id"
            type="text"
            required
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-white outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1" htmlFor="link-api-key">
            API Key
          </label>
          <input
            id="link-api-key"
            type="text"
            required
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-white outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        <Button type="submit" disabled={createLinkMutation.isPending} className="w-full">
          {createLinkMutation.isPending ? 'Linking…' : 'Link'}
        </Button>
      </form>
    </Modal>
  )
}
