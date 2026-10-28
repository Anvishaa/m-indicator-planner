import xml.etree.ElementTree as ET

def load_kml_stops(path, mode, prefix):
    ns = '{http://www.opengis.net/kml/2.2}'
    root = ET.parse(path).getroot()
    rows = []
    for i, pm in enumerate(root.iter(ns + 'Placemark')):
        name = pm.findtext(ns + 'name')
        coords = pm.findtext(f'.//{ns}coordinates')
        if not coords:
            continue
        lon, lat = map(float, coords.strip().split(',')[:2])   # KML = lon,lat
        extra = {sd.get('name'): sd.text for sd in pm.iter(ns + 'SimpleData')}
        rows.append((f'{prefix}_{i}', name.strip(), mode, lat, lon, extra))
    return rows

train = load_kml_stops('suburban_stations.kml', 'train', 'TRN')
print(len(train))
print(train[0])

# keep only the Andheri-Ghatkopar box
train = [r for r in train if 19.05 <= r[3] <= 19.14 and 72.82 <= r[4] <= 72.93]
print(len(train))
for r in train: print(r[1], r[5])

from collections import Counter
fields = Counter()
for r in train:
    for k, v in r[5].items():
        fields[k] += 1
print(fields)            # the 5 field names
print(train[0][5])  

import pandas as pd
df = pd.read_csv('metro_stations.csv', sep=None, engine='python')   # handles tab or comma
df[['lat', 'lon']] = df['cordinates'].str.split(',', expand=True).astype(float)
df['lat'] = df['lat']; 
df['lon'] = df['lon']
df['seq'] = range(1, len(df) + 1)
# print(df[['lat','lon']].describe())                 # lat ~19.0-19.2, lon ~72.82-72.92
# print(df.sort_values('seq')[['station_name','lat','lon']])

import sqlite3
c = sqlite3.connect('bus_subgraph.db')

# 1. stops
df['stop_id'] = ['MET_' + str(i) for i in df['seq']]
c.executemany("INSERT OR IGNORE INTO stops VALUES (?,?,?,?,?)",
    [(r.stop_id, r.station_name, 'metro', r.lat, r.lon) for r in df.itertuples()])

# 2. route (one per direction)
c.execute("INSERT OR IGNORE INTO routes VALUES ('MET1_A','MET1','Line 1','Metro Line 1','metro')")
c.execute("INSERT OR IGNORE INTO routes VALUES ('MET1_B','MET1','Line 1','Metro Line 1','metro')")

# 3. route_stops: forward and reversed
n = len(df)
c.executemany("INSERT OR IGNORE INTO route_stops VALUES (?,?,?)",
    [('MET1_A', r.seq, r.stop_id) for r in df.itertuples()])
c.executemany("INSERT OR IGNORE INTO route_stops VALUES (?,?,?)",
    [('MET1_B', n + 1 - r.seq, r.stop_id) for r in df.itertuples()])
c.commit()

# for row in c.execute("SELECT mode, COUNT(*) FROM stops GROUP BY mode"):
#     print(row)

# c.executemany("INSERT OR IGNORE INTO stops VALUES (?,?,?,?,?)",
#               [r[:5] for r in train])      # first 5 fields: id, name, mode, lat, lon
# c.commit()

# for row in c.execute("SELECT mode, COUNT(*) FROM stops GROUP BY mode"):
#     print(row)

for r in sorted(train, key=lambda r: r[3]):      # sorted by latitude
    print(r[1], round(r[3], 4), round(r[4], 4))








import sqlite3, numpy as np
from scipy.spatial import cKDTree

K, CAP_M = 5, 500            # raise CAP_M to ~800 for train<->metro if needed
M_LAT, M_LON = 111_000, 105_000

c = sqlite3.connect('bus_subgraph.db')
stops = c.execute("SELECT stop_id, mode, lat, lon FROM stops").fetchall()
xy = np.array([(lat*M_LAT, lon*M_LON) for _, _, lat, lon in stops])

# one tree per mode, so "5 nearest of that mode" is a direct query
modes = {m for _, m, _, _ in stops}
trees = {}
for m in modes:
    idx = [i for i, s in enumerate(stops) if s[1] == m]
    trees[m] = (idx, cKDTree(xy[idx]))

rows = []
for i, (sid, mode, _, _) in enumerate(stops):
    for m, (idx, tree) in trees.items():
        if m == mode:
            continue                                   # cross-mode only
        d, nn = tree.query(xy[i], k=min(K, len(idx)),
                           distance_upper_bound=CAP_M)
        for dist, j in zip(np.atleast_1d(d), np.atleast_1d(nn)):
            if np.isinf(dist):                         # beyond the cap
                continue
            tid = stops[idx[j]][0]
            rows.append((sid, tid, int(dist)))
            rows.append((tid, sid, int(dist)))          # both directions

c.executemany("INSERT OR REPLACE INTO transfers VALUES (?,?,?)", rows)
c.commit()


# ----------------------------
import math
def dist_m(a, b):
    return math.hypot((a[2]-b[2])*111000, (a[3]-b[3])*105000)   # a,b = (id, mode, lat, lon)

rows = []
for a in stops:
    for m in modes:
        if m == a[1]: continue
        near = sorted((dist_m(a, b), b[0]) for b in stops if b[1] == m)
        for d, tid in near[:5]:
            if d <= CAP_M:
                rows.append((a[0], tid, int(d))); rows.append((tid, a[0], int(d)))


import sqlite3, heapq, itertools

c = sqlite3.connect('bus_subgraph.db')   # skip this line if c already exists in your session

# ---------- 1. insert train routes (rerunnable) ----------
LINES = {
    'WR': ['Jogeshwari', 'Andheri', 'Vile Parle', 'Santacruz', 'Khar Road', 'Bandra'],
    'CR': ['Kurla', 'Vidyavihar', 'Ghatkopar', 'Vikhroli', 'Kanjur Marg'],
    'HR': ['Chunna', 'Kurla', 'Tilak Nagar', 'Chembur', 'Govandi'],
}

c.execute("DELETE FROM route_stops WHERE seg_id IN (SELECT seg_id FROM routes WHERE mode='train')")
c.execute("DELETE FROM routes WHERE mode='train'")

train = c.execute("SELECT stop_id, name FROM stops WHERE mode='train'").fetchall()

def sid_of(kw):
    m = [s for s, n in train if kw.lower() in n.lower()]
    assert len(m) == 1, (kw, m)      # 0 or 2+ matches -> fix the keyword
    return m[0]

for line, names in LINES.items():
    ids = [sid_of(n) for n in names]
    for seg_id, order in ((line + '_A', ids), (line + '_B', ids[::-1])):
        c.execute("INSERT INTO routes(seg_id,route_id,short_name,long_name,mode) VALUES (?,?,?,?,?)",
                  (seg_id, line, line, line, 'train'))
        for n, s in enumerate(order, 1):
            c.execute("INSERT INTO route_stops(seg_id,seq,stop_id) VALUES (?,?,?)", (seg_id, n, s))
c.commit()

print(c.execute("SELECT mode, COUNT(*) FROM stops GROUP BY mode").fetchall())
print(c.execute("SELECT mode, COUNT(*) FROM routes GROUP BY mode").fetchall())   # bus 538, metro 2, train 6

# ---------- 2. build graph ----------
RIDE = {'bus': 2.0, 'train': 2.0, 'metro': 2.0}   # per hop, tune later
BOARD = 8.0                                         # boarding penalty
WALK_PER_M = 1 / 80                                 # min per metre

mode_of = dict(c.execute("SELECT seg_id, mode FROM routes"))
short = dict(c.execute("SELECT seg_id, short_name FROM routes"))
name = dict(c.execute("SELECT stop_id, name FROM stops"))
stop_mode = dict(c.execute("SELECT stop_id, mode FROM stops"))

seg = {}
for sid, seq, st in c.execute("SELECT seg_id, seq, stop_id FROM route_stops ORDER BY seg_id, seq"):
    seg.setdefault(sid, []).append(st)

g = {}
def add(a, b, w, lab): g.setdefault(a, []).append((b, w, lab))

for sid, l in seg.items():
    w = RIDE[mode_of[sid]]
    for i in range(len(l) - 1):
        add((l[i], sid), (l[i+1], sid), w, ('ride', sid))
    for s in l:
        add((s, ''), (s, sid), BOARD, ('board', sid))
        add((s, 'W'), (s, sid), BOARD, ('board', sid))   # NEW: board after walking
        add((s, sid), (s, ''), 0, ('alight', sid))
for a, b, d in c.execute("SELECT from_stop, to_stop, walk_m FROM transfers"):
    add((a, ''), (b, 'W'), d * WALK_PER_M, ('walk', d))

# ---------- 3. search ----------
cnt = itertools.count()
def route(src, dst, modes=('bus', 'train', 'metro')):
    D = {(src, ''): 0}; prev = {}; pq = [(0, next(cnt), (src, ''))]
    while pq:
        d, _, u = heapq.heappop(pq)
        if d > D.get(u, 1e9): continue
        if u[0] == dst:
            edges = []; k = u
            while k in prev:
                p, lab = prev[k]; edges.append((p, k, lab)); k = p
            edges.reverse()

            legs = []
            for p, k, lab in edges:
                if lab[0] == 'walk':
                    legs.append(['walk', f"{lab[1]:.0f} m", name[p[0]], name[k[0]]])
                elif lab[0] == 'board':
                    legs.append([mode_of[lab[1]], short[lab[1]], name[p[0]], None])
                elif lab[0] == 'alight':
                    legs[-1][3] = name[p[0]]
            # a ride that ends at the destination never takes the alight edge
            if legs and legs[-1][3] is None:
                legs[-1][3] = name[edges[-1][1][0]]
            return round(d), legs
        
        for v, w, lab in g.get(u, []):
            if lab[0] == 'board' and mode_of[lab[1]] not in modes:
                continue
            nd = d + w
            if nd < D.get(v, 1e9):
                D[v] = nd; prev[v] = (u, lab); heapq.heappush(pq, (nd, next(cnt), v))
    return None

def find(kw, mode=None):
    return [s for s, n in name.items() if kw.lower() in n.lower()
            and (mode is None or stop_mode[s] == mode)]

# ---------- 4. test ----------
# print(find('Andheri'), find('Kurla'))   # sanity: see which names exist
print(route(find('Andheri', 'metro')[0], find('Kurla', 'train')[0]))


# print(c.execute("SELECT mode, COUNT(*) FROM stops GROUP BY mode").fetchall())
# print(c.execute("SELECT mode, COUNT(*) FROM routes GROUP BY mode").fetchall())
# print(c.execute("SELECT COUNT(*) FROM transfers t JOIN stops s ON s.stop_id=t.from_stop WHERE s.mode='train'").fetchall())

# print(c.execute("SELECT stop_id, name, lat FROM stops WHERE mode='train' ORDER BY lat").fetchall())

# print(c.execute("SELECT mode, COUNT(*) FROM routes GROUP BY mode").fetchall())


# checking if all metro and trains have a bus transfer
for s, n, m in c.execute("SELECT stop_id, name, mode FROM stops WHERE mode IN ('train','metro')"):
    k = c.execute("""SELECT COUNT(*) FROM transfers t JOIN stops x ON x.stop_id=t.to_stop
                     WHERE t.from_stop=? AND x.mode='bus'""", (s,)).fetchone()[0]
    print(m, n, k)


s = find('Ghatkopar', 'metro')[0]
print(c.execute("""
    SELECT COUNT(DISTINCT r.route_id)
    FROM transfers t
    JOIN stops x ON x.stop_id = t.to_stop
    JOIN route_stops rs ON rs.stop_id = x.stop_id
    JOIN routes r ON r.seg_id = rs.seg_id
    WHERE t.from_stop = ? AND x.mode = 'bus'""", (s,)).fetchone())

pairs = [
    ('Versova', 'metro', 'Chembur', 'train'),
    ('Bandra', 'train', 'Ghatkopar', 'metro'),
    ('Andheri', 'train', 'Ghatkopar', 'train'),
    ('Jogeshwari', 'train', 'Govandi', 'train'),
    ('Vile Parle', 'train', 'Ghatkopar', 'metro'),
]

print('=== COMPARISON ===')
for a, am, b, bm in pairs:
    sa, sb = find(a, am), find(b, bm)
    if not sa or not sb: continue
    multi = route(sa[0], sb[0])
    bus = route(sa[0], sb[0], modes=('bus',))
    print(a, '->', b)
    print('  multi:', multi)
    print('  bus  :', bus)

def show(res):
    if res is None:
        print('  no route'); return
    cost, legs = res
    print(f'  cost {cost}')
    for mode, label, a, b in legs:
        if mode == 'walk':
            print(f'    walk {label}: {a} -> {b}')
        else:
            print(f'    {mode} {label}: {a} -> {b}')



c.execute("CREATE TABLE IF NOT EXISTS interchanges(from_stop, to_stop, cost)")
c.execute("DELETE FROM interchanges")
INTER = [('Andheri', 'train', 'Andheri', 'metro', 3.0)]   # add Ghatkopar etc. if you want
for a, am, b, bm, cost in INTER:
    sa, sb = find(a, am)[0], find(b, bm)[0]
    c.executemany("INSERT INTO interchanges VALUES (?,?,?)", [(sa, sb, cost), (sb, sa, cost)])
c.commit()

for a, b, cost in c.execute("SELECT from_stop, to_stop, cost FROM interchanges"):
    add((a, ''), (b, 'W'), cost, ('interchange', cost))

sa, sb = find('Vile Parle', 'train'), find('Ghatkopar', 'metro')
print('Vile Parle -> Ghatkopar')
print(' multi:'); show(route(sa[0], sb[0]))
print(' bus  :'); show(route(sa[0], sb[0], modes=('bus',)))

print('interchange rows:', c.execute("SELECT * FROM interchanges").fetchall())
print('Andheri metro -> Andheri train:'); show(route(find('Andheri','metro')[0], find('Andheri','train')[0]))
    