"""checks.py -- DB sanity checks. Usage:  python checks.py   (optionally: python checks.py Ghatkopar)"""
import sys
import sqlite3

import config as cfg
from graph import build
from search import route, show


def counts(c):
    print('stops :', c.execute("SELECT mode, COUNT(*) FROM stops GROUP BY mode").fetchall())
    print('routes:', c.execute("SELECT mode, COUNT(*) FROM routes GROUP BY mode").fetchall())   # bus 538, metro 2, train 6
    print('train transfer rows:', c.execute(
        "SELECT COUNT(*) FROM transfers t JOIN stops s ON s.stop_id=t.from_stop WHERE s.mode='train'").fetchone()[0])
    print('train stops by latitude:', c.execute(
        "SELECT stop_id, name, lat FROM stops WHERE mode='train' ORDER BY lat").fetchall())


def bus_links_per_station(c):
    """Every train / metro stop should have at least one bus link. Count = linked bus *stops*, not routes."""
    print('\nbus stops linked to each station:')
    for s, n, m in c.execute("SELECT stop_id, name, mode FROM stops WHERE mode IN ('train','metro')"):
        k = c.execute("""SELECT COUNT(*) FROM transfers t JOIN stops x ON x.stop_id=t.to_stop
                         WHERE t.from_stop=? AND x.mode='bus'""", (s,)).fetchone()[0]
        print(f'  {m:6} {n:30} {k}')


def distinct_routes(c, net, kw, mode):
    """How many different bus routes can you reach on foot from a station."""
    s = net.find(kw, mode)[0]
    n = c.execute("""
        SELECT COUNT(DISTINCT r.route_id)
        FROM transfers t
        JOIN stops x ON x.stop_id = t.to_stop
        JOIN route_stops rs ON rs.stop_id = x.stop_id
        JOIN routes r ON r.seg_id = rs.seg_id
        WHERE t.from_stop = ? AND x.mode = 'bus'""", (s,)).fetchone()[0]
    print(f'{kw} ({mode}): {n} distinct bus routes within walking distance')


def linked_bus_stops(c, net, kw, mode):
    """Which bus stops a station links to, nearest first (check the distances look sensible)."""
    s = net.find(kw, mode)[0]
    print(f'\nbus stops linked to {kw} ({mode}):')
    for r in c.execute("""SELECT x.name, x.stop_id, t.walk_m FROM transfers t
                          JOIN stops x ON x.stop_id=t.to_stop
                          WHERE t.from_stop=? AND x.mode='bus' ORDER BY t.walk_m""", (s,)):
        print(' ', r)


def interchange_check(c, net):
    print('\ninterchange rows:', c.execute("SELECT * FROM interchanges").fetchall())
    a, b = net.find('Andheri', 'metro')[0], net.find('Andheri', 'train')[0]
    print('Andheri metro -> Andheri train:'); show(route(net, a, b))


def main():
    c = sqlite3.connect(cfg.DB_PATH)
    net = build()
    kw = sys.argv[1] if len(sys.argv) > 1 else 'Ghatkopar'
    counts(c)
    bus_links_per_station(c)
    distinct_routes(c, net, kw, 'metro')
    linked_bus_stops(c, net, kw, 'metro')
    interchange_check(c, net)


if __name__ == '__main__':
    main()
