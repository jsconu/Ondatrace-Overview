"""Refresh the static AI Skills page with one complete snapshot of GitHub downloads and Agensi listing uses."""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


# Agensi listings per skill card. Each listing page embeds the same use counter
# that the Agensi creator dashboard shows ("Uses"), as install_count.
AGENSI_LISTINGS = {
    "pmo": [
        "build-the-portfolio-report", "challenge-my-status", "check-the-decision",
        "check-the-success-metrics", "choose-today-s-focus", "debrief-the-meeting",
        "draft-the-charter", "draft-the-stakeholder-update", "find-capacity-conflicts",
        "find-recurring-lessons", "find-the-projects", "group-portfolio-risks",
        "interview-the-sponsor", "plan-change-adoption", "plan-the-handoff",
        "prep-the-portfolio-review", "prioritize-the-backlog", "reconcile-the-dates",
        "review-a-change-request", "review-the-budget", "run-the-retrospective",
        "trace-a-decision", "trace-the-impact", "triage-the-risks", "write-the-weekly-update",
    ],
    "coach": ["personal-career-coach"],
}


def agensi_uses(slug):
    """Return the listing's use count, or None while the listing is not public (still in review)."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("Invalid Agensi listing slug")
    url = f"https://www.agensi.io/skills/{slug}"
    request = Request(url, headers={"User-Agent": "Ondatrace public skill statistics"})
    try:
        with urlopen(request, timeout=30) as response:
            if response.geturl().rstrip("/") != url:
                return None
            html = response.read().decode("utf-8")
    except HTTPError as error:
        if error.code == 404:
            return None
        raise
    if f'slug:"{slug}"' not in html:
        raise ValueError(f"Agensi page for {slug} does not describe that listing")
    matches = re.findall(r"\binstall_count:(\d+)\b", html)
    if len(matches) != 1:
        raise ValueError(f"Could not verify an exact Agensi use count for {slug}")
    return int(matches[0])


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
        live = [n for n in map(agensi_uses, AGENSI_LISTINGS.get(element, [])) if n is not None]
        if live:
            uses = sum(live)
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
