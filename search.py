"""search.py -- Dijkstra, leg building, pretty printing, alternatives.

search()        core: multi-source / multi-target, optional edge penalties, returns (cost, legs, edges)
route()         one stop -> one stop
route_any()     many stops -> many stops (e.g. a train station -> every bus stop named "Ghatkopar")
alternatives()  several *different* multi-modal journeys (penalty method)
show()          print a result
"""
import heapq
import itertools

import config as cfg

_cnt = itertools.count()


# ---------- naming ----------
def nm(net, x):
    """Readable stop name; non-bus stops get their mode so 'Andheri (train)' != 'Andheri (metro)'."""
    return net.name[x] if net.stop_mode[x] == 'bus' else f"{net.name[x]} ({net.stop_mode[x]})"


# ---------- legs ----------
def build_legs(net, edges):
    """edges = [(prev_node, node, label), ...] in travel order -> [[mode, label, from, to], ...]"""
    legs = []
    for p, k, lab in edges:
        if lab[0] == 'walk':
            legs.append(['walk', f"{lab[1]:.0f} m", nm(net, p[0]), nm(net, k[0])])
        elif lab[0] == 'interchange':
            legs.append(['interchange', 'in-station', nm(net, p[0]), nm(net, k[0])])
        elif lab[0] == 'board':
            legs.append([net.mode_of[lab[1]], net.short[lab[1]], nm(net, p[0]), None])
        elif lab[0] == 'alight':
            legs[-1][3] = nm(net, p[0])
    # a ride that ends at the destination never takes the alight edge
    if legs and legs[-1][3] is None:
        legs[-1][3] = nm(net, edges[-1][1][0])
    return legs


# ---------- core search ----------
def search(net, srcs, dsts, modes=cfg.ALL_MODES, extra=None):
    """Cheapest journey from any of srcs to any of dsts. `extra` maps (node_u, node_v) -> added cost,
    used only to steer the search; the cost returned is the real one."""
    extra = extra or {}
    dsts = set(dsts)
    D, prev, pq = {}, {}, []
    for s in srcs:
        D[(s, '')] = 0
        heapq.heappush(pq, (0, next(_cnt), (s, '')))

    while pq:
        d, _, u = heapq.heappop(pq)
        if d > D.get(u, 1e9):
            continue
        if u[0] in dsts:
            edges, k, real = [], u, 0.0
            while k in prev:
                p, lab, w = prev[k]
                edges.append((p, k, lab)); real += w; k = p
            edges.reverse()
            return round(real), build_legs(net, edges), edges
        for v, w, lab in net.g.get(u, []):
            if lab[0] == 'board' and net.mode_of[lab[1]] not in modes:
                continue
            nd = d + w + extra.get((u, v), 0)
            if nd < D.get(v, 1e9):
                D[v] = nd
                prev[v] = (u, lab, w)
                heapq.heappush(pq, (nd, next(_cnt), v))
    return None


def route(net, src, dst, modes=cfg.ALL_MODES):
    r = search(net, [src], [dst], modes)
    return None if r is None else (r[0], r[1])


def route_any(net, srcs, dsts, modes=cfg.ALL_MODES):
    r = search(net, srcs, dsts, modes)
    return None if r is None else (r[0], r[1])


# ---------- several different journeys ----------
def alternatives(net, srcs, dsts, k=3, bump=15.0, max_ratio=1.5, modes=cfg.ALL_MODES):
    """Find the best journey, penalise the rides/boardings it used, search again, repeat.
    Journeys count as different when their sequence of (mode, line) boardings differs.
    Anything costing more than max_ratio x the best is dropped."""
    extra, seen, out, best = {}, set(), [], None
    for _ in range(k * 4):
        res = search(net, srcs, dsts, modes, extra)
        if res is None:
            break
        cost, legs, edges = res
        if best is None:
            best = cost
        sig = tuple((l[0], l[1]) for l in legs if l[0] not in ('walk', 'interchange'))
        if sig not in seen and cost <= best * max_ratio:
            seen.add(sig)
            out.append((cost, legs))
            if len(out) == k:
                break
        for p, kk, lab in edges:
            if lab[0] in ('board', 'ride'):
                extra[(p, kk)] = extra.get((p, kk), 0) + bump
    return out


# ---------- printing ----------
def show(res, indent='  '):
    if res is None:
        print(f'{indent}no route'); return
    cost, legs = res
    print(f'{indent}cost {cost}')
    for mode, label, a, b in legs:
        if mode == 'walk':
            print(f'{indent}  walk {label}: {a} -> {b}')
        else:
            print(f'{indent}  {mode} {label}: {a} -> {b}')
