"""Build the published data files for the website from the working investigation folder.

Run from anywhere:
    python3 scripts/build_data.py [path/to/XX_YANDEX_INVESTIGATION]

Defaults to the folder two levels above this script (the site lives in 07_WEBSITE/ inside it).
Everything the site reads is written to ../data and ../img. Raw inputs that are not
republished (QGIS project, third-party photos, unfiltered OSM extract) stay out of the repo.
"""
import csv, io, json, re, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from PIL import Image

SITE = Path(__file__).resolve().parents[1]
SRC = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else SITE.parent
DATA, IMG = SITE / "data", SITE / "img"
(DATA / "raw").mkdir(parents=True, exist_ok=True)
IMG.mkdir(exist_ok=True)


def read_csv(path, sep=","):
    return pd.read_csv(path, sep=sep, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def us(text):
    """US spelling for display text (centre -> center), leaving URLs and the OSM tag value data_centre alone."""
    if not isinstance(text, str):
        return text
    parts = re.split(r'(https?://\S+|"data_centre")', text)
    return "".join(p if (p.startswith("http") or p == '"data_centre"') else
                   re.sub(r"(?<![_\w])([Cc])entre(s?)\b", r"\1enter\2", p) for p in parts)


def write_csv(df, name):
    df.to_csv(DATA / name, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)


# ---------------------------------------------------------------- strikes
# Corrections applied to 03_ATTACKED_DATA_CENTERS/attack_dc.csv. Each one is logged
# here so the published table can be traced back to the working copy.
CORRECTIONS = {
    ("Kaluga, Kaluga region", "Operator"): ("Yendex", "Yandex"),            # typo
    ("Balakovo, Sarotov region", "Site"): ("Balakovo, Sarotov region", "Balakovo, Saratov region"),  # typo
}

# Reported strike time -> UTC. Only where a clock time and zone are given.
# Times in attack_dc.csv are written as GMT+2 (Prague, CEST).
#  - Sasovo 00:31 GMT+2 = 22:31 UTC on 7 Oct = 01:31 MSK, matching the Yandex Cloud
#    status page (power problems from 01:31 MSK).
#  - Vladimir 03:11 GMT+2 = 01:11 UTC; IODA drop follows at 01:40-02:00 UTC.
#  - VK 03:00 is NOT converted: IODA (AS47541) drops at 23:50-00:00 UTC, i.e. 02:50-03:00 MSK,
#    and Sboy.rf complaints start 03:00 local. "03:00 GMT+2" would put the strike an hour
#    after the drop, so the source most likely gave 03:00 MSK. Left unresolved until checked.
STRIKE_UTC = {
    "Sasovo, Ryazan region": "2026-10-07T22:31:00Z",
    "Vladimir, Vladimir region": "2026-10-11T01:11:00Z",
}

SLUG = {
    "Sasovo, Ryazan region": "sasovo",
    "Kaluga, Kaluga region": "kaluga",
    "Vladimir, Vladimir region": "vladimir",
    "Balakovo, Sarotov region": "balakovo",
    "St. Petersburg, Leningrad region": "novosergievka",
}
LABEL = {
    "sasovo": "Sasovo", "kaluga": "Kaluga", "vladimir": "Vladimir",
    "balakovo": "Balakovo", "novosergievka": "Novosergievka",
}
# rows in 01_service_disruptions.csv use these strike_event keys
EVENT = {
    "sasovo": "Sasovo 2026-10-07/08", "kaluga": "Kaluga 2026-10-09",
    "vladimir": "Vladimir 2026-10-11", "balakovo": "Balakovo 2026-10-13/14",
    "novosergievka": "Leningrad obl. 2026-10-17/18",
}
SPECS_KEY = {
    "sasovo": "Yandex - Sasovo", "kaluga": "Yandex - Kaluga", "vladimir": "Yandex - Vladimir",
    "balakovo": "Sberbank - Balakovo", "novosergievka": "VK - Novosergievka (Leningrad oblast)",
}

attack = read_csv(SRC / "03_ATTACKED_DATA_CENTERS/attack_dc.csv", sep=";")
attack = attack.loc[:, [c for c in attack.columns if c.strip()]]
specs = read_csv(SRC / "XX_KOS/facility_specs.csv").set_index("site")

features, rows = [], []
for i, r in attack.iterrows():
    site_raw = r["Site"]
    slug = SLUG[site_raw]
    rec = {k: us(v.strip()) for k, v in r.items()}
    for (s, col), (old, new) in CORRECTIONS.items():
        if s == site_raw and rec[col] == old:
            rec[col] = new
    sp = specs.loc[SPECS_KEY[slug]].map(us) if SPECS_KEY[slug] in specs.index else None
    props = {
        "n": int(float(r["Index"])) if "Index" in r and str(r["Index"]).strip() else int(i) + 1,
        "id": slug,
        "label": LABEL[slug],
        "date": datetime.strptime(rec["Date"], "%d.%m.%Y").date().isoformat(),
        "time_reported": rec["Time"],
        "time_utc": STRIKE_UTC.get(site_raw),
        "operator": rec["Operator"],
        "site": rec["Site"],
        "power": rec["Power"],
        "cloud_zone": rec["Cloud zone"],
        "operator_statement": rec["Operator statement"],
        "physical_damage": rec["Physical damage"],
        "service_effects": rec["Service effects"],
        "casualties": rec["Casualties"],
        "primary_evidence": rec["Primary evidence"],
        "sources": [s.strip() for s in rec["Sources"].split("|") if s.strip()],
        "notes": rec.get("Notes", ""),
        "event_key": EVENT[slug],
        "location": sp["location"] if sp is not None else "",
        "commissioned": sp["commissioned"] if sp is not None else "",
        "racks": sp["racks"] if sp is not None else "",
        "servers": sp["servers"] if sp is not None else "",
        "area": sp["area"] if sp is not None else "",
        "facility_notes": sp["other"] if sp is not None else "",
        "conflicts": sp["conflicts"] if sp is not None else "",
        "spec_sources": [s.strip() for s in sp["sources"].split("|")] if sp is not None else [],
    }
    lon, lat = float(rec["Longitude"]), float(rec["Latitude"])
    features.append({"type": "Feature", "properties": props,
                     "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]}})
    rows.append({**{k: v for k, v in props.items() if not isinstance(v, list)},
                 "sources": " | ".join(props["sources"]), "lat": round(lat, 6), "lon": round(lon, 6)})

(DATA / "strikes.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
write_csv(pd.DataFrame(rows), "strikes.csv")

# ---------------------------------------------------------------- map layers (from the QGIS GeoPackage exports)
# GeoPackage geometry = GP header + standard WKB. Small reader so no GDAL/fiona is needed.
import sqlite3, struct


def wkb_read(buf, off=0):
    bo = "<" if buf[off] == 1 else ">"
    gtype = struct.unpack_from(bo + "I", buf, off + 1)[0] % 1000
    off += 5

    def pts(n, off):
        out = []
        for _ in range(n):
            x, y = struct.unpack_from(bo + "dd", buf, off); off += 16
            out.append([round(x, 6), round(y, 6)])
        return out, off

    if gtype == 1:
        (c, off) = pts(1, off); return {"type": "Point", "coordinates": c[0]}, off
    if gtype == 3:
        nr = struct.unpack_from(bo + "I", buf, off)[0]; off += 4; rings = []
        for _ in range(nr):
            n = struct.unpack_from(bo + "I", buf, off)[0]; off += 4
            r, off = pts(n, off); rings.append(r)
        return {"type": "Polygon", "coordinates": rings}, off
    if gtype in (4, 6):
        n = struct.unpack_from(bo + "I", buf, off)[0]; off += 4; parts = []
        for _ in range(n):
            g, off = wkb_read(buf, off); parts.append(g["coordinates"])
        return {"type": "MultiPoint" if gtype == 4 else "MultiPolygon", "coordinates": parts}, off
    raise ValueError(f"unsupported WKB type {gtype}")


def read_gpkg(path):
    con = sqlite3.connect(path)
    table, = con.execute("select table_name from gpkg_contents where data_type='features'").fetchone()
    gcol, = con.execute("select column_name from gpkg_geometry_columns where table_name=?", (table,)).fetchone()
    cols = [r[1] for r in con.execute(f'pragma table_info("{table}")')]
    feats = []
    for row in con.execute(f'select * from "{table}"'):
        rec = dict(zip(cols, row)); blob = rec.pop(gcol)
        if blob is None:
            continue
        env = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(blob[3] >> 1) & 7]
        geom, _ = wkb_read(blob, 8 + env)
        feats.append({"type": "Feature", "properties": rec, "geometry": geom})
    return feats


def centroid(geom):
    ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
    xs, ys = [p[0] for p in ring[:-1]] or [ring[0][0]], [p[1] for p in ring[:-1]] or [ring[0][1]]
    return [round(sum(xs) / len(xs), 5), round(sum(ys) / len(ys), 5)]


def save(name, feats):
    (DATA / name).write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False),
                             encoding="utf-8")


# The Overpass extract matched the text "ЦОД" inside unrelated words: "спецодежда" (workwear shops),
# ЦОДД (traffic-control centers), village names, plus Yandex Lavka stores matched on operator=Yandex.
# Keep only: PeeringDB facilities, OSM objects tagged as data centers, or OSM objects whose
# name contains ЦОД / МЦОД / дата-центр / data center as a whole word.
DC_NAME = re.compile(r"(?<![а-яёa-z])м?цод(?![а-яёa-z])|дата[\s-]?цент|датацентр|data[\s-]?cent", re.I)


def is_dc(p):
    if any(p.get(k) for k in ("shop", "amenity", "tourism", "public_transport", "parcel_pickup")):
        return False
    tags = (p.get("building"), p.get("telecom"), p.get("industrial"), p.get("construction:telecom"))
    if "data_center" in tags or "data_centre" in tags:  # OSM uses both spellings
        return True
    names = " ".join(str(p.get(k) or "") for k in ("name", "name:ru", "name:en", "official_name", "description"))
    return bool(DC_NAME.search(names))


def clean_ops(s):  # drop e-mail addresses that PeeringDB/OSM sometimes carry in operator fields
    return "; ".join(o.strip() for o in str(s or "").split(";") if o.strip() and "@" not in o)


EXP = SRC / "02_GIS_LAYERS_EXPORT"

# 1. struck sites: building outlines (targeted_dc_outline.gpkg)
outl = read_gpkg(EXP / "targeted_dc_outline.gpkg")
save("struck_outlines.geojson", [{"type": "Feature", "geometry": f["geometry"], "properties": {
    "name": (f["properties"].get("names") or "").split(";")[0].strip(), "osm_ids": f["properties"].get("osm_ids") or "",
    "peeringdb_ids": f["properties"].get("peeringdb_ids") or ""}} for f in outl])

# 2. all data centers: OSM data-center buildings (filtered) + PeeringDB facilities
bld = [f for f in read_gpkg(EXP / "osm_dc_buildings_overpass_export.gpkg") if is_dc(f["properties"])]
bld_feats = [{"type": "Feature", "geometry": f["geometry"], "properties": {
    "name": f["properties"].get("name") or "", "operator": clean_ops(f["properties"].get("operator")),
    "osm_id": f["properties"].get("@id") or f["properties"].get("id") or "", "source": "OpenStreetMap"}} for f in bld]
save("dc_buildings.geojson", bld_feats)
save("dc_buildings_centroids.geojson", [{"type": "Feature", "properties": f["properties"],
                                         "geometry": {"type": "Point", "coordinates": centroid(f["geometry"])}} for f in bld_feats])
pdb = read_gpkg(EXP / "fac_ru_peeringDB_export.gpkg")
save("peeringdb_facilities.geojson", [{"type": "Feature", "geometry": f["geometry"], "properties": {
    "name": f["properties"].get("name") or "", "operator": clean_ops(f["properties"].get("org_name")),
    "city": f["properties"].get("city") or "", "website": f["properties"].get("website") or "",
    "networks": f["properties"].get("net_count"), "exchanges": f["properties"].get("ix_count"),
    "peeringdb_id": f["properties"].get("id"), "source": "PeeringDB"}} for f in pdb])

# 3. telecom infrastructure: the deduplicated OSM + PeeringDB sites (telecom_infrastructure.gpkg), filtered
osm_all = read_gpkg(EXP / "osm_dc_overpass_export.gpkg") + read_gpkg(EXP / "osm_dc_buildings_overpass_export.gpkg")
dc_osm = {(f["properties"].get("@id") or f["properties"].get("id")) for f in osm_all if is_dc(f["properties"])}
tel_all = read_gpkg(EXP / "telecom_infrastructure.gpkg")
tel = []
for f in tel_all:
    p = f["properties"]
    osm_ids = [x for x in str(p.get("osm_ids") or "").split(";") if x]
    if not (p.get("peeringdb_ids") or any(x in dc_osm for x in osm_ids)):
        continue
    names = [n for n in str(p.get("names") or "").split(";") if n]
    g = f["geometry"]
    coords = g["coordinates"][0] if g["type"] == "MultiPoint" else g["coordinates"]
    tel.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": coords}, "properties": {
        "name": names[0] if names else "", "aka": names[1:], "operator": clean_ops(p.get("operators")),
        "source": "OSM + PeeringDB" if osm_ids and p.get("peeringdb_ids") else ("OSM" if osm_ids else "PeeringDB"),
        "osm_ids": p.get("osm_ids") or "", "peeringdb_ids": p.get("peeringdb_ids") or ""}})
save("telecom_sites.geojson", tel)
print(f"layers: {len(outl)} struck outlines | {len(bld)} OSM DC buildings | {len(pdb)} PeeringDB | "
      f"telecom {len(tel_all)} -> {len(tel)} after filter")

# VersaTiles basemap style, exported from QGIS (protostar-dark)
(DATA / "basemap").mkdir(exist_ok=True)
shutil.copy2(EXP / "VersaTiles_basemap/vesra_map.json", DATA / "basemap/versatiles-protostar-dark.json")

# ---------------------------------------------------------------- IODA
# Same processing and strike windows as 05_OUTAGE_DASHBORDS/plot_ioda.py: 30-minute medians,
# indexed to the 6-7 Oct median, no masking. Empty 30-minute bins are kept as null (line breaks).
ioda = pd.read_csv(SRC / "05_OUTAGE_DASHBORDS/outage_data/ioda_asn_signals.csv", parse_dates=["time_utc"])
ioda["v"] = pd.to_numeric(ioda["value"], errors="coerce")
ping = ioda[ioda.datasource == "ping-slash24"]
BASE = ("2026-10-06 00:00", "2026-10-07 21:00")   # before first reported strike
SERIES = [("Yandex Cloud", "AS200350 Yandex Cloud"), ("VKontakte", "AS47541 VKontakte")]
series = []
for key, name in SERIES:
    s = ping[ping.label == key].set_index("time_utc")["v"].sort_index()
    base = float(s[BASE[0]:BASE[1]].median())
    idx = s.resample("30min").median()
    series.append({"label": key, "name": name, "asn": name.split(" ")[0], "baseline": base, "points": [
        [t.strftime("%Y-%m-%dT%H:%MZ"), None if pd.isna(v) else round(v / base * 100, 1), None if pd.isna(v) else round(v, 1)]
        for t, v in idx.items()]})
# Reported strike windows in UTC (MSK = UTC+3), copied from plot_ioda.py STRIKES.
bands = [
    {"id": "sasovo", "label": "Sasovo", "op": "Yandex", "from": "2026-10-07T21:00Z", "to": "2026-10-08T03:00Z"},
    {"id": "kaluga", "label": "Kaluga", "op": "Yandex", "from": "2026-10-09T03:00Z", "to": "2026-10-09T09:00Z"},
    {"id": "vladimir", "label": "Vladimir", "op": "Yandex", "from": "2026-10-10T21:00Z", "to": "2026-10-11T21:00Z"},
    {"id": "balakovo", "label": "Balakovo", "op": "Sber", "from": "2026-10-13T21:00Z", "to": "2026-10-14T03:00Z"},
    {"id": "novosergievka", "label": "Leningrad obl.", "op": "VK", "from": "2026-10-17T21:00Z", "to": "2026-10-18T03:00Z"},
]
meta = json.loads((SRC / "05_OUTAGE_DASHBORDS/outage_data/ioda_events_asn200350.json").read_text())["metadata"]
(DATA / "ioda_reachability.json").write_text(json.dumps({
    "source": "IODA (Georgia Tech), ping-slash24, 30-min medians",
    "pulled_utc": meta["requestTime"], "baseline_window_utc": BASE,
    "series": series, "strike_windows": bands}, indent=0), encoding="utf-8")
for f in (SRC / "05_OUTAGE_DASHBORDS/outage_data").glob("ioda_*.json"):
    shutil.copy2(f, DATA / "raw" / f.name)
shutil.copy2(SRC / "05_OUTAGE_DASHBORDS/outage_data/ioda_asn_signals.csv", DATA / "raw/ioda_asn_signals.csv")

# ---------------------------------------------------------------- media coverage (Semantic Visions svEye)
# Only aggregates and story titles are published, not the raw svEye exports.
SV = SRC / "07_SV_EYE"
frames = []
for f in SV.glob("*_svEye_*.csv"):
    d = pd.read_csv(f, encoding="utf-8-sig")
    d["company"] = f.name.split("_")[0]
    frames.append(d)
sv = pd.concat(frames)
sv["Date"] = pd.to_datetime(sv["Date"])
sv = sv[(sv.Date >= "2026-10-01") & (sv.Date < "2026-10-20")]
sv["day"] = sv.Date.dt.strftime("%Y-%m-%d")
sv["risk"] = sv["Event Category"].eq("Operational Risk")
days = pd.date_range("2026-10-01", "2026-10-19").strftime("%Y-%m-%d")
media = {"source": "Semantic Visions svEye export, " + max(sv.Date).strftime("%Y-%m-%d %H:%M") + " UTC",
         "days": list(days), "companies": []}
for comp in ("Yandex", "Sberbank", "VK"):
    c = sv[sv.company == comp]
    allc = c.groupby("day")["Articles Count"].sum().reindex(days, fill_value=0)
    risk = c[c.risk].groupby("day")["Articles Count"].sum().reindex(days, fill_value=0)
    media["companies"].append({"name": comp, "all": [int(x) for x in allc], "operational_risk": [int(x) for x in risk]})
stories = []
for f in SV.glob("*_svEye_summary_*.json"):
    for x in json.loads(f.read_text(encoding="utf-8")):
        if x["start_time"] < "2026-10-07":
            continue
        stories.append({"start": x["start_time"][:16] + "Z", "entity": x["entity_name"], "title": x["summary_title"],
                        "text": x["summary_text"], "documents": x["number_of_documents"], "sentiment": x["sentiment"],
                        "category": (x.get("summary_categories") or [{}])[0].get("event_category_name", "")})
stories.sort(key=lambda s: -s["documents"])
media["stories"] = stories
(DATA / "media_coverage.json").write_text(json.dumps(media, ensure_ascii=False, indent=0), encoding="utf-8")
print(f"svEye: {len(sv)} signal rows, {len(stories)} story clusters since 7 Oct")

# ---------------------------------------------------------------- disruption / recovery tables
for src, name in (("06_DISRUPTION_RECOVERY/01_service_disruptions.csv", "service_disruptions.csv"),
                  ("06_DISRUPTION_RECOVERY/02_migration_scenarios.csv", "migration_scenarios.csv"),
                  ("06_DISRUPTION_RECOVERY/03_recovery_tiers.csv", "recovery_tiers.csv"),
                  ("XX_KOS/facility_specs.csv", "facility_specs.csv")):
    write_csv(read_csv(SRC / src).map(us), name)

# ---------------------------------------------------------------- imagery
# Own products only (NASA FIRMS screenshots, Copernicus Browser exports). Third-party photos
# (X / Telegram reposts) are linked from the sources, not republished.
V = SRC / "04_VISUAL_CONFIRMATION"
S2 = "Contains modified Copernicus Sentinel data 2026, processed with Copernicus Browser"
FIRMS = "NASA FIRMS (VIIRS/MODIS thermal anomalies). Basemap as shown in FIRMS"
IMAGES = {
    "sasovo": [
        ("01_YANDEX_SASOVO/01_Sasovo_FIRMS_2026-10-06_2026-10-14[@41.944,54.372,15.082z].png", "firms.jpg",
         "FIRMS thermal anomalies, 6–14 Oct", "detection",
         "Detections cluster over the main hall. Each square is a satellite pixel footprint (375 m or 1 km), not the exact fire position.", FIRMS),
        ("01_YANDEX_SASOVO/A1_BEFORE_2026-10-04-00_00_2026-10-04-23_59_Sentinel-2_L1C_True_color.jpg", "s2-before.jpg",
         "Sentinel-2, 4 Oct (before)", "reference", "True colour, 10 m resolution.", S2),
        ("01_YANDEX_SASOVO/A2_AFTER_2026-10-09-00_00_2026-10-09-23_59_Sentinel-2_L1C_True_color.jpg", "s2-after.jpg",
         "Sentinel-2, 9 Oct (after)", "inconclusive",
         "Haze and cloud cover the scene. No building-level change can be read at 10 m.", S2),
    ],
    "kaluga": [
        ("02_YANDEX_KALUGA/Kaluga_FIRMS_2026-10-06_2026-10-14[@36.352,54.575,14.937z].png", "firms.jpg",
         "FIRMS thermal anomalies, 6–14 Oct", "none",
         "No detections over the site. A fire that is small, short or under cloud can be missed, so this does not rule out damage.", FIRMS),
    ],
    "vladimir": [
        ("03_YANDEX_VLADIMIR/01_Vladimir_FIRMS_2026-10-06_2026-10-14[@40.193,56.102,16.000z].png", "firms.jpg",
         "FIRMS thermal anomalies, 6–14 Oct", "none",
         "No detections over the site. The FIRMS basemap predates the later buildings on the site.", FIRMS),
        ("03_YANDEX_VLADIMIR/A1_BEFORE_2026-10-04-00_00_2026-10-04-23_59_Sentinel-2_L1C_True_color.jpg", "s2-before.jpg",
         "Sentinel-2, 4 Oct (before)", "reference", "True colour, 10 m resolution.", S2),
        ("03_YANDEX_VLADIMIR/A2_AFTER_2026-10-17-00_00_2026-10-17-23_59_Sentinel-2_L1C_True_color.jpg", "s2-after.jpg",
         "Sentinel-2, 17 Oct (after)", "consistent",
         "Roof tone changes on two buildings of the central block. At 10 m this is consistent with the roof damage seen in higher-resolution imagery (RFE/RL via Militarnyi), not proof of it.", S2),
    ],
    "balakovo": [
        ("04_SBERBANK_BALAKOVO/01_Balakovo_FIRMS_2026-10-06_2026-10-14[@47.802,51.961,14.331z].png", "firms.jpg",
         "FIRMS thermal anomalies, 6–14 Oct", "detection",
         "Detections on and around the complex, most of them on open ground.", FIRMS),
        ("04_SBERBANK_BALAKOVO/A1_BEFORE_2026-10-05-00_00_2026-10-05-23_59_Sentinel-2_L2A_True_color.jpg", "s2-before.jpg",
         "Sentinel-2, 5 Oct (before)", "reference", "True colour, 10 m resolution.", S2),
        ("04_SBERBANK_BALAKOVO/A2_AFTER_2026-10-15-00_00_2026-10-15-23_59_Sentinel-2_L2A_True_color.jpg", "s2-after.jpg",
         "Sentinel-2, 15 Oct (after)", "consistent",
         "New burn scars on open ground around the complex match most FIRMS detections. Grass fires from debris and unrelated burning both fit. No building-level change at 10 m.", S2),
    ],
    "novosergievka": [
        ("05_VK_ST_PETERSBURG/01_St_Petersburg_FIRMS_2026-10-17_2026-10-18[@30.581,59.912,16.000z].jpg", "firms.jpg",
         "FIRMS thermal anomalies, 17–18 Oct", "none",
         "No detections over the site. No cloud-free Sentinel-2 scene after the strike yet.", FIRMS),
    ],
}
manifest = {}
for slug, items in IMAGES.items():
    (IMG / slug).mkdir(exist_ok=True)
    manifest[slug] = []
    for src, out, title, result, caption, credit in items:
        im = Image.open(V / src).convert("RGB")
        im.thumbnail((1600, 1600))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82, optimize=True, progressive=True)  # re-encode: no EXIF carried over
        (IMG / slug / out).write_bytes(buf.getvalue())
        manifest[slug].append({"src": f"img/{slug}/{out}", "w": im.width, "h": im.height, "title": title,
                               "result": result, "caption": caption, "credit": credit})
(DATA / "imagery.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

(DATA / "build.json").write_text(json.dumps({"built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}))
print("done:", sorted(p.name for p in DATA.iterdir()))

# ---------------------------------------------------------------- static copy of the content in index.html
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prerender  # noqa: E402
prerender.run()
