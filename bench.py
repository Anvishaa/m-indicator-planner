"""bench.py -- numbers for the pitch: graph size, search latency, transfer-builder scaling.

python bench.py              box-only numbers
python bench.py --full       also time the transfer builder on the full-city bus stops (config.GTFS_STOPS)
"""
import os
import sys
import time
import sqlite3
import statistics

import pandas as pd

import config as cfg
from graph import Net
from search import route, alternatives
from build_transfers import compute_transfers


def timed(fn, *a, **kw):
    t = time.perf_counter()
    out = fn(*a, **kw)
    return out, (time.perf_counter() - t) * 1000      # ms


def bench_graph(c):
    net, ms = timed(Net, c)
    nodes, edges = net.stats()
    print(f'graph build : {ms:.0f} ms  |  {nodes:,} nodes, {edges:,} edges')
    print(f'db size     : {os.path.getsize(cfg.DB_PATH) / 1e6:.2f} MB')
    return net


def bench_search(net, repeats=5):
    rows = []
    for a, am, b, bm in cfg.PAIRS:
        sa, sb = net.find(a, am), net.find(b, bm)
        if not sa or not sb:
            continue
        times = [timed(route, net, sa[0], sb[0])[1] for _ in range(repeats)]
        _, alt_ms = timed(alternatives, net, [sa[0]], [sb[0]], k=3)
        rows.append((f'{a} -> {b}', statistics.median(times), alt_ms))
    print('\nsearch latency (median of %d, ms)' % repeats)
    print(f'  {"pair":40} {"best":>8} {"3 alternatives":>16}')
    for label, ms, alt in rows:
        print(f'  {label:40} {ms:8.1f} {alt:16.1f}')
    if rows:
        print(f'  {"mean":40} {statistics.mean(r[1] for r in rows):8.1f} '
              f'{statistics.mean(r[2] for r in rows):16.1f}')


def bench_transfers(c, full=False):
    stops = c.execute("SELECT stop_id, mode, lat, lon FROM stops").fetchall()
    rows, ms = timed(compute_transfers, stops)
    print(f'\ntransfer builder (box)      : {len(stops):>7,} stops -> {len(rows):>8,} rows in {ms:.0f} ms')

    if full:
        g = pd.read_csv(cfg.GTFS_STOPS)
        bus = [(str(r.stop_id), 'bus', r.stop_lat, r.stop_lon) for r in g.itertuples()]
        others = [s for s in stops if s[1] != 'bus']      # keep train + metro so cross-mode links exist
        full_stops = bus + others
        rows, ms = timed(compute_transfers, full_stops)
        print(f'transfer builder (full city): {len(full_stops):>7,} stops -> {len(rows):>8,} rows in {ms:.0f} ms')


def main():
    c = sqlite3.connect(cfg.DB_PATH)
    net = bench_graph(c)
    bench_search(net)
    bench_transfers(c, full='--full' in sys.argv)


if __name__ == '__main__':
    main()
