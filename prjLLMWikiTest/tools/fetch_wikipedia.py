"""Fetch Wikipedia plaintext for every site in the manifest. No LLM.

Run from prjLLMWikiTest/:
    uv run --with certifi python tools/fetch_wikipedia.py [--force]

certifi only because this machine's default CA store carries an expired root and
rejects the Wikipedia certificate.
"""

import json
import ssl
import time
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import certifi

from sites import SITES

API = "https://en.wikipedia.org/w/api.php"
UA = "CyprusLLMWikiPrototype/0.1 (https://github.com/natmasslove/cyprus_llmwiki)"
RAW = Path("raw")
SSL_CTX = ssl.create_default_context(cafile=certifi.where())


def fetch(title: str) -> dict:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "extracts|coordinates|info",
        "inprop": "url",
        "explaintext": "1",
        "exsectionformat": "plain",
        "redirects": "1",
        "titles": title,
    }
    req = urllib.request.Request(
        f"{API}?{urllib.parse.urlencode(params)}", headers={"User-Agent": UA}
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
                data = json.load(resp)
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            time.sleep(15 * (attempt + 1))
    pages = data["query"]["pages"]
    if not pages or pages[0].get("missing"):
        raise LookupError(f"no Wikipedia page for title: {title!r}")
    return pages[0]


def main() -> int:
    force = "--force" in sys.argv
    RAW.mkdir(exist_ok=True)
    failures = []
    for site in SITES:
        out = RAW / f"{site['slug']}.json"
        if out.exists() and not force:
            print(f"skip  {site['slug']}")
            continue
        try:
            page = fetch(site["title"])
        except LookupError as e:
            print(f"FAIL  {site['slug']}: {e}")
            failures.append(site["slug"])
            continue
        coords = page.get("coordinates")
        record = {
            "slug": site["slug"],
            "title": page["title"],
            "url": page["fullurl"],
            "coordinates": {"lat": coords[0]["lat"], "lon": coords[0]["lon"]} if coords else None,
            "extract": page.get("extract", ""),
        }
        out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"ok    {site['slug']}  ({len(record['extract'])} chars)", flush=True)
        time.sleep(2)
    if failures:
        print(f"\n{len(failures)} title(s) did not resolve: {failures}")
        print("Fix the `title` field in tools/sites.py and rerun.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
