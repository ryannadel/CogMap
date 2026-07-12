---
name: build-cogmap
description: >-
  Incrementally re-ingest notes (Markdown, plain text, or optional OneNote .onex)
  and build/refresh the CogMap Minard-style Knowledge Base visualization
  (an interactive knowledge-base-viz.html). Use when the user says "build the
  knowledge base", "refresh the knowledge base", "update the visualization",
  "re-ingest my notes", "add these notes", "I changed the notes", "rebuild the
  knowledge map", or points at note files to add. Only the chunks that actually
  changed are re-extracted. Runs a resumable one-command orchestrator and spawns
  extraction / resolution / synthesis sub-agents (or runs those stages itself)
  only when the delta requires it. No API key needed — the host coding agent is
  the LLM in the loop.
---

# Build CogMap

This skill is **self-contained**: the whole pipeline ships inside it, so it runs
standalone wherever the skill is installed (no separate checkout required). It
re-ingests notes **incrementally** — only re-extracting chunks whose text changed,
re-clustering only new concept names, re-synthesizing insights only when the graph
changed — then builds a self-contained HTML artifact.

## Locate the pipeline

The engine lives next to this `SKILL.md`, in `scripts/`. The entry point is
`scripts/refresh.py`. Resolve it **relative to this skill directory** — do not
hardcode any repo name. If you are unsure of the absolute path, glob for
`**/build-cogmap/scripts/refresh.py`.

Everything else resolves automatically via `scripts/cogmap_paths.py` (using
`__file__`), so you never pass absolute paths on the command line.

```
build-cogmap/            <- this skill
  SKILL.md
  scripts/               engine: refresh.py + stage scripts
  assets/demo/           bundled demo corpus + prebuilt artifacts (seed data)
  requirements.txt
```

## The workspace (where the user's data lives)

Runtime data is written to a **project-local workspace**, never into the skill
folder. It defaults to `./cogmap` under the current working directory and is
auto-created + seeded from `assets/demo/` on first run:

```
cogmap/                  <- the workspace (in the user's working dir)
  sources/    the user's notes — any .md / .txt files (optional .onex helper)
  work/       extractions + resolved + insights + cache (LLM artifacts)
  output/     knowledge-base-viz.html + knowledge-base-viz-data.json  <- deliverable
```

Run `refresh.py` from a stable directory (e.g. the user's project root) so the
`./cogmap` workspace is predictable. On startup `refresh.py` prints the resolved
workspace paths — use those when reporting the deliverable location. To relocate
the workspace explicitly, set `COGMAP_APP` (or the finer `COGMAP_SOURCES` /
`COGMAP_WORK` / `COGMAP_OUTPUT`; legacy `OSLER_*` names still accepted).

## Environment rules

- Python 3.10+ (no third-party deps for `.md`/`.txt`). `olefile`
  (`pip install -r requirements.txt`) is only needed for the optional `--from-onex`
  OneNote converter. On Windows use `python3.12`; elsewhere `python`/`python3`.
- Always set `PYTHONIOENCODING=utf-8` before running (Unicode-heavy notes).
- Sub-agents must read batch JSON with `json.load`, **not** a file-view tool
  (batches exceed 20KB and get truncated).

## Source of truth

The pipeline ingests **every `.md` / `.txt` file in the workspace `sources/`**
(any filename; `README.md` is ignored). It works with notes from any tool —
Markdown/plain-text exports from Obsidian, Notion, Logseq, Apple/Google Notes,
journals, meeting notes, etc. The chunker auto-detects prose-paragraph vs
one-entry-per-line format, and picks up a date near the top of each note
(`2025-03-14`, `March 2025`, …) for the timeline; otherwise reading order is used.

OneNote is supported via an **optional** converter: `refresh.py --from-onex`
best-effort extracts any `.onex` in `sources/` to clean text first (OLE2 package,
only ~66% of prose recoverable — warn the user before relying on it; a clean
`.md`/`.txt` export is always higher fidelity).

## Adding the user's notes

When the user wants to add notes, put them in the workspace `sources/` and refresh:
- If they give a **path**, copy the file(s) into `<workspace>/sources/`.
- If they **paste** text, write it to a new `<workspace>/sources/<slug>.md` (or `.txt`).
- Encourage a date near the top of each note for a chronological timeline.
- Remove the seeded `sources/sample-notes.txt` once real notes are added (it's a
  synthetic demo corpus, not user content). Adding real notes also triggers the
  pipeline's foreign-corpus reset, which clears the demo's resolved/insight files.

Then run the loop below. See `sources/README.md` in the workspace for the
user-facing guide.

## The operational loop

`refresh.py` is a resumable state machine:
- **exit 0** — done. Report the final counts and tell the user to hard-refresh.
- **exit 10** — an LLM stage is required. Details are in the workspace at
  `work/refresh_cache/action.json` (`{"action": "extract"|"resolve"|"synth", ...}`;
  all file paths inside are absolute). Handle the stage (see below), then **re-run
  the same command**. Repeat until exit 0.

Run it (from the user's working dir; paths self-resolve):
```
PYTHONIOENCODING=utf-8 python <skill>/scripts/refresh.py --with-resolve --with-synth
```

Flags:
- `--with-resolve` — on concept-set change, cluster new names into existing/new
  canonical concepts (best quality). Without it, assemble uses a lossless singleton
  fallback (new concepts appear un-merged).
- `--with-synth` — on graph change, refresh insight narratives + synthesis cards.
  Without it, existing insights are reused.
- `--from-onex` — best-effort re-extract `.onex` → clean text first (~66%).
- `--skip-resolve`, `--skip-synth` — force-skip those gates.
- `--no-open` — don't auto-open the finished HTML (also via `COGMAP_NO_OPEN=1`).
- `--publish-github-pages` — after a successful build, publish the visualization
  to a `gh-pages` branch and configure GitHub Pages when `gh` is authenticated.
  Optional controls: `--publish-remote <name>` (default `origin`),
  `--publish-branch <name>` (default `gh-pages`), `--publish-path <path>` for a
  subdirectory, `--publish-no-push` for a local dry run, and
  `--publish-no-enable-pages` to skip Pages API configuration.

**Default recommendation:** `--with-resolve --with-synth` so a real content change
yields fully-merged concepts and fresh insights. Read `action.json` after every
exit-10, handle the stage, re-run. Never hand-edit pipeline outputs.

### Handling the LLM stages

Each stage below can be run **by dispatched sub-agents** or **by you directly** —
whatever your host tool supports. If your tool can fan out parallel sub-agents
(e.g. one per extraction batch), do so for speed; otherwise process the batches
sequentially yourself. Use a capable general model for extraction and a
higher-reasoning setting for resolve/synth when available.

---

## Stage 1 — Extraction (`action == "extract"`)

`action.json` has `batches: [{input, output, chunk_ids}]`. For **each** batch,
read its `input` file and write its `output` file (parallel sub-agents if
supported, else sequential). Prompt / task (fill INPUT/OUTPUT):

> Read the JSON array at `INPUT` using `json.load` (do NOT use a view tool — it
> truncates). Each element is a note chunk: `{chunk_id, order, source, heading,
> date, text}`. Extract a knowledge graph **grounded only in this text**. Write a
> single JSON object to `OUTPUT` with exactly these keys:
> - `concepts`: `[{name, type, definition, aliases:[...], chunk_ids:[...]}]` —
>   `type` ∈ Technology|Method|Concept|Organization|Person|Product|Metric|Risk|Theme.
>   Every `chunk_ids` value MUST be a `chunk_id` present in this batch.
> - `claims`: `[{text, status, concepts:[names], chunk_id, date}]` —
>   `status` ∈ Observation|Prediction|Decision|Question|Tension.
> - `relations`: `[{source, target, type, evidence_chunk_ids:[...], rationale}]` —
>   `type` ∈ enables|causes|depends_on|part_of|refines|competes_with|contradicts|relates_to.
>   `source`/`target` are concept `name`s that appear in `concepts`.
> Deduplicate names within the batch; use canonical noun-phrase names. Only
> reference chunk_ids from this batch. Output valid UTF-8 JSON, nothing else.

When all outputs exist, re-run `refresh.py` — it auto-ingests them.

## Stage 2 — Incremental resolve (`action == "resolve"`)

`action.json` has `existing` (`work/v3_resolved.json`), `new_names`
(`work/refresh_cache/resolve_new_names.json`), `uncovered` (count). Handle with a
single higher-reasoning pass:

> Read `v3_resolved.json` (existing canonical concepts: `canonical`, `category`,
> `members:[raw names]`) and `resolve_new_names.json` (new raw names not yet
> covered). For EACH new name, either add it to the `members` of the best-matching
> existing concept, or create a new concept with `canonical` (clean noun phrase),
> `category`, and `members`. For `category`: reuse an existing category string
> exactly when one fits; otherwise coin a concise thematic category (a few words).
> Aim for ~5–10 balanced categories overall — enough to form meaningful Minard
> lanes, not one lane per concept. Do not drop or duplicate any name; every new
> name ends up in exactly one concept. Write the merged result back to
> `v3_resolved.json` as a JSON **object** with a top-level `concepts` key —
> exactly `{"concepts": [{"canonical": ..., "category": ..., "members": [...]}, ...]}`
> (NOT a bare array). Prefer merging near-duplicates over creating singletons.

Then re-run `refresh.py --with-resolve`.

## Stage 3 — Synthesis (`action == "synth"`)

`action.json` has `synth_input` (`work/v3_synth_input.json`). Handle with a single
higher-reasoning pass:

> Read `v3_synth_input.json` (keys: `concepts`, `evolves_into`, `enables`,
> `contradictions`, `existing_insight_candidates`, `categories`). Reason over the
> resolved graph and write `v3_insights.json`: polished insight objects plus
> cross-cutting **synthesis cards** that connect ≥2 concepts across categories and
> surface an emergent, non-obvious pattern (idea evolution, tension, or
> convergence). Each item must reference real concept ids/canonicals from the
> input so provenance derives deterministically. Keep narratives tight and
> grounded in the supplied graph.

Then re-run `refresh.py --with-synth`.

---

## When done

On exit 0, report the final line (`DONE. chunks=… tracked-extracted=…`). The
finished `output/knowledge-base-viz.html` is **auto-opened in the default browser**
(disable with `--no-open` or `COGMAP_NO_OPEN=1`). If it was already open, tell the
user to **hard-refresh the browser (Ctrl+Shift+R)** — for large corpora the
embedded page can be 1 MB+ and can't be reloaded from the agent side.

If the user asks to share or publish the map publicly, re-run the final refresh
with `--publish-github-pages` from a GitHub-backed repository. The publisher copies
`knowledge-base-viz.html` to `index.html` on the Pages branch, includes the data
JSON and a small manifest, pushes the branch, and prints the Pages URL when it can
parse the GitHub remote. If automatic Pages enablement fails, report the printed
warning and the branch it pushed so the user can enable Pages manually.

## Notes

- First run **seeds the workspace** from the bundled demo (`assets/demo/`) and
  seeds the extraction baseline from whatever extractions already cover the
  current notes: a fresh install left unchanged is a no-op (renders the demo), but
  if the user has swapped in their own notes those chunks aren't covered, so
  extraction is triggered for them.
- The seeded `sources/sample-notes.txt` + its extractions/resolution/insights are
  a **synthetic demo** so a fresh install renders immediately. They are replaced
  the moment the user adds real notes and refreshes.
- Correctness mechanism: `v3_aggregate.py` filters extractions by the current
  chunk IDs, so stale extractions for edited/removed chunks are auto-dropped.
  Chunk IDs are content-only (position-independent), so mid-file edits don't cascade.
- Engine scripts: `scripts/refresh.py` (orchestrator), `v3_prep.py`,
  `v3_aggregate.py`, `v3_assemble.py`, `build_v2.py`, `extract_onex.py`.
