# Cyprus LLMWiki

Throwaway prototype. Not production code. No support, no versioning.

It answers one design question: can an agent stay grounded if its **only**
source is a local markdown wiki?

A 15-attraction Cyprus wiki in [OKF](https://github.com/GoogleCloudPlatform/open-knowledge-format)
v0.2 markdown, plus a Strands agent on Bedrock AgentCore that answers **only**
by navigating that wiki.

Three separate programs:

| Program | When | Needs |
| --- | --- | --- |
| fetch | build time | network |
| build | build time | AWS Bedrock |
| serve | query time | AWS Bedrock |

The builder never runs at query time. The agent never calls Wikipedia.

---

## Prerequisites

| Item | Version |
| --- | --- |
| Python | 3.10+ |
| `uv` | 0.11.16 |
| Node | 20+ (for the `agentcore` CLI) |
| `agentcore` CLI | 0.29.0 |
| AWS credentials | Bedrock access, `eu-central-1` |
| Model | `global.anthropic.claude-sonnet-4-5-20250929-v1:0` |

`uv` pulls every Python dependency per command. Do not make a venv.

---

## Layout

Working directory for all commands is `prjLLMWikiTest/`.

| Path | Holds |
| --- | --- |
| `tools/` | fetch, build and lint scripts. Build time only. |
| `raw/` | Wikipedia plaintext, 15 `*.json`. Fetch output. |
| `app/CyrpusLLMWikiAgent/wiki/` | the OKF bundle, 27 `*.md`. Build output. |
| `app/CyrpusLLMWikiAgent/wiki_nav/` | the 3 agent tools. Query time only. |
| `tests/` | 20 tests. No AWS, no network. |

`tools/sites.py` is the single source of truth for the 15 sites, 5 regions and
3 themes. `title` is the Wikipedia article title the fetcher needs. Optional
`display` overrides the name shown in the wiki; only `apollo-hylates` uses it.

Bundle shape: 15 sites + 5 regions + 3 themes + 4 `index.md` = 27 files.

---

## Pipeline

Run the steps in order. Each has a gate. Do not continue past a failed gate.

### 1. Fetch Wikipedia plaintext

Network. No LLM, no AWS.

```bash
uv run --with certifi python tools/fetch_wikipedia.py
```

`certifi` is **required**. The default CA store on this machine has an expired
root and rejects the Wikipedia certificate.

The script throttles 2 s between requests and backs off on HTTP 429. It skips
files that exist. Use `--force` to refetch.

Gate: 15 files in `raw/`, every extract longer than 1000 characters.

```bash
uv run python -c "
import json,glob
sz=[len(json.load(open(p,encoding='utf-8'))['extract']) for p in glob.glob('raw/*.json')]
print('files',len(sz),'min',min(sz),'max',max(sz))"
```

Expect `files 15 min 1818 max 31994`.

### 2. Build the OKF bundle

Needs AWS Bedrock.

```bash
PYTHONPATH=tools uv run --with boto3 python tools/build_okf.py
```

`PYTHONPATH=tools` is **required**. The script imports `sites.py`.

Two passes: 15 attraction pages, then 5 region and 3 theme hubs, then the 4
`index.md` files. The 23 LLM pages are skipped if they exist; `--force`
rebuilds all 23. The 4 indexes are deterministic and always rewritten.

Gate: 23 `ok` lines on a cold run, then `ok    index.md x4`.

A warm run prints 23 `skip` lines and the same `ok    index.md x4`.

### 3. Lint the bundle

No AWS.

```bash
uv run --with pyyaml python tools/lint_okf.py
```

Gate: `0 error(s), 0 warning(s)`, exit 0.

```bash
find app/CyrpusLLMWikiAgent/wiki -name "*.md" | wc -l
```

Gate: `27`.

### 4. Tests

No AWS.

```bash
uv run --with pytest --with pyyaml --with strands-agents pytest tests/ -v
```

Gate: `20 passed`.

---

## Run the agent

Needs AWS. Terminal 1:

```bash
agentcore dev
```

It prints the port it chose. It does **not** always get 8080. If 8080 is busy
it reports e.g. `Port 8081 in use, using 8085`. Read the port off that line.
Every invoke must use it.

Output looks like:

```
Starting dev server...
Agent: CyrpusLLMWikiAgent
Server: http://localhost:8080/invocations
```

Terminal 2, with the `PORT` from terminal 1:

```bash
agentcore dev --port 8080 -H "X-Agentcore-Local: 1" "What can I see near Limassol?"
```

### CLI gotchas

`agentcore` here is v0.29.0.

| Symptom | Cause | Fix |
| --- | --- | --- |
| `error: unknown option '--dev'` then help text | `agentcore invoke --dev '{"prompt": "..."}'` is older syntax. `--dev` does not exist and a positional JSON payload is not parsed. | Local invoke is `agentcore dev [prompt]`. |
| `Forbidden: missing X-Agentcore-Local header` | The dev server rejects the local call. Seen earlier in this project; it did **not** reproduce against a server started with `agentcore dev --logs`, so it depends on how the server was started. | Always send `-H "X-Agentcore-Local: 1"`. It is harmless when not needed. |
| `Error: This command requires an interactive terminal.` | Bare `agentcore dev` wants a TTY. | With no TTY (CI, a captured pipe) use `agentcore dev --logs`. |
| `error: Failed to spawn: agentcore` / `program not found` | On git-bash `agentcore` resolves to an npm bash shim that `uv run` cannot spawn. | Call the `.cmd` shim directly: `"$(npm config get prefix)/agentcore.cmd"` |

---

## Does it work?

Four acceptance probes. All pass. Full traces are in the plan's
`## Probe results` section.

| Ask | Expected | Why it matters |
| --- | --- | --- |
| `What can I see near Limassol?` | Names all 4 Limassol sites. Reads `/regions/index.md` then `/regions/limassol.md`. | Hub navigation works. |
| `Where can I see Roman mosaics?` | Finds Paphos Archaeological Park **and** Kourion. | Content is complete, not truncated. |
| `Tell me about Kourion's theatre.` | One `read_wiki` on `/sites/kourion.md`. Late 2C BCE, enlarged under Trajan, 3,500 spectators. | Detail survived the build. |
| `Tell me about the best beaches in Crete.` | **REFUSES.** Zero tool calls. | **The grounding test.** The wiki has no Crete content, so the agent must say so and stop. This is the whole point of the prototype. |

If the Crete probe answers instead of refusing, the prototype has failed.

Every answer ends with the wiki paths that were read. Use that to audit it.

---

## Rebuild one page

The least obvious thing in this project. Read it before you rebuild.

Each site's `description` is **copied** into the hubs and indexes that list it.
`build_hubs` skips files that exist. So if you rebuild one site page, the hubs
keep a stale copy of its description.

The linter cannot catch this. The links still resolve, so lint stays
`0 error(s), 0 warning(s)` and nothing warns you.

The 3 directory `index.md` files self-heal, because `build_indexes` always
rewrites.

**Rule:** delete the site page **and** every hub that lists it.

Worked example, the rebuild actually done at `05ec5cb` after raising
`CHAR_BUDGET`:

```bash
rm app/CyrpusLLMWikiAgent/wiki/sites/{kourion,paphos-archaeological-park}.md
rm app/CyrpusLLMWikiAgent/wiki/{regions/limassol.md,regions/paphos.md,themes/ancient-sites.md}
PYTHONPATH=tools uv run --with boto3 python tools/build_okf.py
```

5 LLM calls, not 23. The other 22 files stay byte-identical.

---

## Notes

- `CHAR_BUDGET` in `tools/build_okf.py` is 36000. Chosen so no extract is
  truncated; the largest is Kourion at 31994 characters. At the original 12000
  the Kourion page silently lost the theatre and the Eustolios mosaics. The
  loss was silent: lint stayed 0/0.
- The agent is jailed to `WIKI_ROOT` (env var, else `wiki/` next to
  `main.py`). Any path that escapes the root is rejected.
- The bundle root `index.md` is inlined into the system prompt at import. That
  is why the agent never calls `list_wiki` on the root. It costs ~300 tokens
  and saves one tool call per query.
- All 124 bundle links start with `/` and resolve against the bundle root.
  OKF `SPEC.md` calls this the recommended form.
- `prjLLMWikiTest/README.md` is AgentCore CLI boilerplate. It is not about
  this project.
