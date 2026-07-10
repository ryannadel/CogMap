# CogMap

CogMap is an agent-assisted tool for navigating the tsunami of information that
agents and people produce. As agents generate more content, we need new tools for
thought that help us understand what a knowledge base contains, how ideas relate,
what changed, what matters, what conflicts, what is missing, and where attention
should go next.

CogMap treats a knowledge base not as a folder of documents, but as an evolving
external memory system with time as a key organizing construct. It extracts
concepts, claims, relationships, tensions, gaps, and trends from notes, then
renders them as a self-contained, source-traceable visualization you can open in
any browser.

The goal is to make accumulated knowledge navigable for both people and agents:
map the concepts, trace relationships across sources, surface conflicts and gaps,
notice drift or convergence, and decide where to focus next.

## Status

CogMap is currently an early public-beta project. The bundled demo renders from a
fresh checkout, and the Markdown/text pipeline has automated smoke coverage. The
semantic extraction, resolution, and synthesis stages are intentionally performed
by your coding agent rather than by a hosted API.

## Why Minard?

Charles Joseph Minard's 1869 map of Napoleon's Russian campaign is one of the
classic examples of information design because it compresses several dimensions
into a single readable story: geography, direction of movement, army size,
temperature, and time. The power of the graphic is not just that it shows data,
but that it shows movement, magnitude, direction, change, context, and consequence
together. In Minard's chart, the thickness of a flow represents the number of
surviving troops.

CogMap borrows that visual language for knowledge work. A knowledge base has
flows too:

- ideas flowing from source notes into synthesized concepts
- concepts branching into themes, decisions, questions, and open gaps
- attention moving across topics over time
- stronger and weaker connections between areas of knowledge
- accumulation, loss, drift, and convergence of understanding

In a CogMap, thicker paths represent heavily developed ideas, thinner paths show
weakly supported concepts, branches reveal divergent themes, convergence points
show synthesis, and fading paths mark stale or unresolved knowledge. The result
is a body of notes that feels less like a pile of documents and more like an
evolving landscape of thought.

## What it does

- Ingests Markdown, plain text, and optional OneNote `.onex` note exports.
- Extracts concepts, claims, typed relationships, contradictions, and emergent insights.
- Tracks provenance so nodes and insights link back to the source text.
- Surfaces change, conflict, gaps, and attention-worthy themes across time.
- Rebuilds incrementally, re-processing only changed chunks where possible.
- Ships with a GitHub Copilot / Claude Code skill for agent-assisted refreshes.
- Outputs a portable HTML artifact with embedded data and no server requirement.

## See it in action

A synthetic demo corpus ships inside the skill. On first run, CogMap seeds a
project-local `cogmap/` workspace from that demo and renders:

```text
cogmap/output/knowledge-base-viz.html
```

The generated page is fully local: no server, database, or API key is required.
Replace the demo notes with your own Markdown or text files when you are ready.

## How CogMap uses agents

CogMap is built as a deterministic pipeline with agent-powered semantic stages.
The Python orchestrator handles file discovery, chunking, caching, aggregation,
graph assembly, and HTML rendering. When a semantic step is needed, it emits a
structured action file and lets the host coding agent do the LLM work.

For large corpora, extraction can fan out across multiple sub-agents — one per
batch of changed chunks — so only the changed parts of the knowledge base are
re-read. Separate higher-reasoning passes then handle concept resolution and
synthesis. In other words, CogMap uses agents as temporary cognitive workers,
while the pipeline remains the durable system of record.

## Quick start

CogMap is a **coding-agent skill**, not a standalone SaaS app. The Python
pipeline is the engine the agent drives; the normal user workflow is to
install/open the project in your agent and ask it to refresh or rebuild the
knowledge base.

### Prerequisites

- Python 3.10 or newer.
- One of: GitHub Copilot CLI, Claude Code, or OpenAI Codex CLI.
- No LLM API key. The host coding agent performs the semantic stages.
- Optional: `olefile` for best-effort OneNote `.onex` conversion.

1. Clone or open this repository in your coding agent workspace.
2. Install or expose the skill at `cogmap-app/skills/build-cogmap`.
3. Add your notes to the generated `cogmap/sources/` workspace as Markdown or plain text.
4. Ask the agent: `"refresh the knowledge base"` or `"add these notes and rebuild the knowledge map"`.
5. Open the generated visualization:

```text
cogmap/output/knowledge-base-viz.html
```

When extraction, resolution, or synthesis work is needed, the skill pauses the
pipeline, gives the coding agent structured actions to perform, and then resumes.
That agent-in-the-loop loop is what lets CogMap rebuild without requiring a
separate LLM API key.

## Installation paths

### GitHub Copilot CLI

Copy the self-contained skill folder into your Copilot skills directory:

```bash
cp -r cogmap-app/skills/build-cogmap ~/.copilot/skills/
```

On Windows, copy `cogmap-app\skills\build-cogmap` to
`%USERPROFILE%\.copilot\skills\`.

### Claude Code

This repository is a Claude Code marketplace. In Claude Code:

```text
/plugin marketplace add ryannadel/CogMap
/plugin install cogmap-knowledge-base@cogmap
```

### OpenAI Codex CLI

Codex discovers agent skills under `.agents/skills`. This repository ships a
mirrored copy at `.agents/skills/build-cogmap/`, kept in sync with the canonical
skill under `cogmap-app/skills/build-cogmap/`.

## Repository layout

```text
cogmap-app/
  skills/build-cogmap/   Self-contained skill and bundled pipeline engine
  tools/                 Utility scripts for keeping skill copies in sync

cogmap/                  Project-local workspace created at runtime
  sources/               Input notes
  work/                  LLM extraction/resolution/synthesis artifacts
  output/                Self-contained visualization HTML and JSON data
```

See `cogmap-app/README.md` for the full app guide.

## Development

Run the public-release checks from the repository root:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
python cogmap-app/tools/sync_skill.py --check
```

See `CONTRIBUTING.md` for contribution and skill-sync guidance.

## License

CogMap is released under the MIT License. See `LICENSE`.
