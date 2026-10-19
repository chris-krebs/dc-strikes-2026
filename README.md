# Strikes on Russian data centers, October 2026

Open-source investigation of five drone strikes on Yandex, Sber and VK data centers in Russia between 8 and 18 October 2026. The site maps the struck facilities against other Russian data centers and telecom sites. It sets out operator statements, satellite imagery (NASA FIRMS, Sentinel-2), IODA network-reachability measurements, Cloudflare Radar traffic, media coverage (Semantic Visions svEye), and grades every reported service disruption from A to D.

Author: Kristof Krebs. Corrections are welcome as issues; please include a source.

Built with the assistance of Claude Opus 5.5 (Anthropic) for parts of the coding, data processing and analysis, source gathering and text drafting. All output was reviewed by the author, who is responsible for the content.

## Repository layout

```
index.html                    the page (static; no build step)
assets/site.css, site.js      styles; map, charts and tables, all loaded from data/
data/
  strikes.geojson/.csv        the five struck sites, from the working table
  struck_outlines.geojson     building outlines of the struck sites
  dc_buildings.geojson        OSM data-center buildings (filtered) + centroids file for small zooms
  peeringdb_facilities.geojson  PeeringDB facilities in Russia (contact fields removed)
  telecom_sites.geojson       merged, deduplicated OSM + PeeringDB sites (filtered)
  basemap/                    VersaTiles style exported from QGIS
  facility_specs.csv          capacity, racks, servers, with conflicting figures noted
  service_disruptions.csv     one row per reported effect, graded A–D
  recovery_tiers.csv          recovery tier per damaged component
  migration_scenarios.csv     operator responses and what to watch
  ioda_reachability.json      IODA chart data (30-min medians, indexed to 6–7 Oct)
  cloudflare_embeds.json      Cloudflare Radar embeds and citations (edited by hand)
  media_coverage.json         daily svEye article counts and story summaries (aggregates only)
  imagery.json                captions, results and credits for img/
  raw/                        untouched IODA API responses and the full signal table
img/                          FIRMS and Sentinel-2 images, re-encoded (no metadata)
scripts/                      build_data.py rebuilds data/ and img/; pull_ioda.py re-pulls IODA
```

## Updating

1. Edit the working files in the investigation folder (CSV tables, GeoPackage exports, imagery, svEye exports).
2. `python3 scripts/build_data.py` (needs pandas and Pillow). It also writes the strike entries, tables and dates into `index.html` as plain HTML (`scripts/prerender.py`), so the content is readable without JavaScript, by search engines, link previews and AI summarisers. Edit text outside the `data-b` / `data-e` marker spans only; anything between them is overwritten.
3. Commit and push. GitHub Pages republishes within a minute or two.

`cloudflare_embeds.json` is not rebuilt by the script. To add a chart: on radar.cloudflare.com set the network and date range, click the share icon, choose **Fixed Time**, and copy the `src` of the iframe into the file with a title and citation. Fixed Time keeps the strike period in view; Real Time slides forward and the event drops out of the chart within days.

## Map

Base maps: OpenStreetMap, VersaTiles (protostar-dark style from QGIS, without the 3D terrain) and Esri World Imagery, all on a globe projection. Overlays: struck data centers, telecom infrastructure (OSM data-center buildings + PeeringDB facilities), all data centers (merged, deduplicated sites). The OSM extract matched the text "ЦОД" inside unrelated words (workwear shops, traffic-control centers); `build_data.py` keeps only objects tagged as data centers or named as one as a whole word.

## Sources and licences

- Network data: IODA, © Georgia Tech Research Corporation. Cloudflare Radar, CC BY-NC 4.0.
- Media data: Semantic Visions svEye. Only daily aggregates and story summaries are published, not the raw exports.
- Imagery: NASA FIRMS; contains modified Copernicus Sentinel data 2026, processed with Copernicus Browser; Esri World Imagery.
- Map data: © OpenStreetMap contributors (ODbL); PeeringDB; VersaTiles.
- Photos and videos posted on X are linked from the strike entries, not republished.
