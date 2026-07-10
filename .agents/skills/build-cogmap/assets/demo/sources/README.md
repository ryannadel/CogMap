# Your notes go here

Drop your notes into this `sources/` folder, then ask your agent to
**"refresh the knowledge base"** (or run `python ../pipeline/refresh.py`).

## Supported formats

| Extension | How it's chunked |
|-----------|------------------|
| `.md`, `.markdown` | By headings and paragraphs |
| `.txt`, `.text` | Auto-detects prose paragraphs vs. one-entry-per-line notebooks |

Every supported file dropped here becomes a **source**. Use as many files as you
like — one per topic, per notebook, per month, whatever suits you. The filename
becomes the source title, so name them meaningfully.

## Getting dates on the timeline

The visualization is a timeline. To place notes in time, include dates in the
text — any of these are recognized:

- `2025-03-14`
- `March 14, 2025` / `Mar 14`
- `3/14/2025`

Notes without an explicit date are interpolated between their dated neighbours
(in reading order). If a note has only a month/day, the year defaults to the
current year (override with the `COGMAP_DEFAULT_YEAR` env var; legacy
`OSLER_DEFAULT_YEAR` is also accepted). If nothing in the
corpus is dated, the timeline collapses — so add at least a few date anchors.

## Adding notes with your coding agent

You don't have to touch files manually. Just tell the agent, e.g.:

- *"Add these notes to the knowledge base: &lt;paste text&gt;"* — it saves them here and refreshes.
- *"Import my journal.md into the knowledge base."*
- *"I have a OneNote export (.onex) — ingest it."* — it runs the `.onex` converter (best-effort ~66%; a clean `.txt`/`.md` export is always better).

## Sample content

`sample-notes.txt` is a **synthetic demo** (a research journal on urban mobility).
Delete it and add your own notes when you're ready — then refresh.
