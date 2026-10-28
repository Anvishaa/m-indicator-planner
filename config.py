"""config.py -- every knob and hand-curated list lives here.

Run order:
    python load_data.py        # KML + metro CSV -> stops / routes / route_stops / interchanges
    python build_transfers.py  # cross-mode walk links -> transfers
    python checks.py           # sanity checks on the DB
    python demo.py             # journeys, mode variants, alternatives
    python bench.py            # latency, graph size, transfer-builder timing
"""

# ---------- files ----------
DB_PATH = 'bus_subgraph.db'
KML_PATH = 'suburban_stations.kml'      # BMC / OpenCity suburban stations
METRO_CSV = 'metro_stations.csv'        # hand-curated Metro Line 1 (station_name, cordinates "lat,lon")
GTFS_STOPS = 'stops_1_.txt'             # full-city bus stops, only used by bench.py

# ---------- region box (Andheri-Ghatkopar corridor) ----------
LAT_MIN, LAT_MAX = 19.05, 19.14
LON_MIN, LON_MAX = 72.82, 72.93

# ---------- cross-mode transfer linking ----------
K = 5                                   # nearest stops kept per other mode
CAP_M = 500                             # default distance cap (metres)
CAP_BY_PAIR = {                         # per mode-pair override; empty dict = use CAP_M everywhere
    # frozenset(('train', 'metro')): 800,
}
M_LAT, M_LON = 111_000, 105_000         # metres per degree (good enough at Mumbai's latitude)

# ---------- edge costs (relative units, NOT minutes) ----------
ALL_MODES = ('bus', 'train', 'metro')
RIDE = {'bus': 2.0, 'train': 2.0, 'metro': 2.0}   # per hop, tune later
BOARD = 8.0                                         # boarding penalty
WALK_PER_M = 1 / 80                                 # cost per metre
LONG_WALK_M = 300                                   # walks longer than this get an extra penalty
LONG_WALK_PENALTY = 4.0                             # set to 0.0 to reproduce the old numbers

# ---------- train lines (station keywords, in geographic order) ----------
LINES = {
    'WR': ['Jogeshwari', 'Andheri', 'Vile Parle', 'Santacruz', 'Khar Road', 'Bandra'],
    'CR': ['Kurla', 'Vidyavihar', 'Ghatkopar', 'Vikhroli', 'Kanjur Marg'],
    'HR': ['Chunna', 'Kurla', 'Tilak Nagar', 'Chembur', 'Govandi'],
}
LINE_NAMES = {'WR': 'Western Line', 'CR': 'Central Line', 'HR': 'Harbour Line'}

# ---------- hand-curated in-station interchanges ----------
# (name_a, mode_a, name_b, mode_b, cost). Both directions are added automatically.
INTERCHANGES = [
    ('Andheri', 'train', 'Andheri', 'metro', 3.0),
    # ('Ghatkopar', 'train', 'Ghatkopar', 'metro', 3.0),   # obvious second one
]

# ---------- demo pairs: (name_a, mode_a, name_b, mode_b) ----------
PAIRS = [
    ('Versova', 'metro', 'Chembur', 'train'),
    ('Bandra', 'train', 'Ghatkopar', 'metro'),
    ('Andheri', 'train', 'Ghatkopar', 'train'),
    ('Jogeshwari', 'train', 'Govandi', 'train'),
    ('Vile Parle', 'train', 'Ghatkopar', 'metro'),
    # more cross-mode ones
    ('Versova', 'metro', 'Kanjur Marg', 'train'),
    ('Santacruz', 'train', 'Ghatkopar', 'metro'),
    ('Khar Road', 'train', 'Chembur', 'train'),
    ('Jogeshwari', 'train', 'Kurla', 'train'),
    ('Bandra', 'train', 'Govandi', 'train'),
    # short ones where multi-modal should NOT win (keeps the demo honest)
    ('Vile Parle', 'train', 'Santacruz', 'train'),
    ('Vikhroli', 'train', 'Kanjur Marg', 'train'),
]

# train/metro station -> any bus stop whose name matches (uses route_any)
ANY_PAIRS = [
    ('Andheri', 'train', 'Ghatkopar', 'bus'),
]

# modes to force diversity in demo.py --variants
MODE_VARIANTS = [
    ('any mode', ALL_MODES),
    ('no metro', ('bus', 'train')),
    ('no train', ('bus', 'metro')),
    ('train + metro only', ('train', 'metro')),
    ('bus only (baseline)', ('bus',)),
]
