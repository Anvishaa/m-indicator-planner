"""api.py -- tiny web backend + page for the journey planner.

Run:   python -m pip install fastapi uvicorn
       uvicorn api:app --reload
Open:  http://127.0.0.1:8000

GET /api/stops?q=and[&mode=train]   autocomplete, one row per (name, mode); 'ids' = every stop with that name
GET /api/plan?src=ID,ID&dst=ID,ID   up to k different journeys, ranked cheapest first
GET /                               the page (index.html)
"""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from graph import build
from search import alternatives

app = FastAPI(title='Multi-modal journey planner')
net = build()                                   # graph is built once at startup
HERE = Path(__file__).parent

# group duplicate directional stops: one entry per (name, mode), holding all its stop_ids
_groups = {}
for _sid, _n in net.name.items():
    _m = net.stop_mode[_sid]
    g = _groups.setdefault((_n.strip().lower(), _m), {'name': _n.strip(), 'mode': _m, 'ids': []})
    g['ids'].append(_sid)
GROUPS = list(_groups.values())


@app.get('/api/stops')
def stops(q: str = Query('', max_length=60), mode: Optional[str] = None, limit: int = 8):
    q = q.strip().lower()
    if not q:
        return []
    hits = []
    for g in GROUPS:
        if mode and g['mode'] != mode:
            continue
        n = g['name'].lower()
        pos = n.find(q)
        if pos < 0:
            continue
        # stations first, then names that start with q, then shorter names
        hits.append((g['mode'] == 'bus', pos != 0, len(n), g))
    hits.sort(key=lambda h: h[:3])
    return [{'name': g['name'], 'mode': g['mode'], 'label': f"{g['name']} ({g['mode']})",
             'ids': ','.join(g['ids'])} for *_, g in hits[:max(1, min(limit, 20))]]


@app.get('/api/plan')
def plan(src: str, dst: str, k: int = 3):
    srcs = [s for s in src.split(',') if s in net.name]
    dsts = [s for s in dst.split(',') if s in net.name]
    if not srcs or not dsts:
        raise HTTPException(400, 'Unknown stop.')
    if set(srcs) & set(dsts):
        raise HTTPException(400, 'Start and destination are the same place.')

    alts = alternatives(net, srcs, dsts, k=max(1, min(k, 5)))
    options, seen = [], set()
    for cost, legs in alts:
        rides = [{'mode': m, 'label': lab} for m, lab, _, _ in legs if m not in ('walk', 'interchange')]
        key = tuple((r['mode'], r['label']) for r in rides)
        if key in seen:                      # same lines in the same order = same option to a rider
            continue
        seen.add(key)
        walk_m = sum(int(float(lab.split()[0])) for m, lab, _, _ in legs if m == 'walk')
        options.append({
            'cost': cost,
            'changes': max(0, len(rides) - 1),
            'walk_m': walk_m,
            'rides': rides,
            'legs': [{'mode': m, 'label': lab, 'from': a, 'to': b} for m, lab, a, b in legs],
        })

    options.sort(key=lambda o: o['cost'])
    fewest = min((o['changes'] for o in options), default=0)
    for i, o in enumerate(options, 1):
        o['rank'] = i
        o['tags'] = (['Fastest'] if i == 1 else []) + \
                    (['Fewest changes'] if o['changes'] == fewest and len(options) > 1 else [])
    return {'options': options}


@app.get('/')
def index():
    return FileResponse(HERE / 'index.html')
