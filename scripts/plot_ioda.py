"""Plot IODA active-probing reachability for Yandex Cloud and VK, indexed to pre-strike baseline,
with REPORTED strike windows (from news/operator statements, not inferred from the data)."""
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

CSV = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "outage_data" / "ioda_asn_signals.csv"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else CSV.with_name("ioda_reachability_indexed.png")

# ---- style (dark) -------------------------------------------------------------
BG, GRID, AXIS = "#0a0a0a", "#262626", "#3a3a3a"
TEXT, TEXT2, BAND = "#ededed", "#9e9e9e", "#1e1e1e"

df = pd.read_csv(CSV, parse_dates=["time_utc"])
df["v"] = pd.to_numeric(df["value"], errors="coerce")
ping = df[df.datasource == "ping-slash24"]

BASE = ("2026-10-06 00:00", "2026-10-07 21:00")   # before first reported strike
SERIES = [("Yandex Cloud", "AS200350 Yandex Cloud", "#86823f"),
          ("VKontakte", "AS47541 VKontakte", "#863f43")]

# Reported strike windows in UTC (MSK = UTC+3). Source: operator statements / press.
STRIKES = [
    ("Sasovo\n(Yandex)",   "2026-10-07 21:00", "2026-10-08 03:00"),  # night 7-8 Oct
    ("Kaluga\n(Yandex)",   "2026-10-09 03:00", "2026-10-09 09:00"),  # morning 9 Oct MSK
    ("Vladimir\n(Yandex)", "2026-10-10 21:00", "2026-10-11 21:00"),  # 11 Oct MSK, time not reported
    ("Balakovo\n(Sber)",   "2026-10-13 21:00", "2026-10-14 03:00"),  # night 13-14 Oct
    ("Leningrad obl.\n(VK)", "2026-10-17 21:00", "2026-10-18 03:00"),  # night 17-18 Oct
]

plt.rcParams.update({"text.color": TEXT, "axes.labelcolor": TEXT2,
                     "xtick.color": TEXT2, "ytick.color": TEXT2})
fig, ax = plt.subplots(figsize=(12, 5.2), dpi=150)
fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
for label, t0, t1 in STRIKES:
    ax.axvspan(pd.Timestamp(t0, tz="UTC"), pd.Timestamp(t1, tz="UTC"), color=BAND, lw=0, zorder=0)
    ax.text(pd.Timestamp(t0, tz="UTC"), 121, label, fontsize=7.5, color=TEXT2, va="top", ha="left")

for key, name, colour in SERIES:
    s = ping[ping.label == key].set_index("time_utc")["v"].sort_index()
    base = s[BASE[0]:BASE[1]].median()
    idx = (s.resample("30min").median() / base * 100)
    ax.plot(idx.index, idx.values, color=colour, lw=2, label=f"{name} (baseline {base:.0f} /24s)")
    last = idx.dropna()
    ax.text(last.index[-1], last.iloc[-1], f"  {name.split(' ', 1)[1]} {last.iloc[-1]:.0f}%",
            color=TEXT, fontsize=8, va="center")

ax.set_ylim(0, 122); ax.set_yticks(range(0, 101, 20)); ax.set_ylabel("Responsive /24 blocks, % of 6-7 Oct median", color=TEXT2)
ax.xaxis.set_major_locator(mdates.DayLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
for sp in ("top", "right"): ax.spines[sp].set_visible(False)
for sp in ("left", "bottom"): ax.spines[sp].set_color(AXIS)
ax.tick_params(colors=TEXT2, labelsize=8)
ax.set_title("Active-probing reachability of Yandex Cloud and VK networks, 6-19 Oct 2026 (UTC)",
             loc="left", fontsize=11, color=TEXT)
leg = ax.legend(loc="lower left", fontsize=8, frameon=False)
for t in leg.get_texts(): t.set_color(TEXT)
fig.text(0.01, 0.01, "Data: IODA (Georgia Tech), ping-slash24, 30-min medians. Grey bands: reported strike windows "
         "from operator/press reports, not inferred from this data.", fontsize=7, color=TEXT2)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(OUT, facecolor=BG)
print("wrote", OUT)