"""Refresh the static AI Skills page with one complete snapshot of GitHub downloads and Agensi listing uses."""

import json
import os
import re
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


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


def downloads_by_file(repository):
    base = f"https://api.github.com/repos/jsconu/{repository}/releases"
    totals = Counter()
    for release in pages(base):
        if release["draft"]:
            continue
        for asset in pages(f"{base}/{release['id']}/assets"):
            if asset["state"] == "uploaded" and asset["name"].endswith((".zip", ".md")):
                totals[asset["name"]] += asset["download_count"]
    if not totals:
        raise ValueError(f"No published skill assets found in {repository}")
    return totals


def log_pmo_ranking(files, listing_uses):
    downloads = Counter()
    bundles = 0
    for filename, count in files.items():
        skill = Path(filename).stem
        if skill == "pmo-skills-all":
            bundles += count
        else:
            downloads[skill] += count

    uses = {("choose-todays-focus" if slug == "choose-today-s-focus" else slug): value
            for slug, value in listing_uses.items()}
    skills = sorted(downloads.keys() | uses.keys(),
                    key=lambda skill: (-(downloads[skill] + (uses.get(skill) or 0)), skill))
    for skill in skills:
        use_count = uses.get(skill)
        use_label = "unavailable" if use_count is None else f"{use_count:,}"
        print(f"{skill}: {downloads[skill]:,} downloads, {use_label} Agensi uses")
    print(f"Full PMO bundle: {bundles:,} downloads")


def replace_element(html, pattern, replacement):
    html, matches = re.subn(pattern, lambda _: replacement, html)
    if matches != 1:
        raise ValueError(f"Expected one dashboard element matching {pattern}")
    return html


def main():
    path = Path(__file__).resolve().parents[1] / "ai-skills/index.html"
    html = path.read_text()
    snapshot = {}
    total = 0
    for element, repo in (("pmo", "pmo-skills"), ("coach", "personal-career-coach")):
        files = downloads_by_file(repo)
        downloads = sum(files.values())
        count = downloads
        label = "downloads"
        listing_uses = {slug: agensi_uses(slug) for slug in AGENSI_LISTINGS[element]}
        if element == "pmo":
            log_pmo_ranking(files, listing_uses)
        live = [n for n in listing_uses.values() if n is not None]
        if live:
            uses = sum(live)
            count += uses
            label = f"combined · {downloads:,} GitHub + {uses:,} Agensi downloads"
        snapshot[element] = {"count": count, "label": label, "agensiUses": sum(live) if live else None}
        total += count
        tag = f'span id="{element}-downloads"'
        row = f'<{tag}>{count:,}</span></strong> <small>{label}</small>'
        html = replace_element(html, f'<{tag}>[^<]*</span></strong> <small>[^<]*</small>', row)
        print(f"{repo}: {count:,} {label}")
    title = "Total downloads"
    html = replace_element(html, r'<span id="total-downloads">[^<]*</span></strong> <small>[^<]*</small>',
                           f'<span id="total-downloads">{total:,}</span></strong> <small>{title}</small>')
    snapshot["total"] = {"count": total, "label": title}
    path.write_text(html)
    path.with_name("counts.json").write_text(json.dumps(snapshot, indent=2) + "\n")


if __name__ == "__main__":
    main()
