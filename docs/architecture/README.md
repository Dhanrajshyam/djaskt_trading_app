# Architecture diagram

`djaskt_trading_architecture.png` is generated from `architecture_diagram.py` using the
[`diagrams`](https://diagrams.mingrammer.com/) package. It reflects what's actually
built and running on this branch — not the aspirational design in
`gemini/architectture_diagrams.py` (FastAPI/Flask/replica DB shown as live services).
Here, FastAPI and Flask are drawn in a separate dashed "Planned — not yet implemented"
cluster, since no backend code for either exists in this repo yet.

## Regenerating

Requires [Graphviz](https://graphviz.org/download/) installed on the host (the `dot`
binary must be on `PATH`) in addition to the Python package below.

```
pip install -r requirements.txt
python architecture_diagram.py
```

This overwrites `djaskt_trading_architecture.png` in place.

## Keeping it accurate

Update `architecture_diagram.py` whenever the real topology changes — e.g. a new
Django app, a new Redis usage, or the FastAPI/Flask services actually landing (at
which point they should move out of the "Planned" cluster into the main one). The
color palette (`SLATE_*`, `INDIGO_500`, etc., near the top of the script) is copied
from `frontend/react/src/components/ui/*.tsx` — update both together if the frontend's
Tailwind palette ever changes.
