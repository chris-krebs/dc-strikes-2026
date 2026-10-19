from pathlib import Path
import json

HERE = Path(__file__).parent

with open(HERE / "fac_ru.json", encoding="utf-8") as f:
    records = json.load(f)["data"]

features, no_coords = [], []
for r in records:
    lat, lon = r.get("latitude"), r.get("longitude")
    if lat is None or lon is None:
        no_coords.append(r["name"])
        continue
    # nested fields (e.g. social_media) -> strings, so QGIS doesn't drop them
    props = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
             for k, v in r.items()}
    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},  # GeoJSON is lon, lat
        "properties": props,
    })

with open("fac_ru.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)

print(f"{len(records)} records, {len(features)} with coordinates")
print("Missing coordinates:", no_coords)