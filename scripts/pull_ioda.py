from pathlib import Path
import datetime as dt, json, time
import requests, pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "outage_data"; OUT.mkdir(exist_ok=True)
API = "https://api.ioda.inetintel.cc.gatech.edu/v2"
T0 = int(dt.datetime(2026, 10, 6, tzinfo=dt.timezone.utc).timestamp())
T1 = int(dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc).timestamp())

# verify each ASN on bgp.he.net before trusting results; add Sber's
ASNS = {"13238": "Yandex", "200350": "Yandex Cloud", "47541": "VKontakte"}

def get(path, **params):
    r = requests.get(f"{API}{path}", params=params, timeout=90)
    r.raise_for_status()
    return r.json()

rows = []
for asn, label in ASNS.items():
    sig = get(f"/signals/raw/asn/{asn}", **{"from": T0, "until": T1})
    (OUT / f"ioda_signals_asn{asn}.json").write_text(json.dumps(sig))
    ev = get("/outages/events", entityType="asn", entityCode=asn, **{"from": T0, "until": T1})
    (OUT / f"ioda_events_asn{asn}.json").write_text(json.dumps(ev))
    for s in sig["data"][0]:
        for i, v in enumerate(s["values"]):
            rows.append({"asn": asn, "label": label, "datasource": s["datasource"],
                         "time_utc": dt.datetime.fromtimestamp(s["from"] + i * s["step"], dt.timezone.utc),
                         "value": v})
    time.sleep(1)

pd.DataFrame(rows).to_csv(OUT / "ioda_asn_signals.csv", index=False)
print(pd.DataFrame(rows).groupby(["label", "datasource"]).size())