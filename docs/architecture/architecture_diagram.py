"""Renders docs/architecture/djaskt_trading_architecture.png.

Depicts the system as actually built on branch `django_react`, not the
aspirational design in gemini/architectture_diagrams.py (which shows a
FastAPI market-data service, a Flask analytics service, and a Postgres
read-replica as if they were live — none of that exists in this repo
today; see the "Planned" cluster below for how those are represented
instead). Regenerate with:

    pip install -r requirements.txt
    python architecture_diagram.py
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.onprem.client import Users
from diagrams.onprem.network import Nginx
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.inmemory import Redis
from diagrams.onprem.security import Vault
from diagrams.programming.framework import Django, FastAPI, Flask, React

# Frontend's own dark palette (frontend/react/src/components/ui/*.tsx,
# Tailwind v4 slate/indigo/emerald/amber/rose/purple/yellow) — reused here
# instead of diagrams' default light theme so the doc visually matches the app.
SLATE_950 = "#020617"  # page background
SLATE_900 = "#0f172a"  # card background
SLATE_800 = "#1e293b"  # borders
SLATE_700 = "#334155"  # borders (lighter)
SLATE_400 = "#94a3b8"  # muted text
WHITE = "#ffffff"
INDIGO_500 = "#6366f1"  # primary/brand, main request path
EMERALD_500 = "#10b981"  # real/success data flow
AMBER_400 = "#fbbf24"  # planned/disconnected
ROSE_500 = "#f43f5e"  # denylist / security-relevant edges
PURPLE_400 = "#c084fc"  # portfolio accent
YELLOW_400 = "#facc15"  # live-market accent

SLATE_300 = "#cbd5e1"  # brighter muted text — used for edge labels, since
# SLATE_400 reads as near-invisible against the slate-900/950 backgrounds
# Graphviz renders here (screen antialiasing is softer than a browser's).

graph_attr = {
    "fontsize": "24",
    "fontcolor": WHITE,
    "bgcolor": SLATE_950,
    "pad": "1.0",
    "splines": "ortho",
    "nodesep": "0.9",
    "ranksep": "1.4",
}
node_attr = {
    "fontcolor": WHITE,
    "fontsize": "13",
}
edge_attr = {
    "fontcolor": SLATE_300,
    "fontsize": "12",
    "color": SLATE_300,
    "penwidth": "1.4",
}
cluster_attr = {
    "bgcolor": SLATE_900,
    "pencolor": SLATE_700,
    "penwidth": "2.0",
    "fontcolor": WHITE,
    "fontsize": "15",
    "style": "filled,rounded",  # "filled" is required for bgcolor to
    # actually paint the cluster box — "rounded" alone only affects the
    # border shape, not whether a fill is drawn at all.
    "margin": "24",
}
inner_cluster_attr = {
    "bgcolor": "#16213f",  # one step lighter than SLATE_900, so the nested
    # django-ledger-app cluster reads as a distinct panel instead of
    # blending into the outer Docker Compose Network cluster.
    "pencolor": SLATE_700,
    "penwidth": "1.5",
    "fontcolor": WHITE,
    "fontsize": "14",
    "style": "filled,rounded",
    "margin": "20",
}
planned_cluster_attr = {
    "bgcolor": "#16213f",
    "pencolor": AMBER_400,
    "penwidth": "1.5",
    "style": "filled,rounded,dashed",
    "fontcolor": AMBER_400,
    "fontsize": "14",
    "margin": "20",
}

with Diagram(
    "Djaskt Trading Architecture",
    filename="djaskt_trading_architecture",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
):
    traders = Users("Traders\n(Browser)")

    with Cluster("Docker Compose Network", graph_attr=cluster_attr):
        proxy = Nginx("nginx\n(single public entry point)")
        frontend = React("React SPA\n(static build,\nno server container\nat runtime)")
        vault = Vault("Infisical Vault\n(optional secret source)")

        with Cluster(
            "django-ledger-app  (ASGI / Uvicorn + Channels)", graph_attr=inner_cluster_attr
        ):
            accounts = Django("accounts\nJWT auth")
            ledger = Django("ledger\nPortfolio / Trade / Cash\n+ realtime WS consumer")
            brokerage = Django("brokerage\nBroker links,\nAngel One strategy")

        redis = Redis("Redis")

        with Cluster("Planned — not yet implemented", graph_attr=planned_cluster_attr):
            fastapi = FastAPI("Market Data Firehose\n(would write price cache)")
            flask = Flask("Analytics Engine\n(batch reporting)")

    postgres = PostgreSQL(
        "Postgres\n(external, host.docker.internal\nsingle instance —\nno real replica configured)"
    )

    # --- Client traffic: proxy fans out to static assets + the 3 Django apps ---
    traders >> Edge(color=INDIGO_500, fontcolor=INDIGO_500, label="HTTPS / WSS") >> proxy
    proxy >> Edge(color=INDIGO_500, fontcolor=INDIGO_500, label="static assets") >> frontend
    proxy >> Edge(color=INDIGO_500, fontcolor=INDIGO_500, label="/api/auth") >> accounts
    (
        proxy
        >> Edge(color=INDIGO_500, fontcolor=INDIGO_500, penwidth="2.2", label="/api/ledger,\n/ws/*")
        >> ledger
    )
    proxy >> Edge(color=INDIGO_500, fontcolor=INDIGO_500, label="/api/brokerage") >> brokerage

    # --- Django -> Postgres (the one real, always-on dependency) ---
    (
        ledger
        >> Edge(color=EMERALD_500, fontcolor=EMERALD_500, label="SELECT FOR UPDATE\n(ACID trades)")
        >> postgres
    )
    accounts >> Edge(color=EMERALD_500, style="dashed") >> postgres
    brokerage >> Edge(color=EMERALD_500, style="dashed") >> postgres

    # --- Django -> Redis, labeled by actual role (not generic "cache") ---
    (
        ledger
        >> Edge(color=PURPLE_400, fontcolor=PURPLE_400, label="Channels layer\n(portfolio WS broadcast)")
        >> redis
    )
    (
        accounts
        >> Edge(color=ROSE_500, fontcolor=ROSE_500, label="JWT denylist\n(deny:{jti})")
        >> redis
    )
    (
        brokerage
        >> Edge(
            color=YELLOW_400,
            fontcolor=YELLOW_400,
            label="broker session cache\n(auth_user_*, IST TTL)",
        )
        >> redis
    )
    (
        ledger
        >> Edge(
            color=AMBER_400,
            fontcolor=AMBER_400,
            style="dashed",
            label="price cache READ\n(no writer yet)",
        )
        >> redis
    )

    # --- Optional secret source ---
    (
        vault
        >> Edge(
            color=SLATE_300,
            fontcolor=SLATE_300,
            style="dotted",
            label="SECRET_KEY, DB/REDIS\npasswords (.env fallback)",
        )
        >> accounts
    )

    # --- Planned services' intended data path ---
    (
        fastapi
        >> Edge(color=AMBER_400, fontcolor=AMBER_400, style="dashed", label="would SET price\n(TTL 10s)")
        >> redis
    )
    (
        proxy
        >> Edge(color=AMBER_400, fontcolor=AMBER_400, style="dashed", label="/api/v1/market\n(planned)")
        >> fastapi
    )
    (
        proxy
        >> Edge(
            color=AMBER_400, fontcolor=AMBER_400, style="dashed", label="/api/v1/analytics\n(planned)"
        )
        >> flask
    )
    (
        flask
        >> Edge(color=AMBER_400, fontcolor=AMBER_400, style="dashed", label="read-only queries\n(planned)")
        >> postgres
    )
