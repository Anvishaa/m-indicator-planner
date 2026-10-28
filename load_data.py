"""load_data.py -- put train + metro data into bus_subgraph.db.

Safe to rerun: stops/metro use INSERT OR IGNORE, train routes and interchanges are cleared and rebuilt.
Usage:  python load_data.py            (add --inspect to print the KML field summary)
"""
import sys
import sqlite3
import xml.etree.ElementTree as ET
from collections import Counter

import pandas as pd

import config as cfg


# ---------- 1. KML -> train stops ----------
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


def in_box(lat, lon):
    return cfg.LAT_MIN <= lat <= cfg.LAT_MAX and cfg.LON_MIN <= lon <= cfg.LON_MAX


def inspect_kml(all_rows, boxed_rows):
    print('stations in KML:', len(all_rows))
    print('first:', all_rows[0])
    print('stations in box:', len(boxed_rows))
    for r in boxed_rows:
        print(r[1], r[5])
    fields = Counter()
    for r in boxed_rows:
        for k in r[5]:
            fields[k] += 1
    print(fields)                       # the 5 field names
    print(boxed_rows[0][5])
    for r in sorted(boxed_rows, key=lambda r: r[3]):      # sorted by latitude
        print(r[1], round(r[3], 4), round(r[4], 4))


def insert_train_stops(c, rows):
    c.executemany("INSERT OR IGNORE INTO stops VALUES (?,?,?,?,?)",
                  [r[:5] for r in rows])      # id, name, mode, lat, lon
    c.commit()


# ---------- 2. metro CSV -> metro stops + routes ----------
def load_metro_df(path):
    df = pd.read_csv(path, sep=None, engine='python')   # handles tab or comma
    df[['lat', 'lon']] = df['cordinates'].str.split(',', expand=True).astype(float)
    df['seq'] = range(1, len(df) + 1)
    df['stop_id'] = ['MET_' + str(i) for i in df['seq']]
    return df


def insert_metro(c, df):
    # stops
    c.executemany("INSERT OR IGNORE INTO stops VALUES (?,?,?,?,?)",
                  [(r.stop_id, r.station_name, 'metro', r.lat, r.lon) for r in df.itertuples()])
    # one route per direction
    c.execute("INSERT OR IGNORE INTO routes VALUES ('MET1_A','MET1','Line 1','Metro Line 1','metro')")
    c.execute("INSERT OR IGNORE INTO routes VALUES ('MET1_B','MET1','Line 1','Metro Line 1','metro')")
    # route_stops: forward and reversed
    n = len(df)
    c.executemany("INSERT OR IGNORE INTO route_stops VALUES (?,?,?)",
                  [('MET1_A', r.seq, r.stop_id) for r in df.itertuples()])
    c.executemany("INSERT OR IGNORE INTO route_stops VALUES (?,?,?)",
                  [('MET1_B', n + 1 - r.seq, r.stop_id) for r in df.itertuples()])
    c.commit()


# ---------- 3. train routes (hard-coded station order, both directions) ----------
def insert_train_routes(c):
    c.execute("DELETE FROM route_stops WHERE seg_id IN (SELECT seg_id FROM routes WHERE mode='train')")
    c.execute("DELETE FROM routes WHERE mode='train'")

    train = c.execute("SELECT stop_id, name FROM stops WHERE mode='train'").fetchall()

    def sid_of(kw):
        m = [s for s, n in train if kw.lower() in n.lower()]
        assert len(m) == 1, (kw, m)      # 0 or 2+ matches -> fix the keyword in config.LINES
        return m[0]

    for line, names in cfg.LINES.items():
        ids = [sid_of(n) for n in names]
        for seg_id, order in ((line + '_A', ids), (line + '_B', ids[::-1])):
            c.execute("INSERT INTO routes(seg_id,route_id,short_name,long_name,mode) VALUES (?,?,?,?,?)",
                      (seg_id, line, line, cfg.LINE_NAMES.get(line, line), 'train'))
            for n, s in enumerate(order, 1):
                c.execute("INSERT INTO route_stops(seg_id,seq,stop_id) VALUES (?,?,?)", (seg_id, n, s))
    c.commit()


# ---------- 4. hand-curated interchanges ----------
def insert_interchanges(c):
    c.execute("CREATE TABLE IF NOT EXISTS interchanges(from_stop, to_stop, cost)")
    c.execute("DELETE FROM interchanges")

    def one(kw, mode):
        m = c.execute("SELECT stop_id FROM stops WHERE mode=? AND lower(name) LIKE ?",
                      (mode, f'%{kw.lower()}%')).fetchall()
        assert len(m) == 1, (kw, mode, m)
        return m[0][0]

    for a, am, b, bm, cost in cfg.INTERCHANGES:
        sa, sb = one(a, am), one(b, bm)
        c.executemany("INSERT INTO interchanges VALUES (?,?,?)", [(sa, sb, cost), (sb, sa, cost)])
    c.commit()


def main():
    c = sqlite3.connect(cfg.DB_PATH)

    train_all = load_kml_stops(cfg.KML_PATH, 'train', 'TRN')
    train = [r for r in train_all if in_box(r[3], r[4])]          # keep only the box
    if '--inspect' in sys.argv:
        inspect_kml(train_all, train)
    insert_train_stops(c, train)

    insert_metro(c, load_metro_df(cfg.METRO_CSV))
    insert_train_routes(c)
    insert_interchanges(c)

    print(c.execute("SELECT mode, COUNT(*) FROM stops GROUP BY mode").fetchall())    # bus 1727, metro 12, train 15
    print(c.execute("SELECT mode, COUNT(*) FROM routes GROUP BY mode").fetchall())   # bus 538, metro 2, train 6
    print('interchange rows:', c.execute("SELECT * FROM interchanges").fetchall())


if __name__ == '__main__':
    main()
