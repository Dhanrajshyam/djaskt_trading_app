import { useState } from 'react'
import { FileText } from 'lucide-react'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'

/**
 * SIMULATED analytics/reporting panel — the real Flask analytics
 * microservice (gemini/LLD - Flask App.docx) doesn't exist yet. Clicking
 * "Generate Report" fakes the documented Flask contract's latency
 * (POST /api/v1/analytics/report/, a few seconds to compile a PDF
 * server-side) without calling anything real.
 */
export function AnalyticsPanel() {
  const [status, setStatus] = useState<'idle' | 'loading' | 'done'>('idle')

  function handleGenerateReport() {
    setStatus('loading')
    // Simulated latency, matching the LLD's description of Flask querying
    // a read-replica and compiling a PDF in-memory before streaming it back.
    setTimeout(() => setStatus('done'), 2000)
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-blue-400" />
          <h2 className="font-semibold text-white">Analytics</h2>
        </div>
        <Badge tone="warning">Reference only</Badge>
      </div>

      <p className="text-xs text-slate-400 mb-4">
        Historical P&amp;L and tax report generation will be handled by a dedicated Flask reporting
        service, kept separate so heavy PDF generation never blocks the trading API.
      </p>

      <Button
        variant="primary"
        onClick={handleGenerateReport}
        disabled={status === 'loading'}
        className="w-full"
      >
        {status === 'loading' ? 'Generating…' : 'Generate Report (demo)'}
      </Button>

      {status === 'done' && (
        <p className="text-xs text-emerald-400 mt-3 text-center">
          Simulated: report generation complete. (Flask service not yet built — nothing was
          actually downloaded.)
        </p>
      )}
    </Card>
  )
}
