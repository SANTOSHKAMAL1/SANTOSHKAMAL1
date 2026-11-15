#!/usr/bin/env python3
"""Generate assets/metrics.svg, a GitHub metrics card built from live API data.

Run by .github/workflows/metrics.yml. Needs GITHUB_TOKEN in the environment,
or pass --data FILE with a saved GraphQL `user` object for local previews.
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape

LOGIN = os.environ.get("METRICS_USER", "SANTOSHKAMAL1")
OUT = os.environ.get("METRICS_OUT", "assets/metrics.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    createdAt
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        forkCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date weekday } }
      }
    }
  }
}
"""

BG, PANEL, BORDER = "#0d1117", "#161b22", "#30363d"
TEXT, MUTED, ACCENT = "#e6edf3", "#8b949e", "#7aa2f7"
LEVELS = ["#1b222c", "#0e4429", "#006d32", "#26a641", "#39d353"]
FONT = "'Segoe UI',Helvetica,Arial,sans-serif"


def fetch():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-metrics"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        body = json.load(res)
    if body.get("errors") or not body.get("data", {}).get("user"):
        sys.exit(f"GitHub API error: {body.get('errors')}")
    return body["data"]["user"]


def shade(hex_color, factor):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (int(r * factor), int(g * factor), int(b * factor))


def text(x, y, s, size=13, fill=TEXT, weight=400, anchor="start"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(s))}</text>')


def render(user):
    repos = user["repositories"]
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]

    stars = sum(r["stargazerCount"] for r in repos["nodes"])
    langs = {}
    for r in repos["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]
            cur = langs.setdefault(n["name"], [0, n["color"] or "#8b949e"])
            cur[0] += e["size"]
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:6]
    lang_total = sum(v[0] for _, v in top) or 1

    best = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] else 0
        best = max(best, run)
    active = sum(1 for d in days if d["contributionCount"])
    weekday = [0] * 7
    for d in days:
        weekday[d["weekday"]] += d["contributionCount"]
    peak = max((d["contributionCount"] for d in days), default=0) or 1

    W, H = 840, 470
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
         f'font-family="{FONT}" role="img" aria-label="GitHub metrics for {escape(LOGIN)}">',
         f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="{BG}" stroke="{BORDER}"/>']

    joined = user["createdAt"][:4]
    o.append(text(28, 42, user.get("name") or LOGIN, 22, TEXT, 700))
    o.append(text(28, 64, f"@{LOGIN} · on GitHub since {joined}", 13, MUTED))
    o.append(text(W - 28, 42, "GitHub metrics", 13, ACCENT, 600, "end"))

    tiles = [
        ("Public repos", repos["totalCount"]),
        ("Contributions (1 yr)", cal["totalContributions"]),
        ("Active days (1 yr)", active),
        ("Best streak", f"{best} days"),
        ("Stars", stars),
        ("Followers", user["followers"]["totalCount"]),
    ]
    tw, gap, x0, y0 = 122, 10.4, 28, 84
    for i, (label, value) in enumerate(tiles):
        x = x0 + i * (tw + gap)
        o.append(f'<rect x="{x:.1f}" y="{y0}" width="{tw}" height="62" rx="10" fill="{PANEL}" stroke="{BORDER}"/>')
        o.append(text(x + 12, y0 + 28, value, 20, TEXT, 700))
        o.append(text(x + 12, y0 + 48, label, 11, MUTED))

    # Languages
    o.append(text(28, 182, "Most used languages", 13, ACCENT, 600))
    bx, by, bw = 28, 194, 360
    o.append(f'<clipPath id="lb"><rect x="{bx}" y="{by}" width="{bw}" height="10" rx="5"/></clipPath>')
    o.append('<g clip-path="url(#lb)">')
    x = bx
    for name, (size, color) in top:
        w = bw * size / lang_total
        o.append(f'<rect x="{x:.1f}" y="{by}" width="{w + 0.5:.1f}" height="10" fill="{color}"/>')
        x += w
    o.append('</g>')
    for i, (name, (size, color)) in enumerate(top):
        lx, ly = bx + (i % 2) * 180, by + 32 + (i // 2) * 22
        o.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{color}"/>')
        o.append(text(lx + 16, ly, name, 12, TEXT))
        o.append(text(lx + 160, ly, f"{100 * size / lang_total:.1f}%", 12, MUTED, 400, "end"))

    # Contributions per weekday
    o.append(text(28, 318, "Contributions per weekday", 13, ACCENT, 600))
    wmax = max(weekday) or 1
    base, maxh = 420, 62
    for i, (label, count) in enumerate(zip("Sun Mon Tue Wed Thu Fri Sat".split(), weekday)):
        x = 28 + i * 52
        h = max(2, maxh * count / wmax)
        o.append(f'<rect x="{x}" y="{base - h:.1f}" width="34" height="{h:.1f}" rx="4" fill="{LEVELS[3]}"/>')
        o.append(text(x + 17, base - h - 5, count, 10, MUTED, 400, "middle"))
        o.append(text(x + 17, base + 16, label, 11, MUTED, 400, "middle"))

    # Isometric contribution calendar
    o.append(text(430, 182, "Contributions calendar", 13, ACCENT, 600))
    a, b, ox, oy = 6.1, 3.05, 480, 232

    def P(x, y, z):
        return f"{ox + (x - y) * a:.1f},{oy + (x + y) * b - z:.1f}"

    for wi, week in enumerate(cal["weeks"]):
        for d in week["contributionDays"]:
            c, di = d["contributionCount"], d["weekday"]
            level = 0 if c == 0 else min(4, 1 + int(3 * c / peak))
            color = LEVELS[level]
            h = 2 + (28 * c / peak if c else 0)
            x1, y1, x2, y2 = wi + .06, di + .06, wi + .94, di + .94
            o.append(f'<polygon fill="{shade(color, .62)}" points="{P(x1, y2, h)} {P(x2, y2, h)} {P(x2, y2, 0)} {P(x1, y2, 0)}"/>')
            o.append(f'<polygon fill="{shade(color, .42)}" points="{P(x2, y1, h)} {P(x2, y2, h)} {P(x2, y2, 0)} {P(x2, y1, 0)}"/>')
            o.append(f'<polygon fill="{color}" points="{P(x1, y1, h)} {P(x2, y1, h)} {P(x2, y2, h)} {P(x1, y2, h)}"/>')

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y")
    o.append(text(W - 28, H - 18, f"Updated {stamp} · generated by GitHub Actions", 11, MUTED, 400, "end"))
    o.append("</svg>")
    return "\n".join(o) + "\n"


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--data":
        with open(sys.argv[2]) as f:
            user = json.load(f)
    else:
        user = fetch()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as f:
        f.write(render(user))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
