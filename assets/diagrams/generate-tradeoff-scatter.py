#!/usr/bin/env python3
"""Generate cost-vs-capability scatter from Epoch AI ECI + OpenRouter pricing.

Each circle = one model. Color = open (cyan) vs closed (red).
Circle area scales with OpenRouter usage (status_heuristics.success).
X = input cost per million tokens (log scale). Y = ECI score.

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

# ── download OpenRouter catalog ────────────────────────────────────
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

# ── manual mapping: ECI family key → OpenRouter slug ────────────────
MAPPING = {
    # OpenAI
    "gpt-5.5-pro-pre-release": "openai/gpt-5.5-pro",
    "gpt-5.5-pre-release": "openai/gpt-5.5",
    "gpt-5.4-2026-03-05": "openai/gpt-5.4",
    "gpt-5.4-pro-2026-03-05": "openai/gpt-5.4-pro",
    "gpt-5.4-mini-2026-03-17": "openai/gpt-5.4-mini",
    "gpt-5.4-nano-2026-03-17": "openai/gpt-5.4-nano",
    "gpt-5.3-codex": "openai/codex-mini-latest",
    "gpt-5.2": "openai/gpt-5.2",
    "gpt-5": "openai/gpt-5",
    "o3": "openai/o3",
    "o3-pro": "openai/o3-pro",
    "o3-mini": "openai/o3-mini",
    "o1": "openai/o1",
    # Anthropic
    "claude-opus-4-7": "anthropic/claude-opus-4.7",
    "claude-opus-4-6": "anthropic/claude-opus-4.6",
    "claude-sonnet-4-6": "anthropic/claude-sonnet-4.6",
    "claude-sonnet-4-5": "anthropic/claude-sonnet-4-5",
    "claude-3.5-sonnet-20241022": "anthropic/claude-3.5-sonnet",
    # Google
    "gemini-3.5-flash": "google/gemini-3.5-flash",
    "gemini-3.1-pro-preview": "google/gemini-3.1-pro-preview",
    "gemini-3-pro-preview": "google/gemini-3-pro-preview",
    "gemini-2.5-pro": "google/gemini-2.5-pro-preview-06-05",
    "gemini-2.5-flash": "google/gemini-2.5-flash",
    "gemini-2.0-flash": "google/gemini-2.0-flash-001",
    # DeepSeek (open)
    "deepseek-v3": "deepseek/deepseek-chat",
    "deepseek-r1": "deepseek/deepseek-r1",
    # Qwen
    "qwen3-235b-a22b": "qwen/qwen3-235b-a22b",
    "qwen3.5-plus": "qwen/qwen3.5-plus",
    "qwen3.5-flash": "qwen/qwen3.5-flash",
    "qwen3.6-max-preview": "qwen/qwen3.6-max",
    "qwen3.6-plus": "qwen/qwen3.6-plus",
    "qwen3.6-flash": "qwen/qwen3.6-flash",
    "qwen2.5-72b-instruct": "qwen/qwen-2.5-72b-instruct",
    # Meta (open)
    "llama-3.1-405b-instruct": "meta-llama/llama-3.1-405b-instruct",
    "llama-3.3-70b-instruct": "meta-llama/llama-3.3-70b-instruct",
    "llama-4-maverick-17b-128e": "meta-llama/llama-4-maverick",
    "llama-4-scout-17b-16e": "meta-llama/llama-4-scout",
    # Others
    "phi-4": "microsoft/phi-4",
    "kimi-k2.5": "moonshotai/kimi-k2.5",
    "kimi-k2.6": "moonshotai/kimi-k2.6",
    "grok-3": "x-ai/grok-3",
    "grok-3-mini": "x-ai/grok-3-mini",
    "mistral-large-2411": "mistralai/mistral-large",
    "nemotron-3-ultra": "nvidia/nemotron-3-ultra-550b-a55b",
    # Grok
    "grok-4-0709": "x-ai/grok-4.3",
    "grok-4-20": "x-ai/grok-4.20",
    "grok-4-fast": "x-ai/grok-4-fast",
    # GPT-5 mini, GPT-4.1 series
    "gpt-5-mini-2025-08-07": "openai/gpt-5-mini",
    "gpt-4.1-2025-04-14": "openai/gpt-4.1-mini",
    "gpt-4.1-mini-2025-04-14": "openai/gpt-4.1-mini",
    "gpt-4.1-nano-2025-04-14": "openai/gpt-4.1-nano",
}

# ── match ───────────────────────────────────────────────────────────
points = []
for fk, info in families.items():
    slug = MAPPING.get(fk)
    if not slug or slug not in or_lookup:
        continue
    or_info = or_lookup[slug]
    points.append({
        "name": info["name"].split(" (")[0],
        "eci": info["eci"],
        "cost": or_info["cost"],
        "usage": or_info["usage"],
        "open": info["open"],
    })

# Deduplicate by name, keep highest ECI
seen = {}
for p in points:
    if p["name"] not in seen or p["eci"] > seen[p["name"]]["eci"]:
        seen[p["name"]] = p
points = sorted(seen.values(), key=lambda x: -x["eci"])

print(f"Matched {len(points)} models")

# ── SVG generation ──────────────────────────────────────────────────
W, H = 1040, 600
ml, mr, mt, mb = 110, 50, 120, 90
pw = W - ml - mr
ph = H - mt - mb

# X axis: log10(cost), Y axis: ECI
costs = [p["cost"] for p in points]
ecis = [p["eci"] for p in points]

log_cost_min = math.floor(math.log10(min(costs)) * 2) / 2  # round down to 0.5
log_cost_max = math.ceil(math.log10(max(costs)) * 2) / 2   # round up to 0.5
eci_min = 125
eci_max = 165

def cx(cost):
    lc = math.log10(cost)
    frac = (lc - log_cost_min) / (log_cost_max - log_cost_min)
    return ml + frac * pw

def cy(eci):
    frac = (eci - eci_min) / (eci_max - eci_min)
    return mt + ph - frac * ph

# Circle radius from usage (sqrt scale, clamped)
usages = [p["usage"] for p in points]
max_usage = max(usages) if usages else 1

def radius(usage):
    if usage <= 0:
        return 4
    return 4 + 14 * math.sqrt(usage / max_usage)

# Labels for selected models
label_set = {
    "GPT-5.5 Pro", "GPT-5.5", "GPT-5.4", "GPT-5.4 mini", "GPT-5.4 nano",
    "Claude Opus 4.7", "Claude Opus 4.6", "Claude Sonnet 4.6",
    "Gemini 3.5 Flash", "Gemini 2.5 Flash",
    "DeepSeek-R1", "DeepSeek-V3",
    "Kimi K2.6", "Kimi K2.5",
    "Qwen3-235B-A22B", "Qwen 3.6 Plus",
    "Llama 4 Maverick", "Llama 4 Scout", "Llama 3.3-70B",
    "Phi-4", "Grok 4", "GPT-5 mini", "GPT-4.1 nano",
}

# Short display names
def short_name(name):
    replacements = {
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
    return replacements.get(name, name)

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
  <text x="50" y="42" class="mono cy" font-size="14" letter-spacing="3">~ COST vs CAPABILITY</text>
  <text x="50" y="78" class="t" font-size="30">Smarter models cost more &#8212; but open weights close the gap</text>
  <text x="50" y="104" class="m" font-size="15">Each circle is one model. Area &#8733; requests on OpenRouter (hover for details). X axis is log scale.</text>

  <!-- legend -->
  <g font-size="14">
    <circle cx="640" cy="42" r="6" fill="#E61E25" fill-opacity="0.7"/><text x="652" y="46" class="l">closed</text>
    <circle cx="730" cy="42" r="6" fill="#35E0D8" fill-opacity="0.7"/><text x="742" y="46" class="l">open weights</text>
  </g>

  <!-- axes -->
  <line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}" stroke="#9795B5" stroke-width="1.2"/>
  <line x1="{ml}" y1="{mt + ph}" x2="{ml + pw}" y2="{mt + ph}" stroke="#9795B5" stroke-width="1.2"/>
  <text x="{ml - 10}" y="{mt - 8}" class="mono m" font-size="13" text-anchor="end">ECI &#8593;</text>
  <text x="{ml + pw + 5}" y="{mt + ph + 20}" class="mono m" font-size="13">&#36;/Mtok &#8594;</text>
'''

# X gridlines (log scale)
x_ticks = [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 30]
x_ticks = [t for t in x_ticks if log_cost_min <= math.log10(t) <= log_cost_max]
for t in x_ticks:
    x = cx(t)
    svg += f'  <line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{mt + ph}" stroke="rgba(151,149,181,0.12)" stroke-width="1"/>\n'
    label = f"&#36;{t:g}"
    svg += f'  <text x="{x:.1f}" y="{mt + ph + 20}" class="mono m" font-size="12" text-anchor="middle">{label}</text>\n'

# Y gridlines
for e in range(130, 165, 5):
    y = cy(e)
    svg += f'  <line x1="{ml}" y1="{y:.1f}" x2="{ml + pw}" y2="{y:.1f}" stroke="rgba(151,149,181,0.10)" stroke-width="1"/>\n'
    svg += f'  <text x="{ml - 10}" y="{y + 5:.1f}" class="mono m" font-size="12" text-anchor="end">{e}</text>\n'

# Draw circles (larger ones first so labels aren't hidden)
points_sorted = sorted(points, key=lambda p: -radius(p["usage"]))
for p in points_sorted:
    x = cx(p["cost"])
    y = cy(p["eci"])
    r = radius(p["usage"])
    color = "#35E0D8" if p["open"] else "#E61E25"
    tag = "open" if p["open"] else "closed"
    tip = f'{p["name"]}  |  ECI {p["eci"]:.1f}  |  ${p["cost"]:.2f}/Mtok  |  {p["usage"]:,} reqs  |  {tag}'
    svg += f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}" fill-opacity="0.55" stroke="{color}" stroke-width="1"><title>{tip}</title></circle>\n'

# Draw labels
for p in points:
    if p["name"] not in label_set:
        continue
    x = cx(p["cost"])
    y = cy(p["eci"])
    r = radius(p["usage"])
    sn = short_name(p["name"])
    color_class = "cy" if p["open"] else "red"
    # Nudge labels to avoid overlap
    ox, oy = r + 4, -4
    anchor = "start"
    # Push left for expensive models near right edge
    if p["cost"] > 15:
        ox = -(r + 4)
        anchor = "end"
    svg += f'  <text x="{x + ox:.1f}" y="{y + oy:.1f}" class="mono {color_class}" font-size="11" text-anchor="{anchor}">{sn}</text>\n'

# Source
svg += f'  <text x="50" y="{H - 18}" class="mono m" font-size="11">Sources: Epoch AI Capabilities Index (epoch.ai/data), OpenRouter API (openrouter.ai). June 2026.</text>\n'

svg += "</svg>\n"

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tradeoff-scatter.svg")
with open(out_path, "w") as f:
    f.write(svg)

print(f"Wrote {out_path}")
