"""build_transfers.py -- link each stop to its K nearest stops *per other mode*, within a distance cap.

compute_transfers() is a pure function over (stop_id, mode, lat, lon) tuples, so bench.py can time it
on the full-city stop list too. Uses a KD-tree when scipy is installed, brute force otherwise.

Usage:  python build_transfers.py
        (scipy missing?  python -m pip install scipy numpy)
"""
import math
import sqlite3

import config as cfg


def cap_for(m1, m2):
    return cfg.CAP_BY_PAIR.get(frozenset((m1, m2)), cfg.CAP_M)


# ---------- A. KD-tree version ----------
def compute_transfers_kdtree(stops, K=cfg.K):
    import numpy as np
    from scipy.spatial import cKDTree

    xy = np.array([(lat * cfg.M_LAT, lon * cfg.M_LON) for _, _, lat, lon in stops])

    # one tree per mode, so "K nearest of that mode" is a direct query
    modes = {m for _, m, _, _ in stops}
    trees = {}
    for m in modes:
        idx = [i for i, s in enumerate(stops) if s[1] == m]
        trees[m] = (idx, cKDTree(xy[idx]))

    rows = set()
    for i, (sid, mode, _, _) in enumerate(stops):
        for m, (idx, tree) in trees.items():
            if m == mode:
                continue                                   # cross-mode only
            d, nn = tree.query(xy[i], k=min(K, len(idx)),
                               distance_upper_bound=cap_for(mode, m))
            for dist, j in zip(np.atleast_1d(d), np.atleast_1d(nn)):
                if np.isinf(dist):                         # beyond the cap
                    continue
                tid = stops[idx[j]][0]
                rows.add((sid, tid, int(dist)))
                rows.add((tid, sid, int(dist)))            # both directions
    return list(rows)


# ---------- B. brute-force version (fine for ~1,750 stops) ----------
def dist_m(a, b):
    return math.hypot((a[2] - b[2]) * cfg.M_LAT, (a[3] - b[3]) * cfg.M_LON)   # a,b = (id, mode, lat, lon)


def compute_transfers_bruteforce(stops, K=cfg.K):
    modes = {s[1] for s in stops}
    rows = set()
    for a in stops:
        for m in modes:
            if m == a[1]:
                continue
            near = sorted((dist_m(a, b), b[0]) for b in stops if b[1] == m)
            for d, tid in near[:K]:
                if d <= cap_for(a[1], m):
                    rows.add((a[0], tid, int(d)))
                    rows.add((tid, a[0], int(d)))
    return list(rows)


def compute_transfers(stops, K=cfg.K):
    try:
        return compute_transfers_kdtree(stops, K)
    except ImportError:
        print('scipy/numpy not found, using brute force')
        return compute_transfers_bruteforce(stops, K)


# ---------- C. save ----------
def save_transfers(c, rows):
    c.execute("""CREATE TABLE IF NOT EXISTS transfers(
                     from_stop, to_stop, walk_m, PRIMARY KEY(from_stop, to_stop))""")
    # clear old cross-mode links only; keep the original bus<->bus links (<=150 m)
    c.execute("""DELETE FROM transfers WHERE EXISTS (
                     SELECT 1 FROM stops a, stops b
                     WHERE a.stop_id = transfers.from_stop
                       AND b.stop_id = transfers.to_stop
                       AND a.mode <> b.mode)""")
    c.executemany("INSERT OR REPLACE INTO transfers VALUES (?,?,?)", rows)
    c.commit()


def main():
    c = sqlite3.connect(cfg.DB_PATH)
    stops = c.execute("SELECT stop_id, mode, lat, lon FROM stops").fetchall()
    rows = compute_transfers(stops)
    save_transfers(c, rows)
    print(len(stops), 'stops ->', len(rows), 'cross-mode transfer rows')
    print(c.execute("SELECT COUNT(*) FROM transfers").fetchone()[0], 'rows in transfers in total')


if __name__ == '__main__':
    main()
