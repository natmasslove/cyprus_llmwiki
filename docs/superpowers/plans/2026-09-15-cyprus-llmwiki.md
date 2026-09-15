# Cyprus LLMWiki Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an OKF v0.2 markdown wiki about 15 Cyprus attractions, and make the existing Strands agent answer only by navigating it.

**Architecture:** Three separate programs. Build-time scripts in `tools/` fetch Wikipedia plaintext to `raw/*.json`, then a Bedrock-backed builder writes `wiki/**.md`. Run-time, the agent gets three read-only filesystem tools jailed to `WIKI_ROOT` and the root index inlined in its system prompt. The builder never runs at query time; the agent never calls Wikipedia.

**Tech Stack:** Python 3.10+, stdlib `urllib` + `pathlib`, `boto3` (build only), `PyYAML` (lint only), Strands Agents SDK, Bedrock AgentCore, `uv`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-15-cyprus-llmwiki-design.md`

## Global Constraints

| Constraint | Value |
| --- | --- |
| Branch | `spec/cyprus-llmwiki`. Never commit to `main`. |
| Working directory for all scripts | `prjLLMWikiTest/` |
| Git repo root | `C:\_prj\cyprus_llmwiki` |
| OKF version | `0.2`, declared in bundle-root `index.md` frontmatter only |
| Required OKF field | `type`, non-empty, on every non-reserved `.md` |
| Reserved filenames | `index.md`, `log.md` — exempt from the `type` rule |
| Bundle-relative links | start with `/`, resolve against bundle root |
| Types used | `attraction`, `region`, `theme`, `index` |
| Themes (exactly 3) | `ancient-sites`, `monasteries`, `beaches-nature` |
| Regions (exactly 5) | `paphos`, `limassol`, `larnaca`, `troodos`, `famagusta` |
| Sites (exactly 15) | see Task 1 |
| Bedrock model id | `global.anthropic.claude-sonnet-4-5-20250929-v1:0` (same as `model/load.py`) |
| Agent runtime deps | UNCHANGED. Do not edit `app/CyrpusLLMWikiAgent/pyproject.toml`. |
| Build/lint deps | supplied per-run with `uv run --with ...` |
| Scope | throwaway learning prototype. No extensibility, no configurability, no error handling for impossible cases. |

## File Structure

| File | Responsibility | New? |
| --- | --- | --- |
| `prjLLMWikiTest/tools/sites.py` | 15-record site manifest. Single source of truth. | create |
| `prjLLMWikiTest/tools/fetch_wikipedia.py` | Wikipedia REST -> `raw/<slug>.json`. No LLM. | create |
| `prjLLMWikiTest/tools/build_okf.py` | `raw/*.json` -> `wiki/**.md`. Two passes. Bedrock. | create |
| `prjLLMWikiTest/tools/lint_okf.py` | OKF conformance checker. | create |
| `prjLLMWikiTest/raw/*.json` | committed Wikipedia plaintext | generated |
| `prjLLMWikiTest/app/CyrpusLLMWikiAgent/wiki/**.md` | the OKF bundle | generated |
| `prjLLMWikiTest/app/CyrpusLLMWikiAgent/wiki_nav/tools.py` | 3 Strands `@tool` functions + path jail | create |
| `prjLLMWikiTest/app/CyrpusLLMWikiAgent/main.py` | rewire tools + system prompt | modify |
| `prjLLMWikiTest/tests/conftest.py` | `sys.path` for `tools/` and the app dir | create |
| `prjLLMWikiTest/tests/test_sites.py` | manifest invariants | create |
| `prjLLMWikiTest/tests/test_lint_okf.py` | linter catches a missing `type` | create |
| `prjLLMWikiTest/tests/test_wiki_nav.py` | path jail + missing-file guidance | create |

## Task Graph

```
T1 sites.py
 |        \
 |         +--> T2 fetch_wikipedia --> T4 build pass 1 (sites) [AWS]
 |                                        |
 +----------------------------------------+--> T5 build pass 2 (hubs) [AWS]
                                                    |
T3 lint_okf ----------------------------------------+
                                                    |
T6 wiki_nav/tools.py ------------------------------>+--> T7 main.py --> T8 probes [AWS]
                                                                            |
                                                                            +--> T9 visualize (optional)
```

| Task | Needs AWS Bedrock credentials | Needs network |
| --- | --- | --- |
| T1, T3, T6, T7 | no | no |
| T2 | no | yes (Wikipedia) |
| T4, T5 | **yes** | no |
| T8 | **yes** | no |
| T9 | no | yes (GitHub clone) |

**Test command (all tasks):**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
uv run --with pytest --with pyyaml --with strands-agents pytest tests/ -v
```

---

### Task 1: Site manifest ✅

**Files:**
- Create: `prjLLMWikiTest/tools/sites.py`
- Create: `prjLLMWikiTest/tests/conftest.py`
- Test: `prjLLMWikiTest/tests/test_sites.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `sites.SITES: list[dict]` — each `{"title": str, "slug": str, "region": str, "themes": list[str]}`. `title` is the Wikipedia article title. `sites.REGIONS: list[str]`, `sites.THEMES: list[str]`.

- [x] **Step 1: Write the conftest**

Create `prjLLMWikiTest/tests/conftest.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "app" / "CyrpusLLMWikiAgent"))
```

- [x] **Step 2: Write the failing test**

Create `prjLLMWikiTest/tests/test_sites.py`:

```python
from sites import SITES, REGIONS, THEMES


def test_fifteen_sites():
    assert len(SITES) == 15


def test_slugs_unique_and_filename_safe():
    slugs = [s["slug"] for s in SITES]
    assert len(set(slugs)) == 15
    for slug in slugs:
        assert slug == slug.lower()
        assert all(c.isalnum() or c == "-" for c in slug)


def test_regions_and_themes_are_known():
    assert set(REGIONS) == {"paphos", "limassol", "larnaca", "troodos", "famagusta"}
    assert set(THEMES) == {"ancient-sites", "monasteries", "beaches-nature"}
    for s in SITES:
        assert s["region"] in REGIONS
        assert s["themes"], f"{s['slug']} has no theme"
        for t in s["themes"]:
            assert t in THEMES


def test_every_region_and_theme_has_a_member():
    used_regions = {s["region"] for s in SITES}
    used_themes = {t for s in SITES for t in s["themes"]}
    assert used_regions == set(REGIONS)
    assert used_themes == set(THEMES)
```

- [x] **Step 3: Run the test to verify it fails**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
uv run --with pytest --with pyyaml --with strands-agents pytest tests/test_sites.py -v
```

Expected: FAIL, `ModuleNotFoundError: No module named 'sites'`.

- [x] **Step 4: Write the manifest**

Create `prjLLMWikiTest/tools/sites.py`:

```python
"""The site manifest. Single source of truth for both build scripts.

Region and theme assignment is a curation decision, fixed by hand here and never
left to the model. `title` must be the English Wikipedia article title; the fetch
script follows redirects, so a near-miss title still resolves.
"""

REGIONS = ["paphos", "limassol", "larnaca", "troodos", "famagusta"]
THEMES = ["ancient-sites", "monasteries", "beaches-nature"]

SITES = [
    {"title": "Paphos Archaeological Park", "slug": "paphos-archaeological-park",
     "region": "paphos", "themes": ["ancient-sites"]},
    {"title": "Tomb of the Kings (Paphos)", "slug": "tombs-of-the-kings",
     "region": "paphos", "themes": ["ancient-sites"]},
    {"title": "Petra tou Romiou", "slug": "petra-tou-romiou",
     "region": "paphos", "themes": ["beaches-nature"]},
    {"title": "Agios Neophytos Monastery", "slug": "agios-neophytos-monastery",
     "region": "paphos", "themes": ["monasteries"]},

    {"title": "Kourion", "slug": "kourion",
     "region": "limassol", "themes": ["ancient-sites"]},
    {"title": "Sanctuary of Apollo Hylates", "slug": "apollo-hylates",
     "region": "limassol", "themes": ["ancient-sites"]},
    {"title": "Kolossi Castle", "slug": "kolossi-castle",
     "region": "limassol", "themes": ["ancient-sites"]},
    {"title": "Limassol Castle", "slug": "limassol-castle",
     "region": "limassol", "themes": ["ancient-sites"]},

    {"title": "Church of Saint Lazarus", "slug": "church-of-saint-lazarus",
     "region": "larnaca", "themes": ["monasteries"]},
    {"title": "Hala Sultan Tekke", "slug": "hala-sultan-tekke",
     "region": "larnaca", "themes": ["monasteries"]},
    {"title": "Choirokoitia", "slug": "choirokoitia",
     "region": "larnaca", "themes": ["ancient-sites"]},
    {"title": "Larnaca Salt Lake", "slug": "larnaca-salt-lake",
     "region": "larnaca", "themes": ["beaches-nature"]},

    {"title": "Kykkos Monastery", "slug": "kykkos-monastery",
     "region": "troodos", "themes": ["monasteries"]},
    {"title": "Painted Churches in the Troodos Region", "slug": "painted-churches-troodos",
     "region": "troodos", "themes": ["monasteries"]},

    {"title": "Cape Greco", "slug": "cape-greco",
     "region": "famagusta", "themes": ["beaches-nature"]},
]

REGION_TITLES = {
    "paphos": "Paphos",
    "limassol": "Limassol",
    "larnaca": "Larnaca",
    "troodos": "Troodos",
    "famagusta": "Famagusta (Ayia Napa & Protaras)",
}

THEME_TITLES = {
    "ancient-sites": "Ancient & Historic Sites",
    "monasteries": "Monasteries & Churches",
    "beaches-nature": "Beaches & Nature",
}


def by_region(region: str) -> list[dict]:
    return [s for s in SITES if s["region"] == region]


def by_theme(theme: str) -> list[dict]:
    return [s for s in SITES if theme in s["themes"]]
```

- [x] **Step 5: Run the test to verify it passes**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
uv run --with pytest --with pyyaml --with strands-agents pytest tests/test_sites.py -v
```

Expected: PASS, 4 tests.

- [x] **Step 6: Commit**

```bash
cd C:/_prj/cyprus_llmwiki
git add prjLLMWikiTest/tools/sites.py prjLLMWikiTest/tests/conftest.py prjLLMWikiTest/tests/test_sites.py
git commit -m "feat: site manifest for Cyprus LLMWiki

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Task 2: Fetch Wikipedia plaintext ✅

**Files:**
- Create: `prjLLMWikiTest/tools/fetch_wikipedia.py`
- Output: `prjLLMWikiTest/raw/<slug>.json` (15 files, committed)

**Interfaces:**
- Consumes: `sites.SITES`.
- Produces: `raw/<slug>.json` with keys `slug`, `title`, `url`, `coordinates` (`{"lat": float, "lon": float}` or `null`), `extract` (full plaintext).

Note: the extracts API returns one full (non-intro) extract per request, so the script makes one HTTP call per site. 15 calls, no batching. Wikipedia requires a `User-Agent`.

- [x] **Step 1: Write the script**

Create `prjLLMWikiTest/tools/fetch_wikipedia.py`:

```python
"""Fetch Wikipedia plaintext for every site in the manifest. No LLM, stdlib only.

Run from prjLLMWikiTest/:
    python tools/fetch_wikipedia.py [--force]
"""

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from sites import SITES

API = "https://en.wikipedia.org/w/api.php"
UA = "CyprusLLMWikiPrototype/0.1 (learning prototype; contact: local)"
RAW = Path("raw")


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
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
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
        print(f"ok    {site['slug']}  ({len(record['extract'])} chars)")
    if failures:
        print(f"\n{len(failures)} title(s) did not resolve: {failures}")
        print("Fix the `title` field in tools/sites.py and rerun.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 2: Run it**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
PYTHONPATH=tools python tools/fetch_wikipedia.py
```

Expected: 15 `ok` lines, exit 0. If any title fails to resolve, correct that `title` in `tools/sites.py` (keep the `slug` unchanged — it is the OKF filename) and rerun.

- [x] **Step 3: Verify the output**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
ls raw/*.json | wc -l
python -c "import json,glob; [print(p, len(json.load(open(p,encoding='utf-8'))['extract'])) for p in sorted(glob.glob('raw/*.json'))]"
```

Expected: `15`, and every extract length > 1000. An extract under 1000 chars means the title hit a disambiguation or stub page — fix the title and rerun with `--force`.

- [x] **Step 4: Commit**

```bash
cd C:/_prj/cyprus_llmwiki
git add prjLLMWikiTest/tools/fetch_wikipedia.py prjLLMWikiTest/raw
git commit -m "feat: fetch Wikipedia extracts to raw/

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Task 3: OKF conformance linter ✅

**Files:**
- Create: `prjLLMWikiTest/tools/lint_okf.py`
- Test: `prjLLMWikiTest/tests/test_lint_okf.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `lint_okf.lint(bundle: Path) -> tuple[list[str], list[str]]` returning `(errors, warnings)`. CLI `main()` exits 1 if `errors` is non-empty.

Rules:

| # | Rule | Severity |
| --- | --- | --- |
| 1 | every non-reserved `.md` has parseable YAML frontmatter | error |
| 2 | every non-reserved `.md` has a non-empty `type` | error |
| 3 | bundle-root `index.md` declares `okf_version: "0.2"` | error |
| 4 | every bundle-relative link (`/...`) resolves to a file | warning |

Rule 4 is a warning because the OKF spec requires consumers to tolerate broken links — but a producer wants to know.

- [x] **Step 1: Write the failing test**

Create `prjLLMWikiTest/tests/test_lint_okf.py`:

```python
from pathlib import Path

import lint_okf


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def good_bundle(tmp_path: Path) -> Path:
    write(tmp_path / "index.md", '---\ntype: index\nokf_version: "0.2"\n---\n# Wiki\n')
    write(tmp_path / "sites" / "kourion.md",
          '---\ntype: attraction\ntitle: "Kourion"\n---\n# Overview\ntext\n')
    return tmp_path


def test_good_bundle_has_no_errors(tmp_path):
    errors, warnings = lint_okf.lint(good_bundle(tmp_path))
    assert errors == []
    assert warnings == []


def test_missing_type_is_an_error(tmp_path):
    bundle = good_bundle(tmp_path)
    write(bundle / "sites" / "broken.md", '---\ntitle: "No type"\n---\n# Overview\n')
    errors, _ = lint_okf.lint(bundle)
    assert any("broken.md" in e and "type" in e for e in errors)


def test_empty_type_is_an_error(tmp_path):
    bundle = good_bundle(tmp_path)
    write(bundle / "sites" / "empty.md", '---\ntype: ""\n---\n# Overview\n')
    errors, _ = lint_okf.lint(bundle)
    assert any("empty.md" in e for e in errors)


def test_unparseable_frontmatter_is_an_error(tmp_path):
    bundle = good_bundle(tmp_path)
    write(bundle / "sites" / "nofm.md", "# No frontmatter at all\n")
    errors, _ = lint_okf.lint(bundle)
    assert any("nofm.md" in e for e in errors)


def test_index_is_exempt_from_the_type_rule(tmp_path):
    bundle = good_bundle(tmp_path)
    write(bundle / "sites" / "index.md", "---\ntitle: Sites\n---\n# Sites\n")
    errors, _ = lint_okf.lint(bundle)
    assert errors == []


def test_missing_okf_version_is_an_error(tmp_path):
    write(tmp_path / "index.md", "---\ntype: index\n---\n# Wiki\n")
    errors, _ = lint_okf.lint(tmp_path)
    assert any("okf_version" in e for e in errors)


def test_broken_link_is_a_warning_not_an_error(tmp_path):
    bundle = good_bundle(tmp_path)
    write(bundle / "sites" / "linky.md",
          '---\ntype: attraction\n---\n[gone](/sites/gone.md)\n')
    errors, warnings = lint_okf.lint(bundle)
    assert errors == []
    assert any("/sites/gone.md" in w for w in warnings)


def test_unknown_keys_are_tolerated(tmp_path):
    bundle = good_bundle(tmp_path)
    write(bundle / "sites" / "extra.md",
          '---\ntype: attraction\nregion: /regions/limassol.md\nwhatever: 42\n---\n# Overview\n')
    errors, _ = lint_okf.lint(bundle)
    assert errors == []
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
uv run --with pytest --with pyyaml --with strands-agents pytest tests/test_lint_okf.py -v
```

Expected: FAIL, `ModuleNotFoundError: No module named 'lint_okf'`.

- [x] **Step 3: Write the linter**

Create `prjLLMWikiTest/tools/lint_okf.py`:

```python
"""Check an OKF v0.2 bundle for conformance.

Run from prjLLMWikiTest/:
    uv run --with pyyaml tools/lint_okf.py [bundle-path]
"""

import re
import sys
from pathlib import Path

import yaml

RESERVED = {"index.md", "log.md"}
LINK = re.compile(r"\[[^\]]*\]\((/[^)\s]+)\)")
DEFAULT_BUNDLE = Path("app/CyrpusLLMWikiAgent/wiki")


def split_frontmatter(text: str):
    """Return (frontmatter dict, body) or (None, text) if there is no valid block."""
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None, text
    if not isinstance(data, dict):
        return None, text
    return data, parts[2]


def lint(bundle: Path):
    errors, warnings = [], []
    root_index = bundle / "index.md"
    if not root_index.exists():
        errors.append("index.md: bundle root index.md is missing")
    else:
        fm, _ = split_frontmatter(root_index.read_text(encoding="utf-8"))
        if not fm or str(fm.get("okf_version", "")) != "0.2":
            errors.append('index.md: bundle root must declare okf_version: "0.2"')

    for path in sorted(bundle.rglob("*.md")):
        rel = "/" + path.relative_to(bundle).as_posix()
        text = path.read_text(encoding="utf-8")
        fm, body = split_frontmatter(text)
        if path.name not in RESERVED:
            if fm is None:
                errors.append(f"{rel}: no parseable YAML frontmatter")
                body = text
            elif not str(fm.get("type", "")).strip():
                errors.append(f"{rel}: missing or empty `type`")
        for target in LINK.findall(body or ""):
            if not (bundle / target.lstrip("/")).exists():
                warnings.append(f"{rel}: broken link -> {target}")
    return errors, warnings


def main() -> int:
    bundle = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BUNDLE
    errors, warnings = lint(bundle)
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s) in {bundle}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Run the test to verify it passes**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
uv run --with pytest --with pyyaml --with strands-agents pytest tests/test_lint_okf.py -v
```

Expected: PASS, 8 tests.

- [x] **Step 5: Commit**

```bash
cd C:/_prj/cyprus_llmwiki
git add prjLLMWikiTest/tools/lint_okf.py prjLLMWikiTest/tests/test_lint_okf.py
git commit -m "feat: OKF v0.2 conformance linter

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Task 4: Build pass 1 — attraction documents ✅

**REQUIRES AWS BEDROCK CREDENTIALS.** Uses `bedrock-runtime:Converse` in the region from `AWS_REGION`/`AWS_DEFAULT_REGION`.

**Files:**
- Create: `prjLLMWikiTest/tools/build_okf.py`
- Output: `prjLLMWikiTest/app/CyrpusLLMWikiAgent/wiki/sites/<slug>.md` (15 files)

**Interfaces:**
- Consumes: `sites.SITES`, `raw/<slug>.json`.
- Produces: `build_okf.ask(prompt: str) -> str`, `build_okf.parse_json(text: str) -> dict`, `build_okf.frontmatter(d: dict) -> str`, `build_okf.build_sites(force: bool) -> None`. Task 5 adds `build_hubs` and `build_indexes` to the same file.

Decisions locked here:

| Item | Choice | Why |
| --- | --- | --- |
| Model returns | JSON `{"description", "tags", "body"}` — body only | script writes frontmatter deterministically, so `type`/`resource`/`region`/`themes` cannot be malformed |
| `# Related` section | written by the script: the other sites in the same region | cannot link to a file that was never built, cannot invent distances |
| Extract budget | 12000 chars | Paphos Park is ~8k words; truncation keeps the call cheap |
| Idempotence | skip existing output unless `--force` | repeated runs cost nothing |

- [x] **Step 1: Write the builder (pass 1 only)**

Create `prjLLMWikiTest/tools/build_okf.py`:

```python
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
        print(f"ok    sites/{site['slug']}.md")


def main() -> int:
    force = "--force" in sys.argv
    build_sites(force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 2: Smoke-test one document before spending 15 calls**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
PYTHONPATH=tools uv run --with boto3 python -c "
import build_okf, json
raw = json.load(open('raw/kourion.json', encoding='utf-8'))
print(build_okf.ask(build_okf.SITE_PROMPT.format(title=raw['title'], extract=raw['extract'][:12000]))[:600])
"
```

Expected: a JSON object with `description`, `tags`, `body`. If credentials or model access fail, stop and fix that first.

- [x] **Step 3: Run the full pass**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
PYTHONPATH=tools uv run --with boto3 python tools/build_okf.py
```

Expected: 15 `ok` lines.

- [x] **Step 4: Verify**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
ls app/CyrpusLLMWikiAgent/wiki/sites/*.md | wc -l
head -20 app/CyrpusLLMWikiAgent/wiki/sites/kourion.md
grep -riE "opening hours|admission|€|entrance fee|open daily" app/CyrpusLLMWikiAgent/wiki/sites/ || echo "no practical facts - good"
uv run --with pyyaml python tools/lint_okf.py
```

Expected: `15`; frontmatter with `type: attraction` and all 7 keys; the hallucination grep prints "no practical facts - good"; the linter reports 0 errors and warnings only about `/regions/*.md`, `/themes/*.md` and the missing root `index.md` (Task 5 creates them).

If any page contains practical facts, rebuild only that page: delete it and rerun without `--force`.

- [x] **Step 5: Commit**

```bash
cd C:/_prj/cyprus_llmwiki
git add prjLLMWikiTest/tools/build_okf.py prjLLMWikiTest/app/CyrpusLLMWikiAgent/wiki
git commit -m "feat: build attraction documents from raw extracts

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Task 5: Build pass 2 — hubs and indexes ✅

**REQUIRES AWS BEDROCK CREDENTIALS.**

**Files:**
- Modify: `prjLLMWikiTest/tools/build_okf.py` (add `build_hubs`, `build_indexes`, call both from `main`)
- Output: `wiki/regions/*.md` (5), `wiki/themes/*.md` (3), `wiki/{,regions/,sites/,themes/}index.md` (4)

**Interfaces:**
- Consumes: `build_okf.ask`, `build_okf.parse_json`, `build_okf.frontmatter`, `lint_okf.split_frontmatter` behaviour (re-implemented locally as `read_description`, to keep the builder free of a PyYAML dependency).
- Produces: `build_okf.build_hubs(force) -> None`, `build_okf.build_indexes() -> None`.

Hub bodies: one LLM call per hub for the orientation paragraph only; the member link list is appended deterministically. Index files are fully deterministic — no LLM.

- [x] **Step 1: Add the pass-2 code**

Append to `prjLLMWikiTest/tools/build_okf.py`, above `main()`:

```python
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


def _build_hub(kind: str, key: str, title: str, members: list[dict], force: bool) -> None:
    out = WIKI / f"{kind}s" / f"{key}.md"
    if out.exists() and not force:
        print(f"skip  {kind}s/{key}.md")
        return
    listing = "\n".join(
        f"- {m['title']}: {read_description(WIKI / 'sites' / (m['slug'] + '.md'))}"
        for m in members
    )
    answer = parse_json(ask(HUB_PROMPT.format(hub_title=title, members=listing), max_tokens=900))
    body = answer["body"].strip() + "\n\n# Sites\n"
    for m in members:
        body += f"- [{m['title']}](/sites/{m['slug']}.md) - {read_description(WIKI / 'sites' / (m['slug'] + '.md'))}\n"
    fm = {"type": kind, "title": title, "description": answer["description"], "tags": answer["tags"]}
    out.write_text(frontmatter(fm) + "\n" + body, encoding="utf-8")
    print(f"ok    {kind}s/{key}.md")


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
            f"- [{s['title']}](/sites/{s['slug']}.md) - {read_description(WIKI / 'sites' / (s['slug'] + '.md'))}\n"
            for s in sorted(SITES, key=lambda s: s["title"])),
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
```

- [x] **Step 2: Wire pass 2 into `main`**

Replace `main()` in `prjLLMWikiTest/tools/build_okf.py` with:

```python
def main() -> int:
    force = "--force" in sys.argv
    build_sites(force)
    build_hubs(force)
    build_indexes()
    return 0
```

- [x] **Step 3: Run it**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
PYTHONPATH=tools uv run --with boto3 python tools/build_okf.py
```

Expected: 15 `skip` lines, 8 `ok` hub lines, `ok index.md x4`.

- [x] **Step 4: Verify — the linter must be clean**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
uv run --with pyyaml python tools/lint_okf.py
echo "exit=$?"
find app/CyrpusLLMWikiAgent/wiki -name "*.md" | wc -l
head -8 app/CyrpusLLMWikiAgent/wiki/index.md
```

Expected: `0 error(s), 0 warning(s)`, `exit=0`, and `27` markdown files (15 sites + 5 regions + 3 themes + 4 indexes).

A broken-link warning means a slug in `sites.py` and a filename disagree. Fix `sites.py`, then rerun with `--force`.

- [x] **Step 5: Commit**

```bash
cd C:/_prj/cyprus_llmwiki
git add prjLLMWikiTest/tools/build_okf.py prjLLMWikiTest/app/CyrpusLLMWikiAgent/wiki
git commit -m "feat: build region/theme hubs and index documents

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Task 6: Agent navigation tools ✅

**Files:**
- Create: `prjLLMWikiTest/app/CyrpusLLMWikiAgent/wiki_nav/__init__.py` (empty)
- Create: `prjLLMWikiTest/app/CyrpusLLMWikiAgent/wiki_nav/tools.py`
- Test: `prjLLMWikiTest/tests/test_wiki_nav.py`

**Interfaces:**
- Consumes: nothing.
- Produces, imported by Task 7 as `from wiki_nav.tools import list_wiki, read_wiki, search_wiki, wiki_root`:
  - `wiki_root() -> Path` — `WIKI_ROOT` env var, else `<dir of main.py>/wiki`. Read on every call, never cached, so a test can monkeypatch the env.
  - `list_wiki(path: str = "/") -> str`
  - `read_wiki(path: str) -> str`
  - `search_wiki(query: str) -> str`

All three are Strands `@tool` functions. `DecoratedFunctionTool` forwards `__call__` to the wrapped function, so the tests call them directly.

Two decisions from the spec, do not change them:
- **Frontmatter is NOT stripped on read.** The agent needs `type`, `tags`, `region`, `themes` to decide where to go next.
- **Errors return guidance, never raise.** A wrong path returns a directory listing so the agent self-corrects in one turn.

- [x] **Step 1: Write the failing test**

Create `prjLLMWikiTest/tests/test_wiki_nav.py`:

```python
import pytest

from wiki_nav import tools as wn


@pytest.fixture
def wiki(tmp_path, monkeypatch):
    (tmp_path / "sites").mkdir()
    (tmp_path / "index.md").write_text('---\ntype: index\n---\n# Wiki\n', encoding="utf-8")
    (tmp_path / "sites" / "kourion.md").write_text(
        '---\ntype: attraction\ntitle: "Kourion"\n---\n# Overview\nRoman mosaics here.\n',
        encoding="utf-8")
    (tmp_path / "sites" / "kolossi-castle.md").write_text(
        '---\ntype: attraction\ntitle: "Kolossi Castle"\n---\n# Overview\nA keep.\n',
        encoding="utf-8")
    (tmp_path / "secret.txt").write_text("not markdown", encoding="utf-8")
    monkeypatch.setenv("WIKI_ROOT", str(tmp_path))
    return tmp_path


def test_read_wiki_returns_frontmatter_and_body(wiki):
    out = wn.read_wiki("/sites/kourion.md")
    assert "type: attraction" in out
    assert "Roman mosaics" in out


def test_read_wiki_rejects_escape(wiki, tmp_path):
    outside = tmp_path.parent / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    out = wn.read_wiki("../outside.md")
    assert "secret" not in out
    assert "outside the wiki" in out


def test_list_wiki_rejects_escape(wiki):
    out = wn.list_wiki("/../..")
    assert "outside the wiki" in out
    assert "sites/" in out  # falls back to the root listing


def test_read_wiki_missing_file_returns_a_listing_and_does_not_raise(wiki):
    out = wn.read_wiki("/sites/nicosia.md")
    assert "not found" in out
    assert "kourion.md" in out


def test_list_wiki_lists_dirs_and_files(wiki):
    out = wn.list_wiki("/")
    assert "sites/" in out
    assert "index.md" in out


def test_list_wiki_unknown_path_falls_back_to_nearest_parent(wiki):
    out = wn.list_wiki("/sites/deep/deeper")
    assert "kourion.md" in out


def test_search_wiki_is_case_insensitive_and_returns_paths(wiki):
    out = wn.search_wiki("ROMAN MOSAICS")
    assert "/sites/kourion.md:" in out


def test_search_wiki_no_matches_returns_root_listing(wiki):
    out = wn.search_wiki("zzzzzz")
    assert "no matches" in out
    assert "sites/" in out
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
uv run --with pytest --with pyyaml --with strands-agents pytest tests/test_wiki_nav.py -v
```

Expected: FAIL, `ModuleNotFoundError: No module named 'wiki_nav'`.

- [x] **Step 3: Write the tools**

Create an empty `prjLLMWikiTest/app/CyrpusLLMWikiAgent/wiki_nav/__init__.py`, then `prjLLMWikiTest/app/CyrpusLLMWikiAgent/wiki_nav/tools.py`:

```python
"""Read-only navigation over the OKF wiki bundle. pathlib only, no new dependencies.

Every path is resolved under WIKI_ROOT and anything that escapes is rejected, the
same approach as skills/fetcher.py. Failures return guidance text instead of
raising, so a wrong path costs the agent one turn, not the whole answer.
"""

import os
from pathlib import Path

from strands import tool

MAX_HITS = 20


def wiki_root() -> Path:
    """The bundle root. WIKI_ROOT env var, else `wiki/` next to main.py."""
    default = Path(__file__).resolve().parent.parent / "wiki"
    return Path(os.environ.get("WIKI_ROOT", default)).resolve()


def _resolve(path: str):
    """Resolve a bundle path under the root, or None if it escapes."""
    root = wiki_root()
    target = (root / path.strip().lstrip("/")).resolve()
    if target != root and not str(target).startswith(str(root) + os.sep):
        return None
    return target


def _listing(directory: Path) -> str:
    root = wiki_root()
    rel = "/" + directory.relative_to(root).as_posix() if directory != root else "/"
    entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
    lines = [f"{p.name}/" if p.is_dir() else p.name for p in entries]
    return f"{rel}\n" + "\n".join(f"  {line}" for line in lines)


@tool
def list_wiki(path: str = "/") -> str:
    """List the directories and files of the Cyprus wiki at a bundle path.

    Args:
        path: Bundle path such as "/" or "/sites". Defaults to the bundle root.
    """
    root = wiki_root()
    target = _resolve(path)
    if target is None:
        return f"'{path}' is outside the wiki. Showing the root instead.\n\n{_listing(root)}"
    while not target.is_dir() and target != root:
        target = target.parent
    return _listing(target)


@tool
def read_wiki(path: str) -> str:
    """Read one Cyprus wiki document, YAML frontmatter included.

    The frontmatter carries type, tags, region and themes. Use them to decide
    which document to open next.

    Args:
        path: Bundle path to a markdown file, such as "/sites/kourion.md".
    """
    root = wiki_root()
    target = _resolve(path)
    if target is None:
        return f"'{path}' is outside the wiki. Showing the root instead.\n\n{_listing(root)}"
    if target.is_file():
        return target.read_text(encoding="utf-8")
    parent = target if target.is_dir() else target.parent
    while not parent.is_dir() and parent != root:
        parent = parent.parent
    return f"'{path}' not found. Here is what that directory holds:\n\n{_listing(parent)}"


@tool
def search_wiki(query: str) -> str:
    """Case-insensitive plain-text search over every Cyprus wiki document.

    Use this only when no link path to the answer is obvious.

    Args:
        query: Text to look for, for example "mosaic" or "Byzantine".
    """
    root = wiki_root()
    needle = query.strip().lower()
    hits = []
    for path in sorted(root.rglob("*.md")):
        rel = "/" + path.relative_to(root).as_posix()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if needle in line.lower():
                hits.append(f"{rel}:{n}: {line.strip()}")
                if len(hits) >= MAX_HITS:
                    return "\n".join(hits) + f"\n\n(stopped at {MAX_HITS} hits)"
    if not hits:
        return f"no matches for '{query}'. Start from the root instead:\n\n{_listing(root)}"
    return "\n".join(hits)
```

- [x] **Step 4: Run the test to verify it passes**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
uv run --with pytest --with pyyaml --with strands-agents pytest tests/ -v
```

Expected: PASS, 20 tests (4 + 8 + 8).

- [x] **Step 5: Smoke-test against the real bundle**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest/app/CyrpusLLMWikiAgent
uv run --with strands-agents python -c "
from wiki_nav.tools import list_wiki, read_wiki, search_wiki, wiki_root
print(wiki_root())
print(list_wiki('/'))
print(read_wiki('/sites/kourion.md')[:300])
print(search_wiki('mosaic')[:300])
"
```

Expected: the real `wiki/` path, the root listing with `regions/ sites/ themes/ index.md`, Kourion's frontmatter, and at least one mosaic hit.

- [x] **Step 6: Commit**

```bash
cd C:/_prj/cyprus_llmwiki
git add prjLLMWikiTest/app/CyrpusLLMWikiAgent/wiki_nav prjLLMWikiTest/tests/test_wiki_nav.py
git commit -m "feat: wiki navigation tools for the agent

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Task 7: Rewire `main.py` ✅

**Files:**
- Modify: `prjLLMWikiTest/app/CyrpusLLMWikiAgent/main.py`

**Interfaces:**
- Consumes: `wiki_nav.tools.{list_wiki, read_wiki, search_wiki, wiki_root}`.
- Produces: nothing for later tasks.

Surgical. Touch only these:

| Change | Reason |
| --- | --- |
| delete `add_numbers` and its `tools.append` | placeholder |
| drop `tool` from the `strands` import | orphaned by deleting `add_numbers` |
| delete the `mcp_client` import, `mcp_clients`, and the append loop | Exa web search lets the agent answer around the wiki, hiding whether navigation works |
| `tools = [list_wiki, read_wiki, search_wiki]` | the three navigation tools |
| rewrite `DEFAULT_SYSTEM_PROMPT`, index inlined | ~300 tokens, saves one tool call per query, keeps the table of contents in context |

Untouched: session agent cache, `strip_trailing_tool_use`, `_extract_prompt`, `_has_inline_function_call`, `_is_inline_function_call`, `_INLINE_FUNCTION_NAMES`, the streaming entrypoint. Do not touch `pyproject.toml`. Do not delete `mcp_client/client.py` — it stays on disk, unused.

- [x] **Step 1: Replace the import block**

In `prjLLMWikiTest/app/CyrpusLLMWikiAgent/main.py`, replace:

```python
from strands import Agent, tool
```

with:

```python
from strands import Agent
```

and replace:

```python
from mcp_client.client import get_streamable_http_mcp_client
```

with:

```python
from wiki_nav.tools import list_wiki, read_wiki, search_wiki, wiki_root
```

- [x] **Step 2: Replace the block from `mcp_clients` down to the MCP append loop**

Replace this whole span:

```python
# Define a Streamable HTTP MCP Client
mcp_clients = [get_streamable_http_mcp_client()]

DEFAULT_SYSTEM_PROMPT = """
You are a helpful assistant. Use tools when appropriate.

"""


# Define a collection of tools used by the model
tools = []

_INLINE_FUNCTION_NAMES = set()

# Define a simple function tool
@tool
def add_numbers(a: int, b: int) -> int:
    """Return the sum of two numbers"""
    return a+b
tools.append(add_numbers)



# Add MCP client to tools if available
for mcp_client in mcp_clients:
    if mcp_client:
        tools.append(mcp_client)
```

with:

```python
# The bundle root index is inlined at import. It costs about 300 tokens and saves
# one tool call on every query: the table of contents stays in context, the pages
# do not.
_INDEX = (wiki_root() / "index.md").read_text(encoding="utf-8")

DEFAULT_SYSTEM_PROMPT = f"""
You are a guide to tourist attractions in Cyprus. Your only source of facts is a
local markdown wiki. You reach it with list_wiki, read_wiki and search_wiki.

How to work:
1. Start from the index below. Do not list the wiki root first, you already have it.
2. Follow the markdown links to reach specifics. A link target that starts with "/"
   is a wiki path. Pass it to read_wiki unchanged.
3. Use search_wiki only when no link path to the answer is obvious.
4. Answer only from document content you have actually read in this conversation.
   If the wiki does not cover the question, say so plainly and stop. Never fall back
   on knowledge from outside the wiki, even when you are confident.
5. The wiki holds history and geography only. It has no opening hours, prices or
   transport information. If asked for those, say the wiki does not carry them.

End every answer with the wiki paths you read.

--- wiki/index.md ---
{_INDEX}
--- end of index ---
"""

# Define a collection of tools used by the model
tools = [list_wiki, read_wiki, search_wiki]

_INLINE_FUNCTION_NAMES = set()
```

- [x] **Step 3: Verify the module imports and the prompt is populated**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest/app/CyrpusLLMWikiAgent
uv run --with strands-agents --with bedrock-agentcore python -c "
import main
assert [t.tool_name for t in main.tools] == ['list_wiki', 'read_wiki', 'search_wiki'], main.tools
assert 'Cyprus Attractions' in main.DEFAULT_SYSTEM_PROMPT
assert 'add_numbers' not in dir(main)
assert 'mcp_clients' not in dir(main)
print('ok', len(main.DEFAULT_SYSTEM_PROMPT), 'chars of prompt')
"
```

Expected: `ok <n> chars of prompt`, roughly 1500-2500.

- [x] **Step 4: Confirm the diff is surgical**

```bash
cd C:/_prj/cyprus_llmwiki
git diff --stat prjLLMWikiTest/app/CyrpusLLMWikiAgent/main.py
git diff prjLLMWikiTest/app/CyrpusLLMWikiAgent/main.py
```

Expected: changes only in the import block and the span between them and `_INLINE_FUNCTION_NAMES`. `strip_trailing_tool_use`, `_extract_prompt`, `agent_factory` and `invoke` must show zero changed lines.

- [x] **Step 5: Re-run the whole test suite**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
uv run --with pytest --with pyyaml --with strands-agents pytest tests/ -v
```

Expected: PASS, 20 tests.

- [x] **Step 6: Commit**

```bash
cd C:/_prj/cyprus_llmwiki
git add prjLLMWikiTest/app/CyrpusLLMWikiAgent/main.py
git commit -m "feat: point the agent at the wiki, drop placeholder and web-search tools

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Task 8: Manual probe run ✅

**REQUIRES AWS BEDROCK CREDENTIALS.** No code changes. This is the acceptance gate.

**Files:** none.

- [x] **Step 1: Start the agent locally**

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
agentcore dev
```

Leave it running in its own terminal.

- [x] **Step 2: Run the four probes**

In a second terminal, one at a time:

```bash
cd C:/_prj/cyprus_llmwiki/prjLLMWikiTest
agentcore invoke --dev '{"prompt": "What can I see near Limassol?"}'
agentcore invoke --dev '{"prompt": "Which sites have Roman mosaics?"}'
agentcore invoke --dev '{"prompt": "Tell me about Kourion theatre"}'
agentcore invoke --dev '{"prompt": "What are the best beaches in Crete?"}'
```

- [x] **Step 3: Check the trace, not only the answer text**

Read the tool calls in the `agentcore dev` output for each probe:

| Probe | Trace must show | Fail signal |
| --- | --- | --- |
| near Limassol | `read_wiki /regions/limassol.md` then one or more `/sites/*.md` | answer with no tool call at all |
| Roman mosaics | `read_wiki /themes/ancient-sites.md` or `search_wiki` | site names not in the wiki |
| Kourion theatre | `read_wiki /sites/kourion.md`, a short path | a long search-first detour |
| Crete beaches | a refusal, "the wiki does not cover Crete" | any actual Crete content — grounding rule broken |

- [x] **Step 4: If the Crete probe does not refuse**

Do not weaken the probe. Strengthen rule 4 of `DEFAULT_SYSTEM_PROMPT` in `main.py`, then rerun all four probes. Grounding is the whole point of the prototype.

- [x] **Step 5: Record the outcome**

Append a short `## Probe results` section to this plan file with the tool-call sequence observed for each of the four probes, then commit:

```bash
cd C:/_prj/cyprus_llmwiki
git add docs/superpowers/plans/2026-09-15-cyprus-llmwiki.md prjLLMWikiTest/app/CyrpusLLMWikiAgent/main.py
git commit -m "chore: record manual probe results

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Task 9 (optional): Third-party consumer check

Confirms the bundle is readable by a consumer we did not write. Skip if time is short — the prototype is complete without it.

**Files:** none in this repo. Clone outside the repo.

- [ ] **Step 1: Clone and visualize**

```bash
cd C:/Users/anatolii.maslov/AppData/Local/Temp
git clone --depth 1 https://github.com/GoogleCloudPlatform/open-knowledge-format
cd open-knowledge-format
uv run python -m reference_agent visualize --bundle C:/_prj/cyprus_llmwiki/prjLLMWikiTest/app/CyrpusLLMWikiAgent/wiki
```

- [ ] **Step 2: Check the graph**

Expected: 27 nodes; hub nodes fan out to their member sites; no isolated node other than nothing at all. A star topology around `index.md` means the cross-links in Task 4's `# Related` section did not land.

Do not commit the clone.

---

## Open Questions

Flag to the user, do not resolve by inventing:

| # | Question | Plan's provisional answer |
| --- | --- | --- |
| 1 | Spec §7 shows a `# Related` entry annotated with a distance ("3 km west"). Distances are not reliably in the extract, and the spec's own risk table forbids inventing practical facts. | Task 4 writes `# Related` deterministically: region hub, theme hubs, and other sites in the same region, no distances. |
| 2 | Spec §6 fixes exactly three themes. Kolossi Castle and Limassol Castle are medieval, and the Church of Saint Lazarus is a church, not a monastery. | `ancient-sites` is read as "ancient and historic", `monasteries` as "monasteries and churches". Theme titles in `sites.py` say so. |
| 3 | Spec §8.2 says pass 2 "generates" hubs but §8.0 says they are produced by "inverting this list". | Hubs get one LLM call for the orientation paragraph only; the member link lists and all four `index.md` files are deterministic. |
| 4 | Spec §11.2 lists the probe "Tell me about Kourion's theatre". Whether the Wikipedia extract covers the theatre in enough detail is unknown until Task 2 runs. | If it does not, the correct answer is a partial one plus "the wiki does not carry more". Do not add content by hand to make the probe look better. |
| 5 | Exact Wikipedia article titles are not verified in this plan. | `redirects=1` absorbs most drift; Task 2 Step 2 fails loudly on any title that does not resolve and tells the executor to fix `sites.py`. |

---

## Probe results

Run 2026-09-15 against `agentcore dev` on port 8083, model
`global.anthropic.claude-sonnet-4-5-20250929-v1:0`, eu-central-1.

CLI note: this project's `agentcore` is v0.29.0, where local invoke is
`agentcore dev --port <p> -H "X-Agentcore-Local: 1" "<prompt>"`. The plan's
`agentcore invoke --dev '{json}'` is older syntax and prints help instead.
On git-bash the CLI resolves only through the `.cmd` shim.

| Probe | Tool calls | Verdict |
| --- | --- | --- |
| near Limassol | `read_wiki /regions/index.md`, `read_wiki /regions/limassol.md` | PASS - named all 4 Limassol sites from the hub |
| Roman mosaics | `search_wiki`, `read_wiki /sites/paphos-archaeological-park.md`, `search_wiki`, `read_wiki /sites/kourion.md`, `read_wiki /themes/ancient-sites.md` | PASS - only Paphos, which is what the wiki says |
| Kourion theatre | `read_wiki /sites/kourion.md`, `search_wiki` x2 | PASS - short path first, then said the wiki does not carry the theatre |
| Crete beaches | none | PASS - refused, zero Crete content |

Totals across the four probes: 6 `read_wiki`, 4 `search_wiki`, 0 `list_wiki`.
Inlining the root index removed the root listing call, as intended.

**Open question 4, now closed by raising the budget.** The first run had no
theatre content in `wiki/sites/kourion.md`: "theatre" appears at character 13152
of the 31994-character extract, past the old `CHAR_BUDGET = 12000`. Only 2 of 15
extracts were truncated at all (kourion 31994, paphos-archaeological-park 16617).

`CHAR_BUDGET` raised to 36000, which covers every extract with no truncation.
Cost: +24,611 characters of input (~+6.8k tokens), one-time, across 2 calls.

Surgical rebuild, 5 LLM calls rather than 23 - the other 22 files stay
byte-identical. `build_hubs` skips existing files, so the hubs that embed a
changed site description must be deleted too or they keep the stale copy
silently (the linter cannot see it, the links still resolve):

```bash
rm app/CyrpusLLMWikiAgent/wiki/sites/{kourion,paphos-archaeological-park}.md
rm app/CyrpusLLMWikiAgent/wiki/{regions/limassol.md,regions/paphos.md,themes/ancient-sites.md}
PYTHONPATH=tools uv run --with boto3 python tools/build_okf.py
```

Result: 7 wiki files changed, lint still 0 errors 0 warnings, still 27 files.
The feared dilution did not occur - both pages became more specific, not more
generic. No content was added by hand.

### Probe results after the rebuild

| Probe | Tool calls | Change |
| --- | --- | --- |
| near Limassol | `read_wiki /regions/index.md`, `read_wiki /regions/limassol.md` | same trace, Kourion blurb now names the theatre |
| Roman mosaics | `search_wiki`, `read_wiki /sites/paphos-archaeological-park.md`, `read_wiki /sites/kourion.md` | now finds BOTH sites. Kourion's House and Baths of Eustolios mosaics were missing before - a real gap, not a stylistic one |
| Kourion theatre | `read_wiki /sites/kourion.md` | one call, no search detour. Full answer: late 2C BCE, enlarged under Trajan, 3,500 spectators |
| Crete beaches | none | unchanged, still refuses |

20 tests still pass.
