#!/usr/bin/env python3
"""Generate cost-vs-capability scatter from Epoch AI + OpenRouter data.

Each circle = one model. Color = open (cyan) vs closed (red).
Circle area scales with OpenRouter usage (status_heuristics.success).
X = input cost per million tokens (log scale).
Y = Epoch Capabilities Index (ECI).

Models with ECI scores use them directly. Models without ECI but with
an OpenRouter Intelligence Index score have their ECI estimated via a
linear fit (II = 0.703 * ECI - 53.5, R² = 0.68, n = 12 overlap).

Usage:
    python generate-tradeoff-scatter.py   # writes tradeoff-scatter.svg
"""

import csv
import io
import json
import math
import os
import re
import zipfile
from urllib.request import urlopen

# ── Linear fit: II = 0.703 * ECI - 53.5 ────────────────────────────
# Estimated from 12 overlapping models. Inverse: ECI = (II + 53.5) / 0.703
FIT_SLOPE = 0.703
FIT_INTERCEPT = -53.5


def ii_to_eci(ii_score):
    return (ii_score - FIT_INTERCEPT) / FIT_SLOPE


# ── OpenRouter Intelligence Index (top 20, June 2026) ──────────────
# Source: openrouter.ai/<model>/benchmarks — not available via API.
II_SCORES = {
    "anthropic/claude-opus-4.8":     61.4,
    "openai/gpt-5.5":               60.2,
    "anthropic/claude-opus-4.7":     57.3,
    "google/gemini-3.1-pro-preview": 57.2,
    "openai/gpt-5.4":               56.8,
    "qwen/qwen3.7-max":             56.6,
    "google/gemini-3.5-flash":       55.3,
    "minimax/minimax-m3":            54.7,
    "moonshotai/kimi-k2.6":          53.9,
    "xiaomi/mimo-v2.5-pro":          53.8,
    "openai/codex-mini-latest":      53.6,
    "qwen/qwen3.7-plus":            53.3,
    "x-ai/grok-4.3":                53.2,
    "anthropic/claude-opus-4.6":     52.9,
    "qwen/qwen3.6-max":             51.8,
    "anthropic/claude-sonnet-4.6":   51.7,
    "deepseek/deepseek-v4-pro":      51.5,
    "z-ai/glm-5.1":                  51.4,
    "openai/gpt-5.2":                51.3,
    "qwen/qwen3.6-plus":            50.0,
}

# Open-weight status for II-only models
II_OPEN = {
    "anthropic/claude-opus-4.8": False,
    "minimax/minimax-m3": False,
    "xiaomi/mimo-v2.5-pro": True,
    "qwen/qwen3.7-max": False,
    "qwen/qwen3.7-plus": False,
    "deepseek/deepseek-v4-pro": True,
    "z-ai/glm-5.1": False,
}

# Display names for II-only models
II_NAMES = {
    "anthropic/claude-opus-4.8": "Opus 4.8",
    "minimax/minimax-m3": "MiniMax M3",
    "xiaomi/mimo-v2.5-pro": "MiMo V2.5 Pro",
    "qwen/qwen3.7-max": "Qwen 3.7 Max",
    "qwen/qwen3.7-plus": "Qwen 3.7+",
    "deepseek/deepseek-v4-pro": "DS V4 Pro",
    "z-ai/glm-5.1": "GLM-5.1",
}

# ── download Epoch AI ECI data ──────────────────────────────────────
print("Downloading Epoch AI benchmark data …")
with urlopen("https://epoch.ai/data/benchmark_data.zip") as resp:
    zdata = resp.read()

eci_all = {}
with zipfile.ZipFile(io.BytesIO(zdata)) as zf:
    with zf.open("epoch_capabilities_index.csv") as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")):
            name = (
                row["Display name"].strip()
                or row["Model name"].strip()
                or row["Model version"].strip()
            )
            score = row["ECI Score"].strip()
            access = row["Model accessibility"].strip()
            if not score:
                continue
            eci_all[row["Model version"].strip()] = {
                "name": name,
                "eci": float(score),
                "open": "Open weights" in access,
            }

print(f"  {len(eci_all)} ECI entries")

# Group by family, keep best score per family
def family_key(v):
    return re.sub(r"_(low|medium|high|xhigh|max)$", "", v)

families = {}
for ver, info in eci_all.items():
    fk = family_key(ver)
    if fk not in families or info["eci"] > families[fk]["eci"]:
        families[fk] = {**info, "version": ver}

# ── download OpenRouter catalog ─────────────────────────────────────
print("Downloading OpenRouter catalog …")
with urlopen("https://openrouter.ai/api/frontend/v1/catalog/models") as resp:
    or_data = json.loads(resp.read())["data"]

or_lookup = {}
for m in or_data:
    ep = m.get("endpoint")
    if not ep:
        continue
    pricing = ep.get("pricing")
    if not pricing:
        continue
    prompt_price = float(pricing.get("prompt", 0)) * 1e6
    if prompt_price <= 0:
        continue
    sh = ep.get("status_heuristics") or {}
    usage = sh.get("success", 0)
    or_lookup[m["slug"]] = {
        "name": m.get("short_name", m["name"]),
        "cost": prompt_price,
        "usage": usage,
    }

print(f"  {len(or_lookup)} priced models on OpenRouter")

# ── ECI family key → OpenRouter slug mapping ────────────────────────
ECI_TO_SLUG = {
    "gpt-5.5-pre-release": "openai/gpt-5.5",
    "gpt-5.4-2026-03-05": "openai/gpt-5.4",
    "gpt-5.4-mini-2026-03-17": "openai/gpt-5.4-mini",
    "gpt-5.4-nano-2026-03-17": "openai/gpt-5.4-nano",
    "gpt-5.2": "openai/gpt-5.2",
    "gpt-5": "openai/gpt-5",
    "gpt-5-mini-2025-08-07": "openai/gpt-5-mini",
    "gpt-4.1-mini-2025-04-14": "openai/gpt-4.1-mini",
    "gpt-4.1-nano-2025-04-14": "openai/gpt-4.1-nano",
    "o3": "openai/o3",
    "o3-mini": "openai/o3-mini",
    "o1": "openai/o1",
    "claude-opus-4-7": "anthropic/claude-opus-4.7",
    "claude-opus-4-6": "anthropic/claude-opus-4.6",
    "claude-sonnet-4-6": "anthropic/claude-sonnet-4.6",
    "claude-sonnet-4-5": "anthropic/claude-sonnet-4-5",
    "claude-3.5-sonnet-20241022": "anthropic/claude-3.5-sonnet",
    "gemini-3.5-flash": "google/gemini-3.5-flash",
    "gemini-3.1-pro-preview": "google/gemini-3.1-pro-preview",
    "gemini-2.5-pro": "google/gemini-2.5-pro-preview-06-05",
    "gemini-2.5-flash": "google/gemini-2.5-flash",
    "gemini-2.0-flash": "google/gemini-2.0-flash-001",
    "deepseek-v3": "deepseek/deepseek-chat",
    "deepseek-r1": "deepseek/deepseek-r1",
    "qwen3-235b-a22b": "qwen/qwen3-235b-a22b",
    "qwen3.5-plus": "qwen/qwen3.5-plus",
    "qwen3.5-flash": "qwen/qwen3.5-flash",
    "qwen3.6-plus": "qwen/qwen3.6-plus",
    "qwen3.6-flash": "qwen/qwen3.6-flash",
    "qwen2.5-72b-instruct": "qwen/qwen-2.5-72b-instruct",
    "llama-3.1-405b-instruct": "meta-llama/llama-3.1-405b-instruct",
    "llama-3.3-70b-instruct": "meta-llama/llama-3.3-70b-instruct",
    "llama-4-maverick-17b-128e": "meta-llama/llama-4-maverick",
    "llama-4-scout-17b-16e": "meta-llama/llama-4-scout",
    "phi-4": "microsoft/phi-4",
    "kimi-k2.5": "moonshotai/kimi-k2.5",
    "kimi-k2.6": "moonshotai/kimi-k2.6",
    "grok-3": "x-ai/grok-3",
    "grok-3-mini": "x-ai/grok-3-mini",
    "grok-4-0709": "x-ai/grok-4.3",
    "grok-4-20": "x-ai/grok-4.20",
    "mistral-large-2411": "mistralai/mistral-large",
    "nemotron-3-ultra": "nvidia/nemotron-3-ultra-550b-a55b",
}

# ── build points ────────────────────────────────────────────────────
points = []
slugs_seen = set()

# 1. Models with real ECI scores
for fk, info in families.items():
    slug = ECI_TO_SLUG.get(fk)
    if not slug or slug not in or_lookup:
        continue
    or_info = or_lookup[slug]
    points.append({
        "name": info["name"].split(" (")[0],
        "eci": info["eci"],
        "cost": or_info["cost"],
        "usage": or_info["usage"],
        "open": info["open"],
        "estimated": False,
    })
    slugs_seen.add(slug)

# 2. Models with II but no ECI — extrapolate
for slug, ii_score in II_SCORES.items():
    if slug in slugs_seen or slug not in or_lookup:
        continue
    or_info = or_lookup[slug]
    is_open = II_OPEN.get(slug)
    if is_open is None:
        continue  # skip if we don't know open/closed
    points.append({
        "name": II_NAMES.get(slug, slug.split("/")[-1]),
        "eci": ii_to_eci(ii_score),
        "cost": or_info["cost"],
        "usage": or_info["usage"],
        "open": is_open,
        "estimated": True,
    })
    slugs_seen.add(slug)

# Deduplicate by name, keep highest ECI
seen = {}
for p in points:
    if p["name"] not in seen or p["eci"] > seen[p["name"]]["eci"]:
        seen[p["name"]] = p
points = sorted(seen.values(), key=lambda x: -x["eci"])

n_real = sum(1 for p in points if not p["estimated"])
n_est = sum(1 for p in points if p["estimated"])
print(f"Matched {len(points)} models ({n_real} ECI, {n_est} extrapolated from OpenRouter II)")
for p in points:
    tag = "OPEN" if p["open"] else "CLSD"
    est = " *" if p["estimated"] else "  "
    print(f"  ECI={p['eci']:6.1f}{est}  ${p['cost']:7.2f}/Mt  usage={p['usage']:>7,}  {tag}  {p['name']}")

# ── SVG generation ──────────────────────────────────────────────────
W, H = 1040, 600
ml, mr, mt, mb = 110, 50, 100, 70
pw = W - ml - mr
ph = H - mt - mb

costs = [p["cost"] for p in points]
log_cost_min = math.floor(math.log10(min(costs)) * 2) / 2
log_cost_max = math.ceil(math.log10(max(costs)) * 2) / 2
eci_min = 125
eci_max = 165


def cx(cost):
    lc = math.log10(cost)
    frac = (lc - log_cost_min) / (log_cost_max - log_cost_min)
    return ml + frac * pw


def cy(eci):
    frac = (eci - eci_min) / (eci_max - eci_min)
    return mt + ph - frac * ph


usages = [p["usage"] for p in points]
max_usage = max(usages) if usages else 1


def radius(usage):
    if usage <= 0:
        return 4
    return 4 + 14 * math.sqrt(usage / max_usage)


# Short display names
SHORT = {
    "Claude Opus 4.8": "Opus 4.8",
    "Claude Opus 4.7": "Opus 4.7",
    "Claude Opus 4.6": "Opus 4.6",
    "Claude Sonnet 4.6": "Sonnet 4.6",
    "Gemini 3.5 Flash": "Gem 3.5 Flash",
    "Gemini 3.1 Pro Preview": "Gem 3.1 Pro",
    "Gemini 2.5 Flash": "Gem 2.5 Flash",
    "Llama 3.3-70B": "Llama 3.3",
    "Llama 4 Maverick": "Maverick",
    "Llama 4 Scout": "Scout",
    "Qwen3-235B-A22B": "Qwen3 235B",
    "Qwen 3.6 Plus": "Qwen 3.6+",
    "DeepSeek-V3": "DS-V3",
    "DeepSeek-R1": "DS-R1",
    "Mistral Large 2": "Mistral L2",
    "Qwen2.5-72B": "Qwen2.5",
}

# Custom label nudges: (dx, dy, anchor)
NUDGES = {
    "Opus 4.8":       (6, -8, "start"),
    "Opus 4.7":       (6, 5, "start"),
    "GPT-5.4":        (6, 14, "start"),
    "MiMo V2.5 Pro":  (6, 14, "start"),
    "Opus 4.6":       (6, 14, "start"),
}

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
    </style>
  </defs>

  <rect width="{W}" height="{H}" fill="#1D1D40"/>

  <!-- header -->
  <text x="50" y="36" class="mono cy" font-size="14" letter-spacing="3">~ COST vs CAPABILITY</text>
  <text x="50" y="66" class="t" font-size="30">Smarter models cost more &#8212; but open weights close the gap</text>
  <text x="50" y="88" class="m" font-size="15">Each circle is one model. Area &#8733; requests on OpenRouter (hover for details). X axis is log scale.</text>

  <!-- legend -->
  <g font-size="14">
    <circle cx="600" cy="36" r="6" fill="#E61E25" fill-opacity="0.7"/><text x="612" y="40" class="l">closed</text>
    <circle cx="690" cy="36" r="6" fill="#35E0D8" fill-opacity="0.7"/><text x="702" y="40" class="l">open weights</text>
    <circle cx="815" cy="36" r="6" fill="#9795B5" fill-opacity="0.4" stroke="#9795B5" stroke-width="1" stroke-dasharray="2 2"/><text x="827" y="40" class="l">dashed = extrapolated</text>
  </g>

  <!-- axes -->
  <line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}" stroke="#9795B5" stroke-width="1.2"/>
  <line x1="{ml}" y1="{mt + ph}" x2="{ml + pw}" y2="{mt + ph}" stroke="#9795B5" stroke-width="1.2"/>
  <text x="{ml - 10}" y="{mt - 8}" class="mono m" font-size="15" text-anchor="end">ECI &#8593;</text>
  <text x="{ml + pw + 5}" y="{mt + ph + 22}" class="mono m" font-size="15">&#36;/Mtok &#8594;</text>
'''

# X gridlines (log scale)
x_ticks = [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 30]
x_ticks = [t for t in x_ticks if log_cost_min <= math.log10(t) <= log_cost_max]
for t in x_ticks:
    x = cx(t)
    svg += f'  <line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{mt + ph}" stroke="rgba(151,149,181,0.12)" stroke-width="1"/>\n'
    label = f"&#36;{t:g}"
    svg += f'  <text x="{x:.1f}" y="{mt + ph + 22}" class="mono m" font-size="14" text-anchor="middle">{label}</text>\n'

# Y gridlines
for e in range(130, 165, 5):
    y = cy(e)
    svg += f'  <line x1="{ml}" y1="{y:.1f}" x2="{ml + pw}" y2="{y:.1f}" stroke="rgba(151,149,181,0.10)" stroke-width="1"/>\n'
    svg += f'  <text x="{ml - 10}" y="{y + 5:.1f}" class="mono m" font-size="14" text-anchor="end">{e}</text>\n'

# Draw circles (larger ones first so labels aren't hidden)
points_sorted = sorted(points, key=lambda p: -radius(p["usage"]))
for p in points_sorted:
    x = cx(p["cost"])
    y = cy(p["eci"])
    r = radius(p["usage"])
    color = "#35E0D8" if p["open"] else "#E61E25"
    tag = "open" if p["open"] else "closed"
    src = "extrapolated from OpenRouter II" if p["estimated"] else "Epoch AI ECI"
    tip = f'{p["name"]}  |  ECI {p["eci"]:.1f} ({src})  |  ${p["cost"]:.2f}/Mtok  |  {p["usage"]:,} reqs  |  {tag}'
    dash = ' stroke-dasharray="3 2"' if p["estimated"] else ""
    svg += f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}" fill-opacity="0.55" stroke="{color}" stroke-width="1.2"{dash} cursor="pointer"><title>{tip}</title></circle>\n'

# Draw labels for all points
for p in points:
    x = cx(p["cost"])
    y = cy(p["eci"])
    r = radius(p["usage"])
    sn = SHORT.get(p["name"], p["name"])
    color_class = "cy" if p["open"] else "red"
    nudge = NUDGES.get(sn)
    if nudge:
        ox, oy, anchor = nudge
    else:
        ox, oy, anchor = r + 4, -4, "start"
        if p["cost"] > 8:
            ox, anchor = -(r + 4), "end"
    svg += f'  <text x="{x + ox:.1f}" y="{y + oy:.1f}" class="mono {color_class}" font-size="12" text-anchor="{anchor}">{sn}</text>\n'

# Source
svg += f'  <text x="50" y="{H - 24}" class="mono m" font-size="12">Sources: Epoch AI Capabilities Index (epoch.ai/data), OpenRouter API + Intelligence Index (openrouter.ai). June 2026.</text>\n'
svg += f'  <text x="50" y="{H - 8}" class="mono m" font-size="12">Dashed circles: ECI extrapolated from OpenRouter Intelligence Index via linear fit (R&#178; = 0.68, n = 12).</text>\n'

svg += "</svg>\n"

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tradeoff-scatter.svg")
with open(out_path, "w") as f:
    f.write(svg)

print(f"Wrote {out_path}")
