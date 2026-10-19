from pathlib import Path
import geopandas as gpd
import pandas as pd

HERE = Path(__file__).parent
allr = gpd.read_file(HERE / "all_records.geojson").set_index("uid")

def read_decisions(path):
    for enc in ("utf-8-sig", "latin-1"):
        for sep in (",", ";", "\t"):
            try:
                df = pd.read_csv(path, sep=sep, encoding=enc, dtype=str)
            except (pd.errors.ParserError, UnicodeDecodeError):
                continue
            if {"uid_a", "uid_b", "decision"} <= set(df.columns):
                if enc != "utf-8-sig":
                    print(f"WARNING: {path.name} is not UTF-8 - Cyrillic in it is probably damaged")
                return df
    raise SystemExit(f"Could not read {path.name} as a decisions table")

dec = read_decisions(HERE / "dedupe_candidates.csv")   # or the file you actually filled in
links = dec[dec["decision"].astype(str).str.strip().str.lower() == "y"]

# union-find: chains a=b, b=c into one site
parent = {u: u for u in allr.index}
def find(u):
    while parent[u] != u:
        parent[u] = parent[parent[u]]
        u = parent[u]
    return u
for a, b in zip(links["uid_a"], links["uid_b"]):
    parent[find(a)] = find(b)
allr["root"] = [find(u) for u in allr.index]

sites = []
for _, g in allr.groupby("root"):
    osm_g = g[g["source"] == "osm"]
    sites.append({
        "site_id": min(g.index),   # deterministic; stays stable across reruns
        "osm_ids": ";".join(osm_g["source_id"]),
        "peeringdb_ids": ";".join(g[g["source"] == "peeringdb"]["source_id"]),
        "names": ";".join(sorted(set(g["name"].dropna()))),
        "operators": ";".join(sorted(set(g["operator"].dropna()))),
        "geom_source": "osm" if len(osm_g) else "peeringdb",
        "n_records": len(g),
        "same_source_merge": g["source"].duplicated().any(),
        "geometry": osm_g.geometry.union_all() if len(osm_g) else g.geometry.iloc[0],
    })

out = gpd.GeoDataFrame(sites, geometry="geometry", crs=allr.crs)
out.to_file(HERE / "sites_merged.geojson", driver="GeoJSON")
print(f"{len(allr)} records -> {len(out)} sites")