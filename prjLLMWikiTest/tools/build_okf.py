"""Turn raw/*.json into an OKF v0.2 bundle using Claude on Bedrock.

Run from prjLLMWikiTest/:
    uv run --with boto3 tools/build_okf.py [--force]

Two passes: attractions first, then hubs and indexes, so every hub link points at
a file that already exists.
"""

import json
import sys
from pathlib import Path

import boto3

from sites import SITES, REGIONS, THEMES, REGION_TITLES, THEME_TITLES, by_region, by_theme

MODEL_ID = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
RAW = Path("raw")
WIKI = Path("app/CyrpusLLMWikiAgent/wiki")
CHAR_BUDGET = 12000

_client = None


def ask(prompt: str, max_tokens: int = 2000) -> str:
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime")
    resp = _client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.2},
    )
    return resp["output"]["message"]["content"][0]["text"]


def parse_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(t)


def frontmatter(d: dict) -> str:
    """Serialise a flat dict as YAML frontmatter. Scalars are JSON-quoted so a
    colon in a description or a URL cannot break the block."""
    out = ["---"]
    for k, v in d.items():
        if isinstance(v, list):
            out.append(f"{k}: [{', '.join(str(i) for i in v)}]")
        elif k == "type":
            out.append(f"type: {v}")
        else:
            out.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    out.append("---")
    return "\n".join(out) + "\n"


SITE_PROMPT = """You write one page of a travel knowledge base about Cyprus.

SOURCE (a Wikipedia plaintext extract for "{title}"):
<<<
{extract}
>>>

Write a concise encyclopedic page from the SOURCE ONLY.

HARD RULES
- Use only facts present in the SOURCE. Invent nothing.
- NEVER state opening hours, ticket prices, phone numbers, bus routes, drive times,
  or anything that changes over time. If the SOURCE has them, leave them out.
- Stay historical, archaeological and geographic.
- No markdown links. No headings other than the four listed below.

Return ONLY a JSON object, no prose around it:
{{
  "description": "one sentence, under 140 characters, what this place is",
  "tags": ["3 to 5 lowercase single-word or hyphenated tags"],
  "body": "markdown with exactly these four headings in this order: '# Overview', '# History', '# What to see', '# Location & access'. 2 to 5 sentences under each. Under 'Location & access' give only where it is (region, nearby town, terrain) - no travel practicalities."
}}
"""


def build_sites(force: bool = False) -> None:
    (WIKI / "sites").mkdir(parents=True, exist_ok=True)
    for site in SITES:
        out = WIKI / "sites" / f"{site['slug']}.md"
        if out.exists() and not force:
            print(f"skip  sites/{site['slug']}.md")
            continue
        raw = json.loads((RAW / f"{site['slug']}.json").read_text(encoding="utf-8"))
        answer = parse_json(ask(SITE_PROMPT.format(
            title=raw["title"], extract=raw["extract"][:CHAR_BUDGET])))

        related = [s for s in by_region(site["region"]) if s["slug"] != site["slug"]]
        body = answer["body"].strip() + "\n\n# Related\n"
        body += f"- [{REGION_TITLES[site['region']]}](/regions/{site['region']}.md) - region overview\n"
        for t in site["themes"]:
            body += f"- [{THEME_TITLES[t]}](/themes/{t}.md) - theme\n"
        for r in related:
            body += f"- [{r['title']}](/sites/{r['slug']}.md) - also in {REGION_TITLES[site['region']]}\n"

        fm = {
            "type": "attraction",
            "title": site["title"],
            "description": answer["description"],
            "resource": raw["url"],
            "tags": answer["tags"],
            "region": f"/regions/{site['region']}.md",
            "themes": [f"/themes/{t}.md" for t in site["themes"]],
        }
        if raw["coordinates"]:
            fm["coordinates"] = f"{raw['coordinates']['lat']},{raw['coordinates']['lon']}"
        out.write_text(frontmatter(fm) + "\n" + body, encoding="utf-8")
        print(f"ok    sites/{site['slug']}.md", flush=True)


def main() -> int:
    force = "--force" in sys.argv
    build_sites(force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
