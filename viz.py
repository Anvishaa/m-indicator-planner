import sqlite3, folium
import config as cfg

c = sqlite3.connect(cfg.DB_PATH)
pos  = {s: (la, lo) for s, la, lo in c.execute("SELECT stop_id, lat, lon FROM stops")}
mode = dict(c.execute("SELECT stop_id, mode FROM stops"))
name = dict(c.execute("SELECT stop_id, name FROM stops"))
rmode = dict(c.execute("SELECT seg_id, mode FROM routes"))
rname = dict(c.execute("SELECT seg_id, short_name FROM routes"))

m = folium.Map(location=[19.095, 72.875], zoom_start=12, tiles='cartodbpositron')
L = {k: folium.FeatureGroup(k, show=(k != 'bus routes')).add_to(m)
     for k in ['bus stops', 'train/metro stops', 'train/metro lines',
               'bus routes', 'cross-mode links', 'interchanges']}
COL = {'bus': '#888888', 'train': '#d62728', 'metro': '#1f77b4'}

# stops
for s, (la, lo) in pos.items():
    big = mode[s] != 'bus'
    folium.CircleMarker((la, lo), radius=6 if big else 2, color=COL[mode[s]], fill=True,
                        tooltip=f"{name[s]} ({mode[s]})"
                        ).add_to(L['train/metro stops' if big else 'bus stops'])

# route lines (stops in seq order)
seg = {}
for sid, st in c.execute("SELECT seg_id, stop_id FROM route_stops ORDER BY seg_id, seq"):
    seg.setdefault(sid, []).append(pos[st])
for sid, pts in seg.items():
    if rmode[sid] != 'bus' and sid.endswith('_B'):
        continue                                   # one direction is enough for the drawing
    layer = 'bus routes' if rmode[sid] == 'bus' else 'train/metro lines'
    folium.PolyLine(pts, color=COL[rmode[sid]], weight=1 if rmode[sid] == 'bus' else 4,
                    opacity=0.5, tooltip=f"{rmode[sid]} {rname[sid]}").add_to(L[layer])

# cross-mode walk links
for a, b, d in c.execute("SELECT from_stop, to_stop, walk_m FROM transfers"):
    if a < b and mode[a] != mode[b]:
        folium.PolyLine([pos[a], pos[b]], color='#2ca02c', weight=1, dash_array='4',
                        tooltip=f"walk {d} m").add_to(L['cross-mode links'])

# hand-curated interchanges
for a, b, cost in c.execute("SELECT from_stop, to_stop, cost FROM interchanges"):
    if a < b:
        folium.PolyLine([pos[a], pos[b]], color='#ff7f0e', weight=6,
                        tooltip=f"interchange {cost}").add_to(L['interchanges'])

folium.LayerControl(collapsed=False).add_to(m)
m.save('graph.html')
print('open graph.html')