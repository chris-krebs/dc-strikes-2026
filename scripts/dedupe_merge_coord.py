from pathlib import Path
import geopandas as gpd
import pandas as pd

HERE = Path(__file__).parent
DECISIONS = HERE / "dedupe_candidates.csv"   # the file you filled in

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

allr = gpd.read_file(HERE / "all_records.geojson").set_index("uid")
dec = read_decisions(DECISIONS)
links = dec[dec["decision"].fillna("").str.strip().str.lower() == "y"]
print(f"{len(links)} pairs marked y")

# stop if a decision points at a record that no longer exists (e.g. after re-running script 1)
unknown = (set(links["uid_a"]) | set(links["uid_b"])) - set(allr.index)
if unknown:
    raise SystemExit(f"Decisions refer to records not in all_records.geojson:\n{sorted(unknown)}")

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
        "site_id": min(g.index),
        "osm_ids": ";".join(osm_g["source_id"]),
        "peeringdb_ids": ";".join(g[g["source"] == "peeringdb"]["source_id"]),
        "names": ";".join(sorted(set(g["name"].dropna()))),
        "operators": ";".join(sorted(set(g["operator"].dropna()))),
        "geom_source": "osm" if len(osm_g) else "peeringdb",
        "n_records": len(g),
        "same_source_merge": bool(g["source"].duplicated().any()),
        "geometry": osm_g.geometry.union_all() if len(osm_g) else g.geometry.iloc[0],
    })

out = gpd.GeoDataFrame(sites, geometry="geometry", crs=allr.crs).sort_values("site_id")
out.to_file(HERE / "sites_merged.geojson", driver="GeoJSON")

# CSV copy: one point per site (inside the footprint) + full geometry as WKT
csv = out.copy()
pt = csv.geometry.representative_point()
csv["lon"] = pt.x.round(6)
csv["lat"] = pt.y.round(6)
csv["wkt"] = csv.geometry.to_wkt()
pd.DataFrame(csv.drop(columns="geometry")).to_csv(
    HERE / "sites_merged.csv", index=False, encoding="utf-8-sig")

print(f"{len(allr)} records -> {len(out)} sites")
print("Wrote sites_merged.geojson and sites_merged.csv")