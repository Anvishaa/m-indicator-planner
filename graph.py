"""graph.py -- load the DB into an in-memory graph.

Nodes:  (stop_id, '')      standing at the stop, free to walk / board
        (stop_id, seg_id)  on board route segment seg_id
        (stop_id, 'W')     arrived by walk or interchange: can board, can't walk again (no walk chaining)
Edges:  (to_node, cost, label)  with label = ('ride'|'board'|'alight'|'walk'|'interchange', payload)
"""
import sqlite3

import config as cfg


def walk_cost(d):
    return d * cfg.WALK_PER_M + (cfg.LONG_WALK_PENALTY if d > cfg.LONG_WALK_M else 0.0)


class Net:
    def __init__(self, c):
        self.c = c
        self.mode_of = dict(c.execute("SELECT seg_id, mode FROM routes"))
        self.short = dict(c.execute("SELECT seg_id, short_name FROM routes"))
        self.name = dict(c.execute("SELECT stop_id, name FROM stops"))
        self.stop_mode = dict(c.execute("SELECT stop_id, mode FROM stops"))
        self.g = {}
        self._build()

    def add(self, a, b, w, lab):
        self.g.setdefault(a, []).append((b, w, lab))

    def _build(self):
        c = self.c
        seg = {}
        for sid, seq, st in c.execute("SELECT seg_id, seq, stop_id FROM route_stops ORDER BY seg_id, seq"):
            seg.setdefault(sid, []).append(st)

        # ride / board / alight edges
        for sid, l in seg.items():
            w = cfg.RIDE[self.mode_of[sid]]
            for i in range(len(l) - 1):
                self.add((l[i], sid), (l[i + 1], sid), w, ('ride', sid))
            for s in l:
                self.add((s, ''), (s, sid), cfg.BOARD, ('board', sid))
                self.add((s, 'W'), (s, sid), cfg.BOARD, ('board', sid))   # board after walking
                self.add((s, sid), (s, ''), 0, ('alight', sid))

        # distance-based walk edges (land on 'W' so walks can't chain)
        for a, b, d in c.execute("SELECT from_stop, to_stop, walk_m FROM transfers"):
            self.add((a, ''), (b, 'W'), walk_cost(d), ('walk', d))

        # hand-curated in-station interchanges
        try:
            for a, b, cost in c.execute("SELECT from_stop, to_stop, cost FROM interchanges"):
                self.add((a, ''), (b, 'W'), cost, ('interchange', cost))
        except sqlite3.OperationalError:
            print('no interchanges table yet (run load_data.py)')

    # ---------- lookups ----------
    def find(self, kw, mode=None):
        """stop_ids whose name contains kw (optionally only one mode)."""
        return [s for s, n in self.name.items()
                if kw.lower() in n.lower() and (mode is None or self.stop_mode[s] == mode)]

    def stops_like(self, kw, mode):
        return [(s, self.name[s]) for s in self.find(kw, mode)]

    def stats(self):
        nodes = set(self.g)
        for edges in self.g.values():
            nodes.update(v for v, _, _ in edges)
        return len(nodes), sum(len(e) for e in self.g.values())


def build(db_path=cfg.DB_PATH):
    return Net(sqlite3.connect(db_path))
