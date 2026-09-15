# Cyprus LLMWiki Prototype — Design

Date: 2026-09-15
Status: approved, ready for implementation plan

## 1. Goal

Learn the LLM-wiki pattern and Google's Open Knowledge Format (OKF) by hand-building a small knowledge base about Cyprus tourist attractions, and connecting the existing Strands/AgentCore agent to it.

Success = the agent answers Cyprus questions by **navigating markdown files**, and you can see in the trace which files it opened.

## 2. Non-goals

- No vector search, embeddings, or Bedrock Knowledge Base.
- No AWS deployment. Local `agentcore dev` only.
- No production quality. This is a throwaway learning prototype.
- No use of Google's `reference_agent enrich` (see 3.3).

## 3. Background — what OKF actually is

### 3.1 Spec facts (v0.2)

| Item | Rule |
| --- | --- |
| Bundle | A directory tree of `.md` files. Nothing else. |
| Concept doc | YAML frontmatter + markdown body. File path = concept identity. |
| Required field | `type` only. Must be non-empty. |
| Recommended fields | `title`, `description`, `resource`, `tags` |
| Optional families | trust/provenance (`generated`, `verified`, `sources`, `status`, `stale_after`), attested computation (`runtime`, `parameters`, `computation`, `executor`, `attester`) |
| Reserved filenames | `index.md` (progressive disclosure), `log.md` (change history) |
| Links | Ordinary markdown links. Bundle-relative paths start with `/`. |
| Version declaration | `okf_version: "0.2"` in the bundle-root `index.md` frontmatter only |
| Unknown keys | Allowed. Consumers MUST NOT reject them. |

Conformance: every non-reserved `.md` parses as frontmatter + body, and carries a non-empty `type`. Consumers MUST tolerate broken links, unknown `type` values, unknown keys, and missing `index.md`.

### 3.2 The pattern

An LLM wiki is **navigation, not retrieval**. The agent holds a table of contents in context, follows links to reach specifics, and reads whole documents. There is no chunking and no similarity score. OKF is the minimal set of conventions that let one producer's wiki be read by a different consumer's agent.

### 3.3 Why we do not use Google's reference agent

`reference_agent enrich` is anchored to BigQuery. Its web pass only follows seed URLs to find documentation for concepts it already extracted from a BQ dataset. With no BQ dataset there are no concepts, so nothing is produced. It also needs `GEMINI_API_KEY` or Vertex AI.

`reference_agent visualize` works on any conformant bundle. We use it as an optional final step.

## 4. Architecture

```
Wikipedia --fetch_wikipedia.py--> raw/*.json --build_okf.py--> wiki/**.md
  (REST API, no LLM)              (plaintext)   (Bedrock/Claude,       |
                                                 1 call per page)      |
                                                                       |
                       +-----------------------------------------------+
                       v
  agentcore dev --> main.py --> Agent(system_prompt = role + wiki/index.md inlined)
                                  +-- tools: list_wiki . read_wiki . search_wiki
                                                |
                                                +-- read-only, WIKI_ROOT-jailed
```

Three separate programs. The builder never runs at query time. The agent never calls Wikipedia. This is the producer/consumer split OKF is designed around.

## 5. File layout

```
prjLLMWikiTest/
+-- raw/                        # committed - makes builds reproducible
|   +-- kourion.json ...
+-- tools/                      # build-time only, deps via `uv run --with`
|   +-- sites.py                # the site manifest - single source of truth
|   +-- fetch_wikipedia.py
|   +-- build_okf.py
|   +-- lint_okf.py
+-- app/CyrpusLLMWikiAgent/
    +-- wiki/                   # the OKF bundle; WIKI_ROOT defaults here
    |   +-- index.md            # okf_version: "0.2"
    |   +-- regions/  index.md + paphos, limassol, larnaca, troodos, famagusta
    |   +-- sites/    index.md + 15 attraction docs
    |   +-- themes/   index.md + ancient-sites, monasteries, beaches-nature
    +-- wiki_nav/tools.py       # the 3 agent tools
```

`wiki/` lives inside the app directory so a later `agentcore deploy` includes it in the CodeZip with no file moves.

## 6. Content

15 sites, all in government-controlled areas.

| Region | Sites |
| --- | --- |
| Paphos | Paphos Archaeological Park, Tombs of the Kings, Petra tou Romiou, Agios Neophytos Monastery |
| Limassol | Kourion, Sanctuary of Apollo Hylates, Kolossi Castle, Limassol Castle |
| Larnaca | Church of Saint Lazarus, Hala Sultan Tekke, Choirokoitia, Larnaca Salt Lake |
| Troodos | Kykkos Monastery, Painted Churches of Troodos |
| Famagusta | Cape Greco |

Sites in the north (Kyrenia Castle, Bellapais Abbey, Saint Hilarion) are excluded. They need careful neutral framing about de facto administration, which adds nothing to a format prototype.

Hub documents: 5 regions + 3 themes. They are short and exist to be link targets, so that progressive disclosure and the link graph are real and not a star topology.

## 7. Document schema

Types: `attraction`, `region`, `theme`.

Attraction document:

```yaml
---
type: attraction
title: Kourion
description: Greco-Roman city-state on a clifftop west of Limassol.
resource: https://en.wikipedia.org/wiki/Kourion
tags: [archaeological, roman, mosaics]
region: /regions/limassol.md
themes: [/themes/ancient-sites.md]
---
# Overview
# History
# What to see
# Location & access
# Related
- [Sanctuary of Apollo Hylates](/sites/apollo-hylates.md) - 3 km west
```

`region` and `themes` are producer-defined keys. The spec permits them, and using them demonstrates that an OKF consumer must tolerate keys it does not know.

Region and theme documents: same frontmatter minus `region`/`themes`, body is a one-paragraph orientation plus a list of links to member sites.

Root `index.md`: `okf_version: "0.2"`, one line per top-level directory, and a short statement of what the bundle covers.

## 8. Build pipeline

All three scripts run from `prjLLMWikiTest/` as the working directory.

### 8.0 `tools/sites.py`

A plain Python list of 15 records, one per site. This is the single source of truth for
both scripts:

```python
{"title": "Kourion", "slug": "kourion",
 "region": "limassol", "themes": ["ancient-sites"]}
```

Region and theme assignment is a curation decision, so it is fixed here by hand and not
left to the model. The hub documents in pass 2 are generated by inverting this list.

### 8.1 `tools/fetch_wikipedia.py`

- Input: the titles in `tools/sites.py`.
- Calls `en.wikipedia.org/w/api.php` with `action=query&prop=extracts|coordinates&explaintext=1`.
- Writes `raw/<slug>.json` holding title, canonical URL, coordinates, full plaintext.
- stdlib `urllib` only. No third-party dependency.
- Skips titles already fetched unless `--force`.

### 8.2 `tools/build_okf.py`

- Reads `raw/*.json`, sends each to Claude on Bedrock with an OKF-shaped prompt.
- Writes `wiki/sites/<slug>.md`.
- Two passes: sites first, then region/theme hubs, so hub links point at filenames that already exist.
- Idempotent. Skips existing output unless `--force`.
- Truncates each extract to a fixed character budget before the model call.
- Run with `uv run --with boto3 tools/build_okf.py`. The agent's `pyproject.toml` is not modified.

**Hallucination guard.** The builder prompt is restricted to the supplied extract and explicitly forbidden from inventing opening hours, ticket prices, or transport times. Content stays historical and geographic. `resource` always cites the source page.

### 8.3 `tools/lint_okf.py`

Checks the spec conformance criteria:

1. Every non-reserved `.md` has parseable YAML frontmatter. **Error** if not.
2. Every one has a non-empty `type`. **Error** if not.
3. Bundle-relative links resolve. **Warning** only — the spec requires consumers to tolerate broken links, but a producer wants to know.

## 9. Agent tools

Three `@tool` functions in `app/CyrpusLLMWikiAgent/wiki_nav/tools.py`. `pathlib` only, no new dependencies.

| Tool | Signature | Returns | On failure |
| --- | --- | --- | --- |
| `list_wiki` | `(path: str = "/")` | directories and files at path | listing of nearest valid parent |
| `read_wiki` | `(path: str)` | raw file text, frontmatter included | `not found` + listing of that directory |
| `search_wiki` | `(query: str)` | up to 20 `path:line` hits, case-insensitive | `no matches` + root listing |

Two deliberate decisions:

- **Frontmatter is not stripped on read.** The agent uses `type`, `tags`, `region`, and `themes` to decide where to go next. Hiding metadata defeats the exercise.
- **Errors return guidance, never raise.** A wrong path returns a directory listing so the agent self-corrects in one turn.

Path safety: resolve every path under `WIKI_ROOT` and reject anything that escapes. Use the same approach as `skills/fetcher.py`.

`WIKI_ROOT` env var, default = `wiki/` next to `main.py`.

## 10. Changes to `main.py`

Surgical. Everything not listed stays as it is.

| Change | Reason |
| --- | --- |
| Delete `add_numbers` | placeholder |
| Delete `mcp_client` import and `mcp_clients` list | points at Exa web search. An external search tool lets the agent answer around the wiki, which hides whether navigation works. |
| `tools = wiki_tools` | the three navigation tools |
| Rewrite `DEFAULT_SYSTEM_PROMPT` | role, navigation protocol, and `wiki/index.md` inlined at import |

Untouched: session agent cache, `strip_trailing_tool_use`, `_extract_prompt`, streaming entrypoint.

The root index is inlined because it costs about 300 tokens and saves one tool call on every query. It also matches the original pattern: the table of contents stays in context, the pages do not.

System prompt rules:

1. Start from the index in this prompt.
2. Follow links to reach specifics. Use `search_wiki` only when no link path is obvious.
3. Answer only from file content. If the wiki does not cover it, say so. Do not fall back on model knowledge.

Rule 3 makes the prototype legible — you can tell whether an answer came from the wiki.

## 11. Verification

### 11.1 Automated

- `python tools/lint_okf.py` exits non-zero on a conformance error.
- pytest, narrow scope:
  - `list_wiki` and `read_wiki` reject a path that escapes `WIKI_ROOT`
  - `read_wiki` on a missing file returns a directory listing, does not raise
  - the linter fails a document with a missing `type`
- No tests over model output.

### 11.2 Manual probes

After `agentcore dev`, invoke with `agentcore invoke --dev`:

| Probe | Must force |
| --- | --- |
| "What can I see near Limassol?" | index -> region hub -> sites |
| "Which sites have Roman mosaics?" | theme hub or `search_wiki` |
| "Tell me about Kourion's theatre" | direct link path, one deep read |
| "What are the best beaches in Crete?" | refusal — proves the grounding rule |

Check the trace for the tool calls, not only the answer text.

### 11.3 Optional final step

Clone `GoogleCloudPlatform/open-knowledge-format` and run `python -m reference_agent visualize --bundle <path to wiki>` to render the bundle as an interactive graph. Confirms the bundle is readable by a consumer we did not write.

## 12. Risks

| Risk | Mitigation |
| --- | --- |
| Builder invents practical facts | prompt restricted to the extract, no hours/prices/fares |
| Cross-links point at files never built | two-pass build; linter warns |
| Long extracts (Paphos Park is about 8k words) | truncate to a character budget per page |
| Repeated build cost | idempotent, `--force` to rebuild |
| Agent answers from model knowledge, not the wiki | system prompt rule 3 + the Crete probe |

## 13. Decisions taken

| Decision | Chosen | Rejected |
| --- | --- | --- |
| Retrieval | filesystem navigation | Bedrock Knowledge Base (vector RAG); both side by side |
| Build method | script calling Bedrock | in-session hand authoring; deterministic no-LLM transform |
| Structure | typed and cross-linked | flat; typed plus full provenance fields |
| Runtime | local `agentcore dev` only | local then deploy; deploy from the start |

## 14. References

- OKF spec v0.2: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md
- Repo and reference agent: https://github.com/GoogleCloudPlatform/open-knowledge-format
- Google Cloud announcement: https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing
