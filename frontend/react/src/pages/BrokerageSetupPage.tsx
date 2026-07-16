import { useState } from 'react'
import { Landmark } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { KNOWN_BROKERAGES } from '../features/brokerage/brokerageApi'
import { useBrokerageLinks, useDeleteBrokerageLink, useBrokerageLogout } from '../features/brokerage/useBrokerageLinks'
import { LinkBrokerageModal } from '../features/brokerage/LinkBrokerageModal'
import { BrokerLoginModal } from '../features/brokerage/BrokerLoginModal'

export default function BrokerageSetupPage() {
  const { data: links, isLoading, isError } = useBrokerageLinks()
  const deleteLinkMutation = useDeleteBrokerageLink()
  const logoutMutation = useBrokerageLogout()

  const [linkModalBrokerage, setLinkModalBrokerage] = useState<string | null>(null)
  const [loginModalBrokerage, setLoginModalBrokerage] = useState<string | null>(null)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Brokerage Setup</h1>
        <p className="text-sm text-slate-400">Link and connect the brokerages you trade through.</p>
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading brokerages…</p>}
      {isError && <p className="text-sm text-rose-400">Couldn't load your brokerage links.</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {KNOWN_BROKERAGES.map((brokerage) => {
          const link = links?.find((l) => l.brokerage_name === brokerage.name)

          return (
            <Card key={brokerage.name}>
              <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
                <div className="flex items-center gap-2">
                  <Landmark className="w-5 h-5 text-indigo-400" />
                  <h2 className="font-semibold text-white">{brokerage.displayName}</h2>
                </div>
                {link ? (
                  link.is_connected ? (
                    <Badge tone="success">Connected</Badge>
                  ) : (
                    <Badge tone="warning">Disconnected</Badge>
                  )
                ) : (
                  <Badge tone="neutral">Not linked</Badge>
                )}
              </div>

              <div className="flex items-center gap-2">
                {!link && (
                  <Button variant="primary" onClick={() => setLinkModalBrokerage(brokerage.name)}>
                    Link
                  </Button>
                )}

                {link && !link.is_connected && (
                  <Button variant="primary" onClick={() => setLoginModalBrokerage(brokerage.name)}>
                    Connect
                  </Button>
                )}

                {link && link.is_connected && (
                  <Button
                    variant="sell"
                    disabled={logoutMutation.isPending}
                    onClick={() => logoutMutation.mutate({ brokerage_name: brokerage.name })}
                  >
                    {logoutMutation.isPending ? 'Disconnecting…' : 'Disconnect'}
                  </Button>
                )}

                {link && (
                  <Button
                    variant="ghost"
                    disabled={deleteLinkMutation.isPending}
                    onClick={() => deleteLinkMutation.mutate(link.id)}
                  >
                    Remove link
                  </Button>
                )}
              </div>
            </Card>
          )
        })}
      </div>

      <LinkBrokerageModal
        open={linkModalBrokerage !== null}
        onClose={() => setLinkModalBrokerage(null)}
        brokerageName={linkModalBrokerage ?? ''}
        displayName={
          KNOWN_BROKERAGES.find((b) => b.name === linkModalBrokerage)?.displayName ?? ''
        }
      />

      <BrokerLoginModal
        open={loginModalBrokerage !== null}
        onClose={() => setLoginModalBrokerage(null)}
        brokerageName={loginModalBrokerage ?? ''}
        displayName={
          KNOWN_BROKERAGES.find((b) => b.name === loginModalBrokerage)?.displayName ?? ''
        }
      />
    </div>
  )
}
