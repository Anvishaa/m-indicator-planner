"""demo.py -- the pitch output.

python demo.py              best journey + up to 3 different alternatives per pair
python demo.py --variants   also show forced-mode variants (no metro, no train, bus-only baseline...)
python demo.py --any        station -> any bus stop matching a name (config.ANY_PAIRS)
"""
import sys

import config as cfg
from graph import build
from search import route, route_any, alternatives, show


def run_pairs(net, variants=False):
    for a, am, b, bm in cfg.PAIRS:
        sa, sb = net.find(a, am), net.find(b, bm)
        if not sa or not sb:
            print('MISSING', a, am, sa, '|', b, bm, sb); continue
        print(f'\n=== {a} ({am}) -> {b} ({bm}) ===')

        alts = alternatives(net, [sa[0]], [sb[0]], k=3)
        if not alts:
            print('  no route'); continue
        for i, res in enumerate(alts, 1):
            print(f' option {i}:')
            show(res, indent='  ')

        if variants:
            for label, modes in cfg.MODE_VARIANTS:
                print(f' [{label}]')
                show(route(net, sa[0], sb[0], modes=modes))


def run_any(net):
    for a, am, b, bm in cfg.ANY_PAIRS:
        srcs, dsts = net.find(a, am), net.find(b, bm)
        if not srcs or not dsts:
            print('MISSING', a, am, len(srcs), '|', b, bm, len(dsts)); continue
        print(f'\n=== {a} ({am}) -> any "{b}" ({bm}), {len(dsts)} candidate stops ===')
        print(' multi:'); show(route_any(net, srcs, dsts))
        print(' bus  :'); show(route_any(net, srcs, dsts, modes=('bus',)))


def main():
    net = build()
    if '--any' in sys.argv:
        run_any(net)
    else:
        run_pairs(net, variants='--variants' in sys.argv)


if __name__ == '__main__':
    main()
