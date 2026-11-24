"""Refresh the static AI Skills page with one complete snapshot of GitHub downloads and configured Agensi uses."""

import json
import os
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


# Map "pmo" and "coach" to the confirmed slugs of their approved Agensi listings.
AGENSI_LISTINGS = {}


class ListingText(HTMLParser):
    """Read visible text in Agensi's server-rendered listing, excluding scripts."""
    def __init__(self):
        super().__init__()
        self.text = []
        self.hidden = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = False

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.text.append(data.strip())


def agensi_uses(slug):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("Invalid Agensi listing slug")
    url = f"https://www.agensi.io/skills/{slug}"
    request = Request(url, headers={"User-Agent": "Ondatrace public skill statistics"})
    with urlopen(request, timeout=30) as response:
        if response.geturl().rstrip("/") != url:
            raise ValueError(f"Agensi redirected away from {slug}")
        parser = ListingText()
        parser.feed(response.read().decode("utf-8"))
        parser.close()
    matches = re.findall(r"(?:^| )(\d{1,3}(?:,\d{3})+|\d+) uses? Times used to date\b",
                         " ".join(parser.text), re.IGNORECASE)
    if len(matches) != 1:
        raise ValueError(f"Could not verify an exact Agensi use count for {slug}")
    return int(matches[0].replace(",", ""))


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
    total = 0
    for element, repo in (("pmo", "pmo-skills"), ("coach", "personal-career-coach")):
        downloads = download_count(repo)
        count = downloads
        label = "downloads"
        if slug := AGENSI_LISTINGS.get(element):
            uses = agensi_uses(slug)
            count += uses
            label = f"combined · {downloads:,} GitHub downloads + {uses:,} Agensi uses"
        total += count
        tag = f'span id="{element}-downloads"'
        row = f'<{tag}>{count:,}</span></strong> <small>{label}</small>'
        html = replace_element(html, f'<{tag}>[^<]*</span></strong> <small>[^<]*</small>', row)
        print(f"{repo}: {count:,} {label}")
    title = "Total downloads and uses" if AGENSI_LISTINGS else "Total skill downloads"
    html = replace_element(html, r'<span id="total-downloads">[^<]*</span></strong> <small>[^<]*</small>',
                           f'<span id="total-downloads">{total:,}</span></strong> <small>{title}</small>')
    now = datetime.now(ZoneInfo("America/Denver"))
    display = now.strftime("%b %d, %Y at %I:%M %p %Z").replace(" 0", " ")
    html = replace_element(html, r'<time id="downloads-updated" datetime="[^"]*">[^<]*</time>',
                           f'<time id="downloads-updated" datetime="{now.isoformat(timespec="minutes")}">{display}</time>')
    path.write_text(html)


if __name__ == "__main__":
    main()
