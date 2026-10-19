from pathlib import Path
import re
import geopandas as gpd
import pandas as pd
from rapidfuzz import fuzz
from unidecode import unidecode

HERE = Path(__file__).parent
RADIUS_M = 500
CRS_METRIC = "EPSG:3576"  # WGS 84 / North Pole LAEA Russia

# 1. Load each source into one schema
def osm_ids(df):
    cols = df.columns
    if "@type" in cols and "@id" in cols:            # osmium export -a type,id
        return df["@type"] + "/" + df["@id"].astype("Int64").astype(str)
    if "@id" in cols:                                # overpass-turbo, e.g. "way/123"
        return df["@id"].astype(str)
    if "osm_type" in cols and "osm_id" in cols:      # QuickOSM
        return df["osm_type"] + "/" + df["osm_id"].astype("Int64").astype(str)
    raise SystemExit(f"No OSM ID column found. Columns are:\n{cols.tolist()}")

osm = gpd.read_file(HERE / "osm_dc.geojson")
osm = gpd.GeoDataFrame({
    "source": "osm",
    "source_id": osm_ids(osm),
    "name": osm.get("name"),
    "operator": osm.get("operator"),
}, geometry=osm.geometry, crs=osm.crs)

pdb = gpd.read_file(HERE / "fac_ru.geojson")
pdb = gpd.GeoDataFrame({
    "source": "peeringdb",
    "source_id": "fac/" + pdb["id"].astype(str),
    "name": pdb["name"],
    "operator": pdb["org_name"],
}, geometry=pdb.geometry, crs=pdb.crs)

allr = gpd.GeoDataFrame(pd.concat([osm, pdb], ignore_index=True),
                        geometry="geometry", crs="EPSG:4326")
allr["uid"] = allr["source"] + ":" + allr["source_id"]
assert allr["uid"].is_unique, "duplicate uids - check source_id columns"

# 2. Normalise names
ALIASES = {"яндекс": "yandex", "ростелеком": "rostelecom", "сбербанк": "sber",
           "сбер": "sber", "мегафон": "megafon", "селектел": "selectel",
           "даталайн": "dataline", "мтс": "mts"}           # extend as you find more
STOP = {"tsod", "tsentr", "obrabotki", "dannykh", "data", "center", "centre",
        "datacenter", "datacentre", "dc", "ooo", "ao", "pao", "zao",
        "llc", "jsc", "pjsc", "ltd"}

def norm(s):
    if not isinstance(s, str):
        return ""
    s = s.lower()
    for ru, en in ALIASES.items():
        s = s.replace(ru, en)
    s = re.sub(r"[^a-z0-9 ]+", " ", unidecode(s).lower())
    return " ".join(t for t in s.split() if t not in STOP)

allr["name_n"] = allr["name"].map(norm)
allr["op_n"] = allr["operator"].map(norm)

# 3. Candidate pairs within RADIUS_M (all sources, including OSM-vs-OSM)
m = allr.to_crs(CRS_METRIC)
pairs = gpd.sjoin(m, m[["uid", "geometry"]], predicate="dwithin",
                  distance=RADIUS_M, lsuffix="a", rsuffix="b")
pairs = pairs[pairs["uid_a"] < pairs["uid_b"]]

lookup = m.set_index("uid")
rows = []
for _, p in pairs.iterrows():
    a, b = lookup.loc[p.uid_a], lookup.loc[p.uid_b]
    scores = [fuzz.token_set_ratio(x, y)
              for x in (a.name_n, a.op_n) for y in (b.name_n, b.op_n) if x and y]
    rows.append({
        "uid_a": p.uid_a, "uid_b": p.uid_b,
        "name_a": a["name"], "operator_a": a["operator"],
        "name_b": b["name"], "operator_b": b["operator"],
        "dist_m": round(a.geometry.distance(b.geometry)),
        "name_score": max(scores, default=None),
        "same_source": a["source"] == b["source"],
        "decision": "",          # you fill in: y / n
    })

cands = pd.DataFrame(rows).sort_values(["name_score", "dist_m"], ascending=[False, True])
cands.to_csv(HERE / "dedupe_candidates.csv", index=False, encoding="utf-8-sig")
allr.drop(columns=["name_n", "op_n"]).to_file(HERE / "all_records.geojson", driver="GeoJSON")
print(f"{len(allr)} records, {len(cands)} candidate pairs")