import { Activity, Briefcase, Database, Landmark, Server, Zap } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { ArchitectureDiagram } from '../features/design/ArchitectureDiagram'

interface BuiltItem {
  name: string
  status: 'live' | 'planned'
  description: string
}

// Sourced from docs/architecture/architecture_diagram.py + its README (the
// verified, ground-truth real-vs-planned split established this session) —
// not the aspirational gemini/architectture_diagrams.py reference.
const BUILT_ITEMS: BuiltItem[] = [
  { name: 'nginx', status: 'live', description: 'Single public entry point. Serves the React SPA static build and proxies /api/ and /ws/ to Django.' },
  { name: 'accounts (Django)', status: 'live', description: 'JWT auth — signup, login, refresh, logout, and a Redis-backed denylist for revoked tokens.' },
  { name: 'ledger (Django)', status: 'live', description: 'The ACID core: Portfolio/Position/Trade/CashTransaction, idempotent trade execution with SELECT FOR UPDATE row locking, and a Channels WebSocket consumer broadcasting live portfolio updates.' },
  { name: 'brokerage (Django)', status: 'live', description: 'Links a user to a real broker (Angel One), authenticates via a Strategy-pattern per broker, and caches the session in Redis with an IST-midnight TTL.' },
  { name: 'Redis', status: 'live', description: 'Three real roles today: the Channels layer for WebSocket broadcast, the JWT denylist, and the brokerage session cache. A price-cache read path exists but has no writer yet.' },
  { name: 'Postgres', status: 'live', description: 'External to Docker (reached via host.docker.internal), a single instance — the "replica" env vars are wired but point at the same instance; no real replication is configured.' },
  { name: 'Infisical Vault', status: 'live', description: 'Optional secret source for SECRET_KEY and DB/Redis passwords, falling back to .env when unconfigured.' },
  { name: 'FastAPI — Market Data Firehose', status: 'planned', description: 'Would stream live ticks and write them into the Redis price cache (TICKER:{symbol}:PRICE, 10s TTL) for the ledger to read. Spec exists; no code yet.' },
  { name: 'Flask — Analytics Engine', status: 'planned', description: 'Would run CPU-bound reporting against a Postgres read-replica and stream PDF/CSV statements. Spec exists; no code yet.' },
]

export default function DesignPage() {
  return (
    <div className="space-y-10 pb-10">
      {/* Hero */}
      <div className="text-center pt-6">
        <div className="inline-flex p-3 bg-indigo-600 rounded-xl mb-4">
          <Activity className="w-7 h-7 text-white" />
        </div>
        <h1 className="text-3xl font-bold text-white">Aegis Financial Terminal</h1>
        <p className="text-slate-400 mt-2 max-w-2xl mx-auto">
          A distributed, real-time paper-trading and collaborative financial analysis platform —
          the original design intent behind Djaskt Trading, and what's actually been built so far.
        </p>
      </div>

      {/* The Idea */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-1">The Idea</h2>
        <p className="text-sm text-slate-400 mb-4">
          A polyglot Python microservice architecture, isolating workloads by their compute pattern
          rather than putting everything in one framework.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <div className="flex items-center gap-2 mb-2">
              <Server className="w-5 h-5 text-emerald-400" />
              <h3 className="font-semibold text-white">Django — State</h3>
            </div>
            <p className="text-sm text-slate-400">
              The system of record. Strict ACID double-entry ledger, row-level locking to prevent
              double-spending, and idempotent trade execution.
            </p>
          </Card>
          <Card>
            <div className="flex items-center gap-2 mb-2">
              <Zap className="w-5 h-5 text-yellow-400" />
              <h3 className="font-semibold text-white">FastAPI — Async I/O</h3>
            </div>
            <p className="text-sm text-slate-400">
              High-throughput, non-blocking ingestion of external market data ticks, broadcast to
              clients over WebSockets.
            </p>
          </Card>
          <Card>
            <div className="flex items-center gap-2 mb-2">
              <Briefcase className="w-5 h-5 text-purple-400" />
              <h3 className="font-semibold text-white">Flask — Analytics</h3>
            </div>
            <p className="text-sm text-slate-400">
              CPU-bound historical computation and report generation, offloaded from the
              transactional ledger entirely.
            </p>
          </Card>
        </div>
      </section>

      {/* What We Built */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-1">What We Built</h2>
        <p className="text-sm text-slate-400 mb-4">
          A reality check against the original design — what's actually running today versus what's
          still just a spec.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {BUILT_ITEMS.map((item) => (
            <Card key={item.name}>
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-white text-sm">{item.name}</h3>
                <Badge tone={item.status === 'live' ? 'success' : 'warning'}>
                  {item.status === 'live' ? 'Live' : 'Planned'}
                </Badge>
              </div>
              <p className="text-sm text-slate-400">{item.description}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* Architecture Diagram */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-1">Architecture</h2>
        <p className="text-sm text-slate-400 mb-4">
          Live request flow, animated — matches docs/architecture/architecture_diagram.py.
        </p>
        <Card>
          <div className="flex items-center gap-2 mb-4 border-b border-slate-800 pb-2">
            <Database className="w-5 h-5 text-indigo-400" />
            <h3 className="font-semibold text-white">System Topology</h3>
          </div>
          <ArchitectureDiagram />
        </Card>
      </section>

      {/* Key design decisions */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-4">Key Design Decisions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <div className="flex items-center gap-2 mb-1">
              <Landmark className="w-4 h-4 text-indigo-400" />
              <h3 className="font-semibold text-white text-sm">Idempotency everywhere</h3>
            </div>
            <p className="text-sm text-slate-400">
              Every trade and cash transfer carries a client-generated UUID — a retried request
              never double-executes.
            </p>
          </Card>
          <Card>
            <div className="flex items-center gap-2 mb-1">
              <Landmark className="w-4 h-4 text-indigo-400" />
              <h3 className="font-semibold text-white text-sm">Pessimistic locking</h3>
            </div>
            <p className="text-sm text-slate-400">
              SELECT FOR UPDATE on Portfolio and Position inside transaction.atomic() guarantees
              zero double-spending under concurrent trades.
            </p>
          </Card>
          <Card>
            <div className="flex items-center gap-2 mb-1">
              <Landmark className="w-4 h-4 text-indigo-400" />
              <h3 className="font-semibold text-white text-sm">Opaque broker credentials</h3>
            </div>
            <p className="text-sm text-slate-400">
              A common envelope (brokerage_name) with an opaque per-broker payload — each broker's
              own auth strategy knows what fields it needs, the API layer doesn't.
            </p>
          </Card>
          <Card>
            <div className="flex items-center gap-2 mb-1">
              <Landmark className="w-4 h-4 text-indigo-400" />
              <h3 className="font-semibold text-white text-sm">IST-midnight session TTL</h3>
            </div>
            <p className="text-sm text-slate-400">
              A linked broker's cached session expires at the next IST midnight, not a fixed
              duration — matching how a trading day actually ends.
            </p>
          </Card>
        </div>
      </section>
    </div>
  )
}
