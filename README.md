# Multi-Modal Journey Planner (prototype)

A small proof of concept: plan one journey across **bus, train and metro** by linking nearby stops of different modes in a single graph. Built on a slice of Mumbai (Andheri to Ghatkopar) with SQLite and an in-memory search. No timetables yet; the goal is to find a path first.

## The idea

Most transit apps show each mode separately. Here, everything is one graph:

- **Nodes:** stops (bus stops, train stations, metro stations).
- **Ride edges:** a stop to the next stop along the same route (direction-specific).
- **Transfer edges:** a walk from a stop to the 5 nearest stops of each *other* mode within a distance cap (about 500 m). This is the "cross-link" table, and it's the new part.

A search (Dijkstra) over this graph returns journeys like *metro, then train, then bus*.

## Why it's light

- The whole subgraph is about **1 MB** in one SQLite file.
- Transfers are precomputed once, using a spatial index, so queries are a lookup plus a graph search.
- Query time is in the **milliseconds** range on a laptop (bus-only test: about 130 ms including trying several start/end stop pairs). [update with your numbers]

## Data

| Layer | Source | Notes |
|---|---|---|
| Bus | Mumbai GTFS (BEST operator only) | routes, stops, trips, stop_times |
| Train | BMC "Mumbai Suburban Network" stations KML (OpenCity) | 15 stations in the region: Western, Central, Harbour |
| Metro | Hand-curated, Metro Line 1 | 12 stations, coordinates checked by hand |

Region: lat 19.05 to 19.14, lon 72.82 to 72.93.
Raw data files are not included in this repo (size and licensing). See "Getting the data".

## Database schema

- `stops(stop_id, name, mode, lat, lon)`
- `routes(seg_id, route_id, short_name, long_name, mode)`
- `route_stops(seg_id, seq, stop_id)`
- `transfers(from_stop, to_stop, walk_m)`

## How to run

```bash
python -m pip install numpy scipy pandas
python build_db.py     # builds bus_subgraph.db from the data files   
python search.py       # runs example journeys                         
python -m pip install fastapi uvicorn 
python -m uvicorn api:app --reload #final interface
```

## Search

Dijkstra on an in-memory graph loaded from SQLite. Edge cost in v1 is a placeholder: a small cost per ride hop, a larger boarding penalty, and walking time from distance. These are **not real timings**.

## Results

=== Khar Road (train) -> Chembur (train) ===
 option 1:
  cost 57
    train WR: Khar Road (train) -> Bandra (train)
    walk 175 m: Bandra (train) -> Bandra (W) Bus Station
    bus 375 AS: Bandra (W) Bus Station -> Dr.Ambedkar Udyan; ChemburStation
    walk 76 m: Dr.Ambedkar Udyan; Chembur Station -> Chembur (train)
 option 2:
  cost 65
    train WR: Khar Road (train) -> Andheri (train)
    interchange in-station: Andheri (train) -> Andheri (metro)
    metro Line 1: Andheri (metro) -> Ghatkopar (metro)
    walk 9 m: Ghatkopar (metro) -> Ghatkopar (train)
    train CR: Ghatkopar (train) -> Kurla (train)
    train HR: Kurla (train) -> Chembur (train)
 option 3:
  cost 69
    walk 295 m: Khar Road (train) -> Khar Station (W) Road 
    bus 473 AS: Khar Station (W) Road  -> Priyadarshini (Chunabhatti)
    walk 12 m: Priyadarshini (Chunabhatti) -> Priyadarshini (Chunabhatti)
    bus 491 AS: Priyadarshini (Chunabhatti) -> Amar Mahal
    walk 418 m: Amar Mahal -> Chembur (train)




## Limitations

- No timetables or live data, so waiting times are approximated.
- Straight-line distance is used for walking links, not the street network.
- Directional bus stops appear as separate nodes.
- Bus data is from the public Mumbai GTFS, not from any operator's internal data.

## Next steps

- Real timings (GTFS stop_times), fares and live data.
- A\* and round-based search for alternative journeys.
- Street-network walking distances.
- Benchmark the transfer builder on the full city.