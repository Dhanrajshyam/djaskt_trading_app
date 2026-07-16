import type { ReactNode } from 'react'
import {
  ChromeIcon,
  DjangoIcon,
  DockerIcon,
  FastApiIcon,
  FlaskIcon,
  NginxIcon,
  PostgresIcon,
  RedisIcon,
} from './BrandIcons'

/**
 * Hand-drawn SVG mirror of docs/architecture/architecture_diagram.py —
 * same nodes, same groupings, same real-vs-planned split, so the two stay
 * conceptually in sync even though one is Graphviz output and this one is
 * hand-drawn (Graphviz can't animate a flattened PNG, hence the redraw).
 * Colors are copied directly from that script's palette constants.
 */

const SLATE_900 = '#0f172a'
const SLATE_700 = '#334155'
const SLATE_400 = '#94a3b8'
const SLATE_300 = '#cbd5e1'
const WHITE = '#ffffff'
const INDIGO_500 = '#6366f1'
const EMERALD_500 = '#10b981'
const AMBER_400 = '#fbbf24'
const ROSE_500 = '#f43f5e'
const PURPLE_400 = '#c084fc'
const YELLOW_400 = '#facc15'

interface NodeBoxProps {
  x: number
  y: number
  w: number
  h: number
  label: string
  sublabel?: string
  accent?: string
  dashed?: boolean
  icon?: ReactNode
}

function NodeBox({ x, y, w, h, label, sublabel, accent = SLATE_700, dashed, icon }: NodeBoxProps) {
  const hasIcon = Boolean(icon)
  const centerY = y + h / 2
  const textX = hasIcon ? x + 34 : x + w / 2
  const textAnchor = hasIcon ? 'start' : 'middle'
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={10}
        fill={SLATE_900}
        stroke={accent}
        strokeWidth={1.5}
        strokeDasharray={dashed ? '5 4' : undefined}
      />
      {icon && (
        <foreignObject x={x + 12} y={centerY - 11} width={22} height={22}>
          {icon}
        </foreignObject>
      )}
      <text x={textX} y={centerY - (sublabel ? 6 : -4)} textAnchor={textAnchor} fill={WHITE} fontSize={13} fontWeight={600}>
        {label}
      </text>
      {sublabel && (
        <text x={textX} y={centerY + 12} textAnchor={textAnchor} fill={SLATE_400} fontSize={10}>
          {sublabel}
        </text>
      )}
    </g>
  )
}

interface FlowEdgeProps {
  id: string
  d: string
  color: string
  label?: string
  labelX?: number
  labelY?: number
  live?: boolean
  dashed?: boolean
}

function FlowEdge({ id, d, color, label, labelX, labelY, live, dashed }: FlowEdgeProps) {
  return (
    <g>
      <path id={id} d={d} fill="none" stroke={color} strokeWidth={2} strokeDasharray={dashed ? '6 5' : undefined} markerEnd="url(#arrowhead)" opacity={dashed ? 0.85 : 1} />
      {live && (
        // A small glowing, rounded "request" travels along the same path
        // via SMIL animateMotion — more reliably supported inside inline
        // SVG than CSS offset-path, and needs no per-edge JS.
        <circle r={5} fill={color} className="flow-pulse" style={{ filter: `drop-shadow(0 0 4px ${color})` }}>
          <animateMotion dur="2.6s" repeatCount="indefinite" rotate="auto">
            <mpath href={`#${id}`} />
          </animateMotion>
        </circle>
      )}
      {label && (
        <text x={labelX} y={labelY} textAnchor="middle" fill={color} fontSize={10.5}>
          {label}
        </text>
      )}
    </g>
  )
}

export function ArchitectureDiagram() {
  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox="0 0 1200 630" className="min-w-[900px] w-full h-auto" role="img" aria-label="Djaskt architecture diagram with animated request flow">
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" fill={SLATE_300} />
          </marker>
        </defs>

        <rect x={0} y={0} width={1200} height={630} fill="transparent" />

        {/* Docker Compose Network outer boundary */}
        <rect x={230} y={30} width={780} height={570} rx={14} fill={SLATE_900} stroke={SLATE_700} strokeWidth={2} opacity={0.5} />
        <foreignObject x={250} y={40} width={20} height={20}>
          <DockerIcon size={16} color={WHITE} />
        </foreignObject>
        <text x={276} y={54} fill={WHITE} fontSize={13} fontWeight={600}>
          Docker Compose Network
        </text>

        {/* Traders */}
        <NodeBox x={40} y={280} w={130} h={60} label="Traders" sublabel="(Browser)" accent={INDIGO_500} icon={<ChromeIcon size={18} color={INDIGO_500} />} />

        {/* nginx */}
        <NodeBox x={270} y={280} w={140} h={60} label="nginx" sublabel="public entry point" accent={INDIGO_500} icon={<NginxIcon size={18} color={INDIGO_500} />} />

        {/* django-ledger-app inner cluster */}
        <rect x={470} y={90} width={330} height={330} rx={12} fill="#16213f" stroke={SLATE_700} strokeWidth={1.5} />
        <text x={488} y={112} fill={WHITE} fontSize={12} fontWeight={600}>
          django-ledger-app (ASGI + Channels)
        </text>
        <NodeBox x={500} y={130} w={270} h={55} label="accounts" sublabel="JWT auth" accent={EMERALD_500} icon={<DjangoIcon size={18} color={EMERALD_500} />} />
        <NodeBox x={500} y={205} w={270} h={55} label="ledger" sublabel="Portfolio / Trade / Cash + WS" accent={EMERALD_500} icon={<DjangoIcon size={18} color={EMERALD_500} />} />
        <NodeBox x={500} y={280} w={270} h={55} label="brokerage" sublabel="Broker links, Angel One" accent={EMERALD_500} icon={<DjangoIcon size={18} color={EMERALD_500} />} />
        <NodeBox x={500} y={355} w={270} h={45} label="Infisical Vault" sublabel="optional secret source" accent={SLATE_400} dashed />

        {/* Redis — tall enough that its 4 incoming edges (JWT denylist,
            Channels layer, broker session cache, price cache read) land at
            evenly spaced points on its left border instead of bunching. */}
        <NodeBox x={880} y={95} w={110} h={190} label="Redis" accent={ROSE_500} icon={<RedisIcon size={18} color={ROSE_500} />} />

        {/* Postgres (external) */}
        <NodeBox x={880} y={470} w={140} h={60} label="Postgres" sublabel="external, single instance" accent={EMERALD_500} icon={<PostgresIcon size={18} color={EMERALD_500} />} />

        {/* Planned cluster */}
        <rect x={470} y={450} width={330} height={130} rx={12} fill="#16213f" stroke={AMBER_400} strokeWidth={1.5} strokeDasharray="7 5" />
        <text x={488} y={472} fill={AMBER_400} fontSize={12} fontWeight={600}>
          Planned — not yet implemented
        </text>
        <NodeBox x={490} y={485} w={140} h={80} label="FastAPI" sublabel="Market Data Firehose" accent={AMBER_400} dashed icon={<FastApiIcon size={18} color={AMBER_400} />} />
        <NodeBox x={645} y={485} w={140} h={80} label="Flask" sublabel="Analytics Engine" accent={AMBER_400} dashed icon={<FlaskIcon size={18} color={AMBER_400} />} />

        {/* --- Edges --- */}
        {/* Traders -> nginx -> the 3 Django apps. Every endpoint below is
            snapped exactly onto the target node's border (verified against
            the NodeBox coordinates above) so no arrowhead floats in empty
            space. */}
        <FlowEdge id="edge-https" d="M170,310 L270,310" color={INDIGO_500} label="HTTPS / WSS" labelX={220} labelY={300} live />
        <FlowEdge id="edge-auth" d="M410,295 C450,260 460,175 500,157" color={INDIGO_500} label="/api/auth" labelX={438} labelY={210} live />
        <FlowEdge id="edge-ledger" d="M410,310 C450,300 465,270 500,251" color={INDIGO_500} label="/api/ledger, /ws/*" labelX={455} labelY={278} live />
        <FlowEdge id="edge-brokerage" d="M410,325 C450,345 465,330 500,315" color={INDIGO_500} label="/api/brokerage" labelX={452} labelY={352} live />

        {/* The 3 Django apps -> Redis, landing at 4 evenly spaced points on
            Redis's left border (x=880, y from 95 to 285) so none overlap. */}
        <FlowEdge id="edge-denylist" d="M770,150 C815,140 850,125 880,120" color={ROSE_500} label="JWT denylist" labelX={815} labelY={122} live />
        <FlowEdge id="edge-channels" d="M770,220 C815,195 850,170 880,165" color={PURPLE_400} label="Channels layer" labelX={820} labelY={183} live />
        <FlowEdge id="edge-session" d="M770,300 C820,270 850,220 880,210" color={YELLOW_400} label="broker session cache" labelX={815} labelY={245} live />
        <FlowEdge id="edge-priceread" d="M770,240 C815,245 850,252 880,255" color={AMBER_400} label="price cache READ (no writer)" labelX={805} labelY={295} dashed />

        {/* ledger -> Postgres, landing on Postgres's top-left border. */}
        <FlowEdge id="edge-lock" d="M770,250 C820,340 870,440 900,470" color={EMERALD_500} label="SELECT FOR UPDATE" labelX={775} labelY={430} live />

        {/* Planned service wiring — nginx/ledger fan out to FastAPI/Flask,
            and their intended data paths back to Redis/Postgres. Labels
            moved off the "Planned" cluster title (y=472) to avoid overlap. */}
        <FlowEdge id="edge-market" d="M405,340 C400,400 420,455 490,505" color={AMBER_400} label="/api/v1/market" labelX={420} labelY={430} dashed />
        <FlowEdge id="edge-analytics" d="M415,340 C440,420 520,530 645,535" color={AMBER_400} label="/api/v1/analytics" labelX={500} labelY={445} dashed />
        <FlowEdge id="edge-setprice" d="M630,500 C740,460 830,340 880,280" color={AMBER_400} label="would SET price (TTL 10s)" labelX={735} labelY={475} dashed />
        <FlowEdge id="edge-readonly" d="M785,510 C840,505 880,500 900,494" color={AMBER_400} label="read-only queries" labelX={850} labelY={525} dashed />

        <text x={620} y={615} textAnchor="middle" fill={SLATE_400} fontSize={11}>
          Glowing dot = live request flow · Dashed amber = planned, not yet built
        </text>
      </svg>
    </div>
  )
}
