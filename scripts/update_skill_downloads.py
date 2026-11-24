"""Refresh the static AI Skills page with one complete GitHub release snapshot."""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


def pages(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ondatrace-skill-downloads"}
    if token := os.getenv("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"

    page = 1
    while True:
        request = Request(f"{url}?per_page=100&page={page}", headers=headers)
        with urlopen(request, timeout=30) as response:
            items = json.load(response)
        if not isinstance(items, list):
            raise ValueError(f"Expected a GitHub collection at {url}")
        yield from items
        if len(items) < 100:
            return
        page += 1


def download_count(repository):
    base = f"https://api.github.com/repos/jsconu/{repository}/releases"
    total = 0
    matched = False
    for release in pages(base):
        if release["draft"]:
            continue
        for asset in pages(f"{base}/{release['id']}/assets"):
            if asset["state"] == "uploaded" and asset["name"].endswith((".zip", ".md")):
                total += asset["download_count"]
                matched = True
    if not matched:
        raise ValueError(f"No published skill assets found in {repository}")
    return total


def replace_element(html, pattern, replacement):
    html, matches = re.subn(pattern, replacement, html)
    if matches != 1:
        raise ValueError(f"Expected one dashboard element matching {pattern}")
    return html


def main():
    path = Path(__file__).resolve().parents[1] / "ai-skills/index.html"
    html = path.read_text()
    for element, repo in (("pmo", "pmo-skills"), ("coach", "personal-career-coach")):
        count = download_count(repo)
        tag = f'span id="{element}-downloads"'
        html = replace_element(html, f'<{tag}>[^<]*</span>', f'<{tag}>{count:,}</span>')
        print(f"{repo}: {count}")
    now = datetime.now(ZoneInfo("America/Denver"))
    display = now.strftime("%b %d, %Y at %I:%M %p %Z").replace(" 0", " ")
    html = replace_element(html, r'<time id="downloads-updated" datetime="[^"]*">[^<]*</time>',
                           f'<time id="downloads-updated" datetime="{now.isoformat(timespec="minutes")}">{display}</time>')
    path.write_text(html)


if __name__ == "__main__":
    main()
