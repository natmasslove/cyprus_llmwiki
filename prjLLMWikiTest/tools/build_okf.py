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

from sites import SITES, REGIONS, THEMES, REGION_TITLES, THEME_TITLES, by_region, by_theme, display

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
            body += f"- [{display(r)}](/sites/{r['slug']}.md) - also in {REGION_TITLES[site['region']]}\n"

        fm = {
            "type": "attraction",
            "title": display(site),
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


def read_description(path: Path) -> str:
    """Pull `description` out of a generated document's frontmatter.

    The builder writes that frontmatter itself with JSON-quoted scalars, so a
    line-scan is enough and boto3 stays the only dependency.
    """
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        if line == "---":
            break
        if line.startswith("description:"):
            return json.loads(line[len("description:"):].strip())
    return ""


HUB_PROMPT = """You write the orientation paragraph for a hub page of a Cyprus travel
knowledge base.

HUB: {hub_title}
MEMBER SITES:
{members}

Write ONE paragraph, 3 to 5 sentences, that tells a reader what this group of places
has in common and what to expect. Use only what the member list implies. Invent no
facts, no hours, no prices, no travel times. No markdown links, no headings.

Return ONLY a JSON object:
{{"description": "one sentence, under 140 characters", "tags": ["2 to 4 lowercase tags"], "body": "the paragraph"}}
"""


def _build_hub(kind: str, key: str, title: str, members: list, force: bool) -> None:
    out = WIKI / f"{kind}s" / f"{key}.md"
    if out.exists() and not force:
        print(f"skip  {kind}s/{key}.md")
        return
    listing = "\n".join(
        f"- {display(m)}: {read_description(WIKI / 'sites' / (m['slug'] + '.md'))}"
        for m in members
    )
    answer = parse_json(ask(HUB_PROMPT.format(hub_title=title, members=listing), max_tokens=900))
    body = answer["body"].strip() + "\n\n# Sites\n"
    for m in members:
        body += f"- [{display(m)}](/sites/{m['slug']}.md) - {read_description(WIKI / 'sites' / (m['slug'] + '.md'))}\n"
    fm = {"type": kind, "title": title, "description": answer["description"], "tags": answer["tags"]}
    out.write_text(frontmatter(fm) + "\n" + body, encoding="utf-8")
    print(f"ok    {kind}s/{key}.md", flush=True)


def build_hubs(force: bool = False) -> None:
    (WIKI / "regions").mkdir(parents=True, exist_ok=True)
    (WIKI / "themes").mkdir(parents=True, exist_ok=True)
    for region in REGIONS:
        _build_hub("region", region, REGION_TITLES[region], by_region(region), force)
    for theme in THEMES:
        _build_hub("theme", theme, THEME_TITLES[theme], by_theme(theme), force)


def build_indexes() -> None:
    """Deterministic. Always rewritten, so it always matches what is on disk."""
    def listing(kind: str, keys, titles) -> str:
        return "".join(
            f"- [{titles[k]}](/{kind}/{k}.md) - {read_description(WIKI / kind / (k + '.md'))}\n"
            for k in keys
        )

    (WIKI / "regions" / "index.md").write_text(
        frontmatter({"type": "index", "title": "Regions",
                     "description": "The five areas this wiki covers."})
        + "\n# Regions\n\n" + listing("regions", REGIONS, REGION_TITLES),
        encoding="utf-8")

    (WIKI / "themes" / "index.md").write_text(
        frontmatter({"type": "index", "title": "Themes",
                     "description": "Cross-cutting groupings of attractions."})
        + "\n# Themes\n\n" + listing("themes", THEMES, THEME_TITLES),
        encoding="utf-8")

    (WIKI / "sites" / "index.md").write_text(
        frontmatter({"type": "index", "title": "Sites",
                     "description": "All 15 attractions, alphabetical."})
        + "\n# Sites\n\n" + "".join(
            f"- [{display(s)}](/sites/{s['slug']}.md) - {read_description(WIKI / 'sites' / (s['slug'] + '.md'))}\n"
            for s in sorted(SITES, key=display)),
        encoding="utf-8")

    (WIKI / "index.md").write_text(
        frontmatter({"type": "index", "okf_version": "0.2", "title": "Cyprus Attractions",
                     "description": "Tourist attractions in the government-controlled areas of Cyprus."})
        + """
# Cyprus Attractions

A knowledge base of 15 tourist attractions in the government-controlled areas of
the Republic of Cyprus: archaeological sites, castles, monasteries and natural
landmarks. Content is historical and geographic only. It carries no opening
hours, prices or travel practicalities. Sites in the north are not covered.

## Directories

- [Regions](/regions/index.md) - browse by area: Paphos, Limassol, Larnaca, Troodos, Famagusta
- [Themes](/themes/index.md) - browse by kind: ancient sites, monasteries and churches, beaches and nature
- [Sites](/sites/index.md) - all 15 attraction pages, alphabetical
""",
        encoding="utf-8")
    print("ok    index.md x4")


def main() -> int:
    force = "--force" in sys.argv
    build_sites(force)
    build_hubs(force)
    build_indexes()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
