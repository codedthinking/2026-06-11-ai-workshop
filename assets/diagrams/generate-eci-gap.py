#!/usr/bin/env python3
"""Generate open-closed-eci-gap.svg from Epoch AI data.

Downloads epoch_capabilities_index.csv from epoch.ai/data/benchmark_data.zip,
computes running-max ECI for closed vs open-weight models, and writes an SVG
with step-function lines and shaded gap area.

Usage:
    python generate-eci-gap.py          # writes open-closed-eci-gap.svg
"""

import csv
import io
import os
import zipfile
from collections import OrderedDict
from datetime import datetime, timedelta
from urllib.request import urlopen

# ── download ────────────────────────────────────────────────────────
DATA_URL = "https://epoch.ai/data/benchmark_data.zip"
CSV_NAME = "epoch_capabilities_index.csv"

print(f"Downloading {DATA_URL} …")
with urlopen(DATA_URL) as resp:
    zdata = resp.read()

with zipfile.ZipFile(io.BytesIO(zdata)) as zf:
    with zf.open(CSV_NAME) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
        raw = list(reader)

print(f"  {len(raw)} rows")

# ── parse ───────────────────────────────────────────────────────────
rows = []
for r in raw:
    date_str = r["Release date"].strip()
    access = r["Model accessibility"].strip()
    eci = r["ECI Score"].strip()
    name = (
        r["Display name"].strip()
        or r["Model name"].strip()
        or r["Model version"].strip()
    )
    if not date_str or not eci:
        continue
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        continue
    rows.append((dt, float(eci), "Open weights" in access, name))

rows.sort(key=lambda r: r[0])

# ── running-max frontiers ───────────────────────────────────────────
open_pts, closed_pts = [], []
open_max = closed_max = -999
for dt, eci, is_open, name in rows:
    if is_open:
        if eci > open_max:
            open_max = eci
            open_pts.append((dt, eci, name))
    else:
        if eci > closed_max:
            closed_max = eci
            closed_pts.append((dt, eci, name))

# ── SVG geometry ────────────────────────────────────────────────────
W, H = 1040, 600
ml, mr, mt, mb = 110, 50, 120, 100
pw = W - ml - mr
ph = H - mt - mb

date_min = datetime(2023, 1, 1)
date_max = datetime(2026, 7, 1)
eci_min = 90
eci_max = 165


def dx(dt):
    frac = (dt - date_min).total_seconds() / (date_max - date_min).total_seconds()
    return ml + frac * pw


def ey(eci):
    frac = (eci - eci_min) / (eci_max - eci_min)
    return mt + ph - frac * ph


# ── step-function polyline ──────────────────────────────────────────
def step_polyline(pts):
    if not pts:
        return ""
    segs = [f"{dx(pts[0][0]):.1f},{ey(pts[0][1]):.1f}"]
    for i in range(1, len(pts)):
        segs.append(f"{dx(pts[i][0]):.1f},{ey(pts[i-1][1]):.1f}")
        segs.append(f"{dx(pts[i][0]):.1f},{ey(pts[i][1]):.1f}")
    segs.append(f"{dx(date_max):.1f},{ey(pts[-1][1]):.1f}")
    return " ".join(segs)


closed_step = step_polyline(closed_pts)
open_step = step_polyline(open_pts)

# ── daily running max (for gap polygon) ─────────────────────────────
def daily_max(pts):
    result = OrderedDict()
    cur = None
    idx = 0
    d = date_min
    while d <= date_max:
        while idx < len(pts) and pts[idx][0] <= d:
            v = pts[idx][1]
            if cur is None or v > cur:
                cur = v
            idx += 1
        if cur is not None:
            result[d] = cur
        d += timedelta(days=1)
    return result


cd = daily_max(closed_pts)
od = daily_max(open_pts)
common = sorted(set(cd.keys()) & set(od.keys()))
sampled = common[::7]
if sampled[-1] != common[-1]:
    sampled.append(common[-1])

gap_top = " ".join(f"{dx(d):.1f},{ey(cd[d]):.1f}" for d in sampled)
gap_bot = " ".join(f"{dx(d):.1f},{ey(od[d]):.1f}" for d in reversed(sampled))

# ── labels ──────────────────────────────────────────────────────────
closed_labels = {
    "GPT-4 (Mar 2023)": (-5, -12),
    "o1-preview": (-5, -12),
    "GPT-5 (high)": (-5, -12),
    "GPT-5.5 Pro (xhigh)": (-60, -12),
}
open_labels = {
    "LLaMA-65B": (6, 16),
    "DeepSeek-R1": (6, 16),
    "Llama 3.1-405B": (6, 16),
    "Kimi K2.6": (6, 16),
}

# ── build SVG ───────────────────────────────────────────────────────
years = [2023, 2024, 2025, 2026]
eci_ticks = [100, 110, 120, 130, 140, 150, 160]

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="'Brockmann','Helvetica Neue',Arial,sans-serif">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&amp;display=swap');
      .mono {{ font-family: 'DM Mono', ui-monospace, monospace; }}
      .t  {{ fill:#fff; font-weight:700; }}
      .l  {{ fill:#D4D2E3; }}
      .m  {{ fill:#9795B5; }}
      .red{{ fill:#E61E25; }}
      .cy {{ fill:#35E0D8; }}
      .am {{ fill:#E0A85A; }}
    </style>
  </defs>

  <rect width="{W}" height="{H}" fill="#1D1D40"/>

  <!-- header -->
  <text x="50" y="42" class="mono cy" font-size="14" letter-spacing="3">~ THE OPEN&#8211;CLOSED GAP</text>
  <text x="50" y="78" class="t" font-size="30">Open weights trail the frontier by months, not years</text>
  <text x="50" y="104" class="m" font-size="16">Epoch Capabilities Index (ECI): running maximum. The gap is ~8 points &#8776; 4 months.</text>

  <!-- legend -->
  <g font-size="14">
    <line x1="580" y1="42" x2="612" y2="42" stroke="#E61E25" stroke-width="3"/><text x="620" y="46" class="l">closed frontier</text>
    <line x1="760" y1="42" x2="792" y2="42" stroke="#35E0D8" stroke-width="3"/><text x="800" y="46" class="l">best open-weight</text>
  </g>

  <!-- axes -->
  <line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}" stroke="#9795B5" stroke-width="1.2"/>
  <line x1="{ml}" y1="{mt + ph}" x2="{ml + pw}" y2="{mt + ph}" stroke="#9795B5" stroke-width="1.2"/>
  <text x="{ml - 10}" y="{mt - 8}" class="mono m" font-size="13" text-anchor="end">ECI &#8593;</text>
'''

for y in years:
    x = dx(datetime(y, 1, 1))
    svg += f'  <line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{mt + ph}" stroke="rgba(151,149,181,0.15)" stroke-width="1"/>\n'
    svg += f'  <text x="{x:.1f}" y="{mt + ph + 24}" class="mono m" font-size="14" text-anchor="middle">{y}</text>\n'

for e in eci_ticks:
    y = ey(e)
    svg += f'  <line x1="{ml}" y1="{y:.1f}" x2="{ml + pw}" y2="{y:.1f}" stroke="rgba(151,149,181,0.10)" stroke-width="1"/>\n'
    svg += f'  <text x="{ml - 10}" y="{y + 5:.1f}" class="mono m" font-size="12" text-anchor="end">{e}</text>\n'

svg += f'  <polygon fill="#9795B5" fill-opacity="0.15" points="{gap_top} {gap_bot}"/>\n'
svg += f'  <polyline fill="none" stroke="#E61E25" stroke-width="2.5" points="{closed_step}"/>\n'
svg += f'  <polyline fill="none" stroke="#35E0D8" stroke-width="2.5" points="{open_step}"/>\n'

for dt, eci, name in closed_pts:
    x, y = dx(dt), ey(eci)
    svg += f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#E61E25"/>\n'
    if name in closed_labels:
        ox, oy = closed_labels[name]
        short = name.split(" (")[0]
        svg += f'  <text x="{x + ox:.1f}" y="{y + oy:.1f}" class="mono red" font-size="12" text-anchor="start">{short}</text>\n'

for dt, eci, name in open_pts:
    x, y = dx(dt), ey(eci)
    svg += f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#35E0D8"/>\n'
    if name in open_labels:
        ox, oy = open_labels[name]
        short = name.split(" (")[0]
        svg += f'  <text x="{x + ox:.1f}" y="{y + oy:.1f}" class="mono cy" font-size="12">{short}</text>\n'

annot_date = datetime(2026, 3, 15)
c_val = cd[annot_date]
o_val = od[annot_date]
ax = dx(annot_date)
ay1, ay2 = ey(c_val), ey(o_val)
svg += f'  <line x1="{ax:.1f}" y1="{ay1:.1f}" x2="{ax:.1f}" y2="{ay2:.1f}" stroke="#E0A85A" stroke-width="2" stroke-dasharray="5 3"/>\n'
svg += f'  <text x="{ax + 10:.1f}" y="{(ay1+ay2)/2 + 5:.1f}" class="mono am" font-size="13">~{c_val - o_val:.0f} pts &#8776; 4 mo</text>\n'

svg += f'  <text x="50" y="{H - 22}" class="mono m" font-size="12">Source: Epoch AI Capabilities Index (epoch.ai/data). CC BY. Downloaded June 2026.</text>\n'
svg += "</svg>\n"

out_path = os.path.join(os.path.dirname(__file__), "open-closed-eci-gap.svg")
with open(out_path, "w") as f:
    f.write(svg)

print(f"Wrote {out_path}")
