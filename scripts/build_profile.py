"""Render the neofetch-style profile card (dark_mode.svg / light_mode.svg).

ASCII art comes from art.txt, the info column from INFO below, and the
GitHub stats from the GraphQL API (token in GITHUB_TOKEN or GH_TOKEN).
"""

import datetime as dt
import json
import os
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

LOGIN = "Tomas-Polanek"
HEADER = "tomas@polanek"
WIDTH = 60  # characters in the info column

# (key, value) rows; None is an empty spacer row, a str is a section header.
INFO = [
    ("OS", "Windows 11, Debian 13 (homelab)"),
    ("Host", "Prague, CZ"),
    ("Kernel", "Software Development student"),
    ("IDE", "VS Code"),
    None,
    ("Languages.Programming", "TypeScript, Python, PHP, JS"),
    ("Languages.Web", "HTML, CSS, Tailwind"),
    ("Frameworks", "React, Next.js, Express, FastAPI"),
    None,
    ("Homelab.Hardware", "Raspberry Pi 5, 8 GB, 1 TB NVMe"),
    ("Homelab.Services", "AdGuard, Jellyfin, Tailscale"),
    ("Homelab.Ops", "Docker, Uptime Kuma, SSH only"),
    "Contact",
    ("Email", "tomaspolanek1@gmail.com"),
    ("Web", "tomaspolanek.dev"),
    ("LinkedIn", "tomas-polanek"),
    "GitHub Stats",
]

THEMES = {
    "dark": {"bg": "#161b22", "fg": "#c9d1d9", "key": "#ffa657", "value": "#a5d6ff", "dots": "#616e7f"},
    "light": {"bg": "#f6f8fa", "fg": "#24292f", "key": "#953800", "value": "#0a3069", "dots": "#c2cfde"},
}

FONT_SIZE = 16
LINE_H = 20
CHAR_W = 9.65  # >= 0.6em, the widest common 16px monospace cell; only sizes the canvas
GAP = 4  # spaces between the art and the info column
PAD = 20

ROOT = Path(__file__).resolve().parent.parent


def graphql(query, variables):
    token = os.environ.get("GITHUB_TOKEN") or os.environ["GH_TOKEN"]
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": LOGIN},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch_stats():
    data = graphql(
        """
        query($login: String!) {
          user(login: $login) {
            createdAt
            followers { totalCount }
            repositories(ownerAffiliations: OWNER, privacy: PUBLIC, first: 100) {
              totalCount
              nodes { stargazerCount }
            }
            repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) { totalCount }
          }
        }
        """,
        {"login": LOGIN},
    )["user"]

    created = dt.datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    commits = 0
    for year in range(created.year, now.year + 1):
        start = max(created, dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc))
        end = min(now, dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc))
        cc = graphql(
            """
            query($login: String!, $from: DateTime!, $to: DateTime!) {
              user(login: $login) {
                contributionsCollection(from: $from, to: $to) {
                  totalCommitContributions
                  restrictedContributionsCount
                }
              }
            }
            """,
            {"login": LOGIN, "from": start.isoformat(), "to": end.isoformat()},
        )["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"] + cc["restrictedContributionsCount"]

    return {
        "repos": data["repositories"]["totalCount"],
        "contributed": data["repositoriesContributedTo"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in data["repositories"]["nodes"]),
        "commits": commits,
        "followers": data["followers"]["totalCount"],
    }


# A rendered line is a list of (css class or None, text) segments.
def kv(key, value, width=WIDTH):
    dots = width - len(key) - len(value) - 5  # ". " + ":" + " " + dots + " "
    return [(None, ". "), ("key", key), (None, ":"), ("dots", " " + "." * max(dots, 1) + " "), ("value", value)]


def section(title, width=WIDTH):
    head = f"- {title} "
    return [(None, head + "-" * (width - len(head) - 4) + "-.--")]


def stat_pair(k1, v1, k2, v2, width=WIDTH):
    left = kv(k1, v1, width // 2)
    right = kv(k2, v2, width - width // 2 - 1)  # " | " is one char wider than ". "
    right[0] = (None, " | ")
    return left + right


def info_lines(stats):
    lines = [[("value", HEADER), (None, " " + "-" * (WIDTH - len(HEADER) - 5) + "-.--")]]
    for row in INFO:
        if row is None:
            lines.append([(None, ".")])
        elif isinstance(row, str):
            lines.append([(None, "")])
            lines.append(section(row))
        else:
            lines.append(kv(*row))
    lines.append(stat_pair("Repos", f"{stats['repos']} {{Contributed: {stats['contributed']}}}", "Stars", str(stats["stars"])))
    lines.append(stat_pair("Commits", str(stats["commits"]), "Followers", str(stats["followers"])))
    return lines


def render(theme, art, lines):
    """Art and info share one <text> row each, so the columns line up in any monospace font."""
    c = THEMES[theme]
    art_w = max(len(a) for a in art) + GAP
    rows = max(len(art), len(lines))
    art = [""] * ((rows - len(art)) // 2) + art
    width = round(PAD * 2 + (art_w + WIDTH) * CHAR_W)
    height = PAD * 2 + rows * LINE_H

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" '
        f'font-family="ConsolasFallback,Consolas,ui-monospace,SFMono-Regular,Menlo,monospace" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-size="{FONT_SIZE}px">',
        "<style>",
        f".key{{fill:{c['key']}}} .value{{fill:{c['value']}}} .dots{{fill:{c['dots']}}} text,tspan{{white-space:pre}}",
        "</style>",
        f'<rect width="{width}" height="{height}" fill="{c["bg"]}" rx="15"/>',
        f'<text x="{PAD}" y="{PAD + LINE_H}" fill="{c["fg"]}">',
    ]
    for i in range(rows):
        art_part = escape((art[i] if i < len(art) else "").ljust(art_w))
        segs = lines[i] if i < len(lines) else []
        info_part = "".join(f'<tspan class="{cls}">{escape(t)}</tspan>' if cls else escape(t) for cls, t in segs)
        out.append(f'<tspan x="{PAD}" y="{PAD + LINE_H * (i + 1)}">{art_part}{info_part}</tspan>')
    out.append("</text>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    art = (ROOT / "art.txt").read_text(encoding="utf-8").rstrip("\n").split("\n")
    lines = info_lines(fetch_stats())
    for theme in THEMES:
        (ROOT / f"{theme}_mode.svg").write_text(render(theme, art, lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
