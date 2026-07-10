# CogMap

CogMap is a tool for navigating the tsunami of information that agents and people
produce. As agents generate more content, we need new tools for thought that help
us understand what a knowledge base contains, how ideas relate, what changed, what
matters, what conflicts, what is missing, and where attention should go next.

CogMap treats a knowledge base not as a folder of documents, but as an evolving
external memory system with time as a key organizing construct. It extracts
concepts, claims, relationships, tensions, gaps, and trends from notes, then
renders them as a self-contained, source-traceable visualization you can open in
any browser.

The goal is to make accumulated knowledge navigable for both people and agents:
map the concepts, trace relationships across sources, surface conflicts and gaps,
notice drift or convergence, and decide where to focus next.

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

## Quick start

CogMap is designed to run **inside a coding agent** such as GitHub Copilot,
Claude Code, or Codex. The Python pipeline is the engine the agent drives; the
normal user workflow is to install/open the project in your agent and ask it to
refresh or rebuild the knowledge base.

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
