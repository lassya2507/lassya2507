#!/usr/bin/env python3
"""Generate a cute, self-animating SVG aquarium from public GitHub repos.

Each repo becomes a little jelly creature. Stars influence size, recent pushes
make a repo glow, and a persistent phase value makes the scene shift every day.
The script uses only Python's standard library and GitHub's public API.
"""

from __future__ import annotations

import html
import json
import math
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OWNER = "lassya2507"
PROFILE_REPO = "lassya2507"
MAX_REPOS = 8
W, H = 760, 470

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "tidepool" / "state.json"
OUT_PATH = ROOT / "dist" / "tidepool.svg"

SLOTS = [
    (150, 150), (360, 130), (590, 155), (675, 285),
    (520, 350), (310, 360), (120, 330), (245, 245),
]
HOME = (405, 255)

PALETTES = [
    ("#ff8fc7", "#ffd2e9", "#b94d89", "#fff1f8"),
    ("#c9a7ff", "#eadcff", "#7650b7", "#f6efff"),
    ("#91d7ff", "#d9f3ff", "#3d8fb9", "#eefaff"),
    ("#ffb7a7", "#ffe1da", "#bd6857", "#fff3ef"),
    ("#9ee7d2", "#dff9f1", "#4a9f88", "#effcf8"),
]

FALLBACK = [
    {"name": "ai-project", "stars": 0, "days": 5, "language": "Python"},
    {"name": "ml-playground", "stars": 0, "days": 16, "language": "Python"},
    {"name": "secure-ai", "stars": 0, "days": 40, "language": "Python"},
]


def api_repos():
    url = f"https://api.github.com/users/{OWNER}/repos?per_page=100&type=owner&sort=pushed"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "prarthana-repo-aquarium"}
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as r:
            data = json.load(r)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return FALLBACK

    now = datetime.now(timezone.utc)
    repos = []
    for repo in data:
        if repo.get("fork") or repo.get("archived") or repo.get("name") == PROFILE_REPO:
            continue
        try:
            pushed = datetime.strptime(repo.get("pushed_at", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            days = max(0, (now - pushed).days)
        except ValueError:
            days = 999
        repos.append(
            {
                "name": repo["name"],
                "stars": int(repo.get("stargazers_count", 0)),
                "days": days,
                "language": repo.get("language") or "Code",
            }
        )

    if not repos:
        return FALLBACK

    # Favor starred repos, but keep recently active work visible too.
    repos.sort(key=lambda r: (r["stars"] * 25 + max(0, 45 - r["days"])), reverse=True)
    return repos[:MAX_REPOS]


def load_phase():
    try:
        return float(json.loads(STATE_PATH.read_text()).get("phase", 0.0))
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return 0.0


def save_phase(phase):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"phase": round(phase, 4)}, indent=2) + "\n")


def esc(value):
    return html.escape(str(value), quote=True)


def jelly(cx, cy, radius, colors, index, active):
    body, light, dark, text = colors
    bob = 4.8 + (index % 4) * 0.7
    sway = 5.5 + (index % 3) * 0.8
    glow = ""
    if active:
        glow = f'''<circle cx="0" cy="0" r="{radius*1.3:.1f}" fill="{body}" opacity="0.12">
          <animate attributeName="r" values="{radius*1.1:.1f};{radius*1.55:.1f};{radius*1.1:.1f}" dur="3.2s" repeatCount="indefinite"/>
          <animate attributeName="opacity" values="0.16;0.03;0.16" dur="3.2s" repeatCount="indefinite"/>
        </circle>'''

    tentacles = "".join(
        f'<path d="M{x:.1f},{radius*0.35:.1f} q{-5 if k%2 else 5:.1f},{radius*0.45:.1f} 0,{radius*0.9:.1f}" stroke="{dark}" stroke-width="3" fill="none" stroke-linecap="round"/>'
        for k, x in enumerate((-radius*0.55, -radius*0.18, radius*0.18, radius*0.55))
    )

    return f'''<g transform="translate({cx},{cy})">
      <g>
        <animateTransform attributeName="transform" type="translate" values="0,0; 7,-9; 0,0" dur="{bob:.1f}s" repeatCount="indefinite"/>
        {glow}
        <g>
          <animateTransform attributeName="transform" type="rotate" values="-3 0 0;3 0 0;-3 0 0" dur="{sway:.1f}s" repeatCount="indefinite"/>
          {tentacles}
        </g>
        <ellipse cx="0" cy="0" rx="{radius:.1f}" ry="{radius*0.78:.1f}" fill="{body}"/>
        <ellipse cx="0" cy="{-radius*0.13:.1f}" rx="{radius*.95:.1f}" ry="{radius*0.5:.1f}" fill="{light}" opacity="0.75"/>
        <circle cx="{-radius*.28:.1f}" cy="{-radius*.05:.1f}" r="3.2" fill="#4a3150"/>
        <circle cx="{radius*.28:.1f}" cy="{-radius*.05:.1f}" r="3.2" fill="#4a3150"/>
        <circle cx="{-radius*.25:.1f}" cy="{-radius*.09:.1f}" r="1.1" fill="white"/>
        <circle cx="{radius*.31:.1f}" cy="{-radius*.09:.1f}" r="1.1" fill="white"/>
        <path d="M-5,{radius*.16:.1f} Q0,{radius*.21:.1f} 5,{radius*.16:.1f}" stroke="#784f70" stroke-width="1.8" fill="none" stroke-linecap="round"/>
      </g>
    </g>''', text


def render(repos, phase):
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img">
    <title>Prarthana's living repo aquarium</title>
    <desc>Public repositories appear as animated jelly creatures. Size reflects stars and glow reflects recent activity.</desc>
    <defs>
      <linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#24152d"/>
        <stop offset="45%" stop-color="#1b2038"/>
        <stop offset="100%" stop-color="#101d2d"/>
      </linearGradient>
      <radialGradient id="pearl">
        <stop offset="0%" stop-color="#fff7fc"/>
        <stop offset="55%" stop-color="#f6b8db"/>
        <stop offset="100%" stop-color="#b971b0"/>
      </radialGradient>
    </defs>
    <rect width="760" height="470" rx="22" fill="url(#water)"/>
    <circle cx="80" cy="70" r="45" fill="#ff8fc7" opacity="0.05"/>
    <circle cx="700" cy="110" r="70" fill="#c9a7ff" opacity="0.04"/>
    ''']

    for i, bx in enumerate((70, 180, 280, 515, 630, 715)):
        delay = (i % 4) * 0.7
        parts.append(f'''<circle cx="{bx}" cy="430" r="{2 + i%3}" fill="#fff" opacity="0.22">
          <animate attributeName="cy" values="430;30" dur="{8+i}s" begin="-{delay}s" repeatCount="indefinite"/>
          <animate attributeName="opacity" values="0;0.3;0" dur="{8+i}s" begin="-{delay}s" repeatCount="indefinite"/>
        </circle>''')

    # Home pearl
    hx, hy = HOME
    parts.append(f'''<g transform="translate({hx},{hy})">
      <circle r="35" fill="#f8b7da" opacity="0.10">
        <animate attributeName="r" values="32;42;32" dur="4s" repeatCount="indefinite"/>
      </circle>
      <circle r="25" fill="url(#pearl)"/>
      <text x="0" y="4" text-anchor="middle" font-size="18">🎀</text>
      <text x="0" y="48" text-anchor="middle" fill="#ffdff0" font-family="system-ui,sans-serif" font-size="13" font-weight="700">{PROFILE_REPO}</text>
      <text x="0" y="64" text-anchor="middle" fill="#cfa7c5" font-family="system-ui,sans-serif" font-size="10">home · profile reef</text>
    </g>''')

    wave = math.sin(phase)
    for i, repo in enumerate(repos):
        cx, cy = SLOTS[i]
        colors = PALETTES[i % len(PALETTES)]
        star_bonus = min(16, math.sqrt(max(0, repo["stars"])) * 7)
        activity_bonus = max(0, 9 - min(9, repo["days"] / 4))
        pulse = 1 + 0.08 * math.sin(phase + i * 0.8)
        radius = (22 + star_bonus + activity_bonus) * pulse
        active = repo["days"] <= 14
        art, text_color = jelly(cx, cy, radius, colors, i, active)
        parts.append(art)
        y = cy + radius + 29
        name = esc(repo["name"][:28] + ("…" if len(repo["name"]) > 28 else ""))
        meta = f'★ {repo["stars"]} · {esc(repo["language"])}' if repo["stars"] else f'{esc(repo["language"])} · {repo["days"]}d ago'
        parts.append(f'''<text x="{cx}" y="{y:.1f}" text-anchor="middle" fill="{text_color}" font-family="system-ui,sans-serif" font-size="12" font-weight="650">{name}</text>
        <text x="{cx}" y="{y+15:.1f}" text-anchor="middle" fill="#ba9db7" font-family="system-ui,sans-serif" font-size="10">{meta}</text>''')

    parts.append('''<g transform="translate(24,26)">
      <rect width="252" height="63" rx="14" fill="#0d1020" opacity="0.72"/>
      <text x="15" y="23" fill="#ffd9ec" font-family="system-ui,sans-serif" font-size="12" font-weight="700">🫧 Repo Aquarium</text>
      <text x="15" y="42" fill="#cbb1c8" font-family="system-ui,sans-serif" font-size="10">bigger = more stars · glow = recently active</text>
      <text x="15" y="56" fill="#a88da5" font-family="system-ui,sans-serif" font-size="9">re-generated daily from live GitHub data ✨</text>
    </g>''')
    parts.append('</svg>')
    return "".join(parts)


def main():
    repos = api_repos()
    phase = (load_phase() + 0.42) % (math.tau)
    save_phase(phase)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render(repos, phase))
    print(f"wrote {OUT_PATH} with {len(repos)} repos")


if __name__ == "__main__":
    main()
