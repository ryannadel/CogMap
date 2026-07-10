# CogMap Knowledge Base App

A **portable, self-contained skill** for navigating the growing flood of
information that people and agents produce. CogMap treats a knowledge base not as
a folder of documents, but as an evolving external memory system: it helps you see
what the corpus contains, how ideas relate, what changed, what matters, what
conflicts, what is missing, and where attention should go next.

The visualization combines **timeline + events + trends in one view** (à la
Minard): it shows how ideas flow from source notes into synthesized concepts,
branch into themes, decisions, questions, and gaps, converge into insights, or
fade into stale unresolved knowledge. Every claim remains traceable back to its
source snippet, with a click-through to read the full note.

It installs into **GitHub Copilot CLI**, **Claude Code**, and **OpenAI Codex CLI**,
so the extraction/rebuild pipeline runs *in the loop* with your coding agent (no
LLM API key required).

It works with **any plain-text notes** — Markdown (`.md`) or text (`.txt`) — from
any tool (Obsidian, Notion/Logseq exports, Apple/Google Notes, a journal, meeting
notes…). OneNote `.onex` is supported via an optional converter. A synthetic demo
corpus ships inside the skill so a fresh install renders immediately; it is
replaced the moment you add your own notes.

## What's in the box

The pipeline is **bundled inside the skill** (`skills/build-cogmap/`), so the skill
installs standalone in any of the three tools — no separate checkout required.

```
cogmap-app/                          Claude Code plugin root
├─ README.md                         this file
├─ requirements.txt                  olefile (only for --from-onex)
├─ .gitignore
├─ .claude-plugin/plugin.json        Claude Code plugin manifest
└─ skills/build-cogmap/              THE skill (self-contained)
   ├─ SKILL.md                       instructions + agent prompts
   ├─ requirements.txt
   ├─ scripts/                       the data-processing engine
   │  ├─ cogmap_paths.py             central path resolver (engine vs. workspace)
   │  ├─ refresh.py                  one-command, resumable orchestrator
   │  ├─ v3_prep.py                  chunker (sources → chunks, any .md/.txt)
   │  ├─ v3_aggregate.py             merge extractions → raw concepts
   │  ├─ v3_assemble.py              build the graph data JSON
   │  ├─ build_v2.py                 render the self-contained HTML
   │  └─ extract_onex.py             optional: OneNote .onex → clean text (~66%)
   └─ assets/demo/                   bundled demo corpus + prebuilt artifacts
      ├─ sources/sample-notes.txt    synthetic demo corpus
      ├─ work/…                      demo extractions / resolution / insights
      └─ output/…                    prebuilt knowledge-base-viz.html + data
```

### Engine vs. workspace

The **engine** (the `scripts/` folder) is immutable and lives in the skill. Your
**data** lives in a separate, project-local **workspace** so an installed skill
never writes notes or output into a shared skill directory. The workspace defaults
to `./cogmap` under the directory you run from, and is **auto-created and seeded
from the bundled demo** on first run:

```
cogmap/                              the workspace (created in your working dir)
├─ sources/   ← drop YOUR notes here (.md / .txt; optional .onex)
├─ work/      extractions + resolution + insights (+ cache)
└─ output/    ← the deliverable: knowledge-base-viz.html (+ data json)
```

Relocate the workspace with `COGMAP_APP` (or the finer `COGMAP_SOURCES` /
`COGMAP_WORK` / `COGMAP_OUTPUT`; legacy `OSLER_*` names still accepted).

## Quick start (run it with a coding agent)

CogMap is a **coding agent skill**, not a standalone app you run by hand:

1. Install the skill in your agent (see below), or open this checkout in the agent.
2. Tell the agent: *"build the knowledge base"* (or *"refresh the knowledge base"*).
   On first run it seeds `./cogmap` from the demo and renders it.
3. To use your own notes, tell the agent *"add my notes from `<path/or/paste>`"* —
   it writes them into `cogmap/sources/`, removes the demo corpus, and refreshes.
4. Open `cogmap/output/knowledge-base-viz.html` when the agent reports completion
   (the agent prints the exact workspace path on every run).

`refresh.py` diffs the notes, re-extracts **only the chunks that changed**,
re-clusters **only new concepts**, re-synthesizes insights **only if the graph
moved**, then rebuilds the HTML. When an LLM stage is needed it writes the inputs,
prints an `ACTION` block, and exits `10`; the agent handles that stage and re-runs
until exit `0`. See `skills/build-cogmap/SKILL.md` for the full loop and the three
agent prompt templates.

Under the hood, CogMap uses agents as temporary cognitive workers while the
Python pipeline remains the durable system of record. Extraction can fan out
across multiple sub-agents — one per changed batch — while separate
higher-reasoning passes handle concept resolution and synthesis.

> **`.onex` note:** direct OneNote `.onex` re-extraction recovers only ~66% of
> prose. For full fidelity, supply a clean `.md`/`.txt` export instead. Ask the
> agent to use `--from-onex` only for `.onex`-only updates.

## Install as a GitHub Copilot CLI skill

Copy the self-contained skill folder into your Copilot skills directory:

```bash
cp -r skills/build-cogmap ~/.copilot/skills/
```

(On Windows: copy `skills\build-cogmap` to `%USERPROFILE%\.copilot\skills\`.)
Then say *"build the knowledge base"*.

## Install as a Claude Code plugin

This repo is a Claude Code marketplace (`.claude-plugin/marketplace.json` at the
repo root) exposing the `cogmap-app` plugin. In Claude Code:

```
/plugin marketplace add <your-github-org>/CogMap
/plugin install cogmap-knowledge-base@cogmap
```

The `build-cogmap` skill (with its bundled `scripts/` and `assets/`) is copied into
Claude's plugin cache and becomes available automatically.

## Install in OpenAI Codex CLI

Codex discovers agent skills under `.agents/skills`. This repo ships a copy at
`.agents/skills/build-cogmap/` (kept in sync with the canonical skill). Open the
repo in Codex, or copy that folder to `~/.agents/skills/` for a user-wide install,
then ask Codex to *"build the knowledge base"*.

## Keeping the copies in sync

The canonical skill is `cogmap-app/skills/build-cogmap/`. The Codex copy under
`.agents/skills/build-cogmap/` is regenerated from it:

```bash
python cogmap-app/tools/sync_skill.py          # regenerate the .agents copy
python cogmap-app/tools/sync_skill.py --check   # CI/pre-commit drift check
```

## How it stays correct

- **Content-only chunk IDs** — mid-file edits don't cascade; only truly changed
  chunks are re-extracted.
- **Valid-ID filtering** — `v3_aggregate.py` keeps only extractions whose chunk
  IDs still exist, so stale extractions for edited/removed notes are auto-dropped.
- **Foreign-corpus reset** — the first time you swap in your own notes, the demo's
  resolved/insight artifacts are cleared so your corpus doesn't inherit demo
  categories.
- **Name-keyed graph** — concepts/insights are keyed by canonical name, so the
  incremental resolve/synth steps merge cleanly into the existing graph.
