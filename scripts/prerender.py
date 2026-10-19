"""Write the page content into index.html as plain HTML, so readers without JavaScript
(search engines, link previews, AI summarisers) see the full investigation.

Content goes between <!--B:name--> and <!--/B:name--> markers. The page script re-renders
the same sections with interactivity; this only fills the static copy. Run by build_data.py,
or on its own:  python3 scripts/prerender.py
"""
import csv, json, re
from datetime import datetime
from html import escape
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
DATA = SITE / "data"


def e(s):
    return escape(str(s if s is not None else ""), quote=True)


def fmt_date(iso):
    d = datetime.strptime(iso[:10], "%Y-%m-%d")
    return f"{d.day} {d.strftime('%b')}"


def utc(iso):
    return iso[:16].replace("T", " ")


def links(parts):
    if isinstance(parts, str):
        parts = parts.split("|")
    out = []
    for p in (x.strip() for x in parts):
        if not p:
            continue
        if re.match(r"https?://", p):
            m = re.match(r"https?://(?:www\.)?([^/]+)(/[^/?#]*)?", p)
            host = m.group(1) if m else p
            if host == "x.com" and m.group(2):
                host += m.group(2)
            out.append(f'<a href="{e(p)}" rel="noopener">{e(host)}</a>')
        else:
            out.append(f"<span>{e(p)}</span>")
    return " ".join(out)


def grade(g):
    return f'<span class="grade g-{e(g)}" title="Evidence grade {e(g)}">{e(g)}</span>' if g else ""


def rows(name):
    with open(DATA / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def jload(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


RESULT = {"detection": "Thermal detection", "consistent": "Change consistent with reports", "none": "No detection",
          "inconclusive": "Inconclusive", "reference": "Before (reference)"}


def strikes_html(strikes, imagery):
    out = []
    for f in strikes["features"]:
        p = f["properties"]
        facts = [("Operator said", p.get("operator_statement"), "quote"), ("Physical damage", p.get("physical_damage"), ""),
                 ("Service effects", p.get("service_effects"), ""), ("Casualties", p.get("casualties"), ""),
                 ("Capacity", p.get("power"), ""), ("Cloud zone", p.get("cloud_zone"), ""), ("Facility", p.get("location"), ""),
                 ("Built", p.get("commissioned"), ""), ("On site", p.get("facility_notes"), ""),
                 ("Conflicting figures", p.get("conflicts"), ""), ("Note", p.get("notes"), "")]
        dl = "".join(f'<dt>{k}</dt><dd{f" class={chr(34)}{c}{chr(34)}" if c else ""}>{e(v)}</dd>'
                     for k, v, c in facts if v and v not in ("n/a", "unknown"))
        when = f'{fmt_date(p["date"])} 2026, {e(p["time_reported"])}' + (f'<br>{p["time_utc"][11:16]} UTC' if p.get("time_utc") else "")
        imgs = "".join(
            f'<figure><img src="{e(im["src"])}" width="{im["w"]}" height="{im["h"]}" loading="lazy" alt="{e(im["title"] + ". " + im["caption"])}">'
            f'<figcaption><b>{e(im["title"])}</b><span class="result {e(im["result"])}">{RESULT.get(im["result"], "")}</span><br>{e(im["caption"])}</figcaption></figure>'
            for im in imagery.get(p["id"], []))
        x = p.get("x_posts") or []
        extra = (f'<a href="{e(p["firms_link"])}" rel="noopener">FIRMS map</a> ' if p.get("firms_link") else "") + \
                (f"Posts on X: {links(x)}" if x else "Posts on X: none found")
        prim = f' <span>Primary evidence:</span> {links(p["primary_evidence"])}' if p.get("primary_evidence") else ""
        out.append(f'''<article class="strike" id="strike-{e(p["id"])}">
<div class="strike-head"><span class="num" aria-hidden="true">{p["n"]}</span><h3>{e(p["label"])}</h3>
<p>{e(p["operator"])}, {e(p["site"])}</p><p class="when">{when}</p></div>
<div><dl class="facts">{dl}</dl><p class="sources">Sources: {links(p.get("sources", []))}{prim}</p></div>
{f'<div class="imagery">{imgs}</div>' if imgs else ""}<p class="img-links">{extra}</p></article>''')
    return "\n".join(out)


def ioda_parts(d):
    last = []
    for s in d["series"]:
        v = [p for p in s["points"] if p[1] is not None][-1]
        last.append((s["label"], v))
    t = max(v[0] for _, v in last)
    summary = f"At the last reading ({utc(t)} UTC), " + " and ".join(f"{lab} was at {round(v[1])}% of its baseline" for lab, v in last) + "."
    return summary, utc(d["pulled_utc"]) + " UTC"


def radar_html(cfg):
    out = []
    for g in cfg["groups"]:
        items = "".join(f'<li>Cloudflare, Inc. “{e(x["title"])}.” Cloudflare Radar, 2026, <a href="{e(x["url"])}" rel="noopener">'
                        f'{e(x["url"].replace("https://", ""))}</a>. Accessed {e(cfg["accessed"])}.</li>' for x in g["embeds"])
        out.append(f'<div class="radar-panel"><h3>{e(g["label"])}</h3><p>{e(g["note"])}</p><ul>{items}</ul></div>')
    return "\n".join(out)


STORY_RE = re.compile(r"drone|attack|strike|target|data cent|outage|disrupt|traffic|emergency|restor|force majeure|migrat|"
                      r"supercomputer|hardware|phishing|waive|compensation|backup|doomsday|connectivity|failure", re.I)


def media_parts(m):
    days = m["days"]
    chart = "".join(f'<p class="media-row"><span class="m-name">{e(c["name"])}</span><span>{sum(c["all"])} articles, 1–19 Oct; '
                    f'peak {max(c["all"])} on {fmt_date(days[c["all"].index(max(c["all"]))])}</span></p>' for c in m["companies"])
    st = [s for s in m["stories"] if STORY_RE.search(s["title"])][:14]
    stories = ('<thead><tr><th>Started (UTC)</th><th>Entity</th><th>Story (machine-generated summary)</th><th>Articles</th><th>Sentiment</th></tr></thead><tbody>' +
               "".join(f'<tr><td class="id">{utc(s["start"])}</td><td>{e(s["entity"])}</td><td class="wide"><details><summary>{e(s["title"])}</summary>'
                       f'<p class="muted">{e(s["text"])}</p></details></td><td>{s["documents"]}</td><td class="sentiment">{e(s["sentiment"])}</td></tr>' for s in st) +
               "</tbody>")
    return chart, stories, m["source"].replace("Semantic Visions svEye export, ", "export of ")


def event_label(k):
    return k.replace("Leningrad obl.", "Novosergievka (Leningrad obl.)")


def disruptions_html(rs):
    h = ('<thead><tr><th>ID</th><th>Service</th><th>Affected</th><th>Reported disruption</th><th>When (MSK)</th><th>Last known status</th>'
         '<th>Grade</th><th>Basis</th><th>Caveat</th><th>Sources</th></tr></thead><tbody>')
    cur = None
    for r in rs:
        if r["strike_event"] != cur:
            cur = r["strike_event"]
            h += f'<tr class="group"><td colspan="10">{e(event_label(cur))}</td></tr>'
        asof = f'<br><span class="muted">as of {fmt_date(r["status_date"])}</span>' if r["status_date"] else ""
        h += (f'<tr><td class="id">{e(r["row_id"])}</td><td class="mid">{e(r["service"])}<br><span class="muted">{e(r["owner_operator"])}</span></td>'
              f'<td>{e(r["affected_party"])}</td><td class="wide">{e(r["disruption"])}</td><td>{e(r["time_msk"])}</td>'
              f'<td class="mid">{e(r["last_known_status"])}{asof}</td><td>{grade(r["evidence_grade"])}</td>'
              f'<td class="mid">{e(r["evidence_basis"])}<br><span class="muted">{e(r["source_chain"])}</span></td>'
              f'<td class="caveat">{e(r["caveat"])}</td><td>{links(r["sources"])}</td></tr>')
    return h + "</tbody>"


def recovery_parts(rec, mig):
    tiers = {}
    for r in rec:
        t = r["recovery_tier"].split(" ")[0]
        if re.fullmatch(r"T\d", t) and t not in tiers:
            tiers[t] = r
    tiers_html = "".join(f'<div><b>{t}</b><span class="dur">{e(tiers[t]["typical_duration"])}</span><span>{e(tiers[t]["tier_definition"])}</span></div>'
                         for t in sorted(tiers))
    rec_html = ('<thead><tr><th>ID</th><th>Facility</th><th>Component</th><th>Known damage</th><th>Tier</th><th>Status 19 Oct</th>'
                '<th>Basis</th><th>Assessment</th><th>Sources</th></tr></thead><tbody>' +
                "".join(f'<tr><td class="id">{e(r["row_id"])}</td><td class="mid">{e(r["facility"])}</td><td class="mid">{e(r["component"])}</td>'
                        f'<td class="mid">{e(r["known_damage"])}</td><td>{e(r["recovery_tier"])}</td><td class="wide">{e(r["status_2026-10-19"])}</td>'
                        f'<td>{e(r["basis"])}</td><td>{e(r["assessment_type"])}</td><td>{links(r["sources"])}</td></tr>' for r in rec) + "</tbody>")
    mig_html = ('<thead><tr><th>ID</th><th>Operator</th><th>Scenario</th><th>Evidence for</th><th>Against or unknown</th><th>What to watch</th>'
                '<th>Assessment</th><th>Sources</th></tr></thead><tbody>' +
                "".join(f'<tr><td class="id">{e(r["scenario_id"])}</td><td>{e(r["owner_operator"])}</td><td class="mid"><b>{e(r["scenario"])}</b><br>{e(r["description"])}</td>'
                        f'<td class="wide">{e(r["evidence_for"])}</td><td class="mid">{e(r["evidence_against_or_unknown"])}</td>'
                        f'<td class="mid">{e(r["observable_indicators"])}</td><td class="mid"><b>{e(r["assessment"])}</b><br>'
                        f'<span class="muted">{e(r["assessment_basis"])}</span></td><td>{links(r["sources"])}</td></tr>' for r in mig) + "</tbody>")
    return tiers_html, rec_html, mig_html


def run():
    strikes, imagery = jload("strikes.geojson"), jload("imagery.json")
    summary, pulled = ioda_parts(jload("ioda_reachability.json"))
    chart, stories, msrc = media_parts(jload("media_coverage.json"))
    dis = rows("service_disruptions.csv")
    tiers, rec, mig = recovery_parts(rows("recovery_tiers.csv"), rows("migration_scenarios.csv"))
    n = lambda f: len(jload(f)["features"])
    parts = {
        "count-struck": str(len(strikes["features"])),
        "count-dcs": str(n("dc_buildings.geojson") + n("peeringdb_facilities.geojson")),
        "count-telecom": str(n("telecom_sites.geojson")),
        "strikes": strikes_html(strikes, imagery),
        "ioda-pulled": pulled, "ioda-summary": e(summary),
        "radar": radar_html(jload("cloudflare_embeds.json")),
        "media-chart": chart, "media-source": e(msrc), "stories": stories,
        "f-count": f"{len(dis)} of {len(dis)} rows", "disruptions": disruptions_html(dis),
        "tiers": tiers, "recovery": rec, "migration": mig,
        "built": utc(jload("build.json")["built_utc"]) + " UTC",
    }
    page = (SITE / "index.html").read_text(encoding="utf-8")
    for k, v in parts.items():
        pat = re.compile(rf"<!--B:{re.escape(k)}-->.*?<!--/B:{re.escape(k)}-->", re.S)
        if not pat.search(page):
            raise SystemExit(f"marker {k} missing from index.html")
        page = pat.sub(lambda _m: f"<!--B:{k}-->{v}<!--/B:{k}-->", page)
    (SITE / "index.html").write_text(page, encoding="utf-8")
    print(f"prerendered {len(parts)} sections into index.html")


if __name__ == "__main__":
    run()
