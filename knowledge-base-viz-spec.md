# Knowledge Base Visualization — Product & Technical Spec

**Status:** Draft v1
**Owner:** Ryan
**Scope:** Source-agnostic system that ingests arbitrary source material, extracts
entities/topics/relationships, and presents them as (a) a navigable knowledge graph and
(b) a browsable dashboard, with the ability to inspect underlying source material at every step.

---

## 1. Vision & Goals

Build a tool that turns a pile of unstructured source material into a **navigable map of
ideas**. The user should be able to:

1. **See connections** between ideas visually (graph view).
2. **Browse by topic and category** (e.g., Product Ideas, Issues, Future Research), where
   categories are *extracted from the data*, not hand-authored.
3. **Inspect the source** behind any node, edge, or claim (provenance / "show me why").
4. **Trust it** — every derived fact traces back to a specific source span.

### Non-goals (v1)
- Real-time collaborative editing.
- Full-text search engine replacement (we index for retrieval, not to be Elasticsearch).
- Authoring/writing tool — this is for *exploration and sense-making*, not drafting.

### Success criteria
- From a cold set of documents, a user can find a non-obvious connection between two ideas
  in under 2 minutes.
- Every node links to at least one source span; no "orphan claims."
- Categories/topics feel meaningful to the user ≥80% of the time (spot-check).

---

## 2. Core Concepts / Data Model

A small, stable ontology keeps the system flexible across source types.

### Entities (nodes)
| Type | Description | Example |
|------|-------------|---------|
| `Source` | A raw ingested artifact | a PDF, a note, a transcript, a URL |
| `Chunk` | A retrievable span of a Source | paragraph, slide, transcript segment |
| `Concept` | An extracted idea/entity/theme | "vector search", "onboarding friction" |
| `Category` | A high-level bucket, data-derived | "Product Idea", "Issue", "Future Research" |
| `Claim` | An assertion made in the material | "users abandon at step 3" |
| `Entity` | Named things: people, orgs, products, tech | "Ryan", "Postgres", "GPT-5" |

### Relationships (edges) — typed and directional
- `MENTIONS` (Chunk → Concept/Entity)
- `RELATES_TO` (Concept ↔ Concept, weighted by co-occurrence / semantic similarity)
- `SUPPORTS` / `CONTRADICTS` (Claim ↔ Claim)
- `BELONGS_TO` (Concept/Claim → Category)
- `DERIVED_FROM` (every derived node → Chunk → Source)  ← **provenance backbone**
- `DEPENDS_ON` / `BLOCKS` (for idea/issue dependencies)
- `EVOLVES_INTO` (temporal: idea A becomes idea B)

### Universal metadata (on every node/edge)
- `id`, `created_at`, `source_ts` (when the underlying material is dated)
- `confidence` (0–1, from the extractor)
- `provenance[]` (list of {source_id, chunk_id, char_span})
- `salience` / `weight` (importance score)
- `embedding` (vector, for similarity + clustering)

> **Principle:** No derived node exists without a `DERIVED_FROM` path to a Source. This makes
> "inspect the source" trivial and keeps the whole graph auditable.

---

## 3. Pipeline / Architecture

```
Ingest → Normalize → Chunk → Extract → Link → Categorize → Score → Store → Serve → Visualize
```

### 3.1 Ingest (source-agnostic)
- Pluggable connectors: filesystem (md/txt/pdf/docx), URLs, transcripts, CSV/JSON, clipboard.
- Each connector emits a normalized `Source` + raw text + metadata (title, date, author, path).
- Store the original bytes/URL so the user can always open the true original.

### 3.2 Normalize & Chunk
- Convert to clean text; preserve structure (headings, timestamps, page numbers) as anchors.
- Chunk by semantic boundaries (headings/paragraphs) with overlap; keep char offsets for
  precise provenance highlighting.

### 3.3 Extract (LLM + NLP)
- Extract Concepts, Entities, Claims per chunk with confidence scores.
- Deduplicate/merge across chunks (entity resolution): "vector DB" == "vector database".
  Use embedding similarity + canonical-name resolution.

### 3.4 Link
- Build edges from co-occurrence, semantic similarity (embedding cosine), and explicit
  LLM-inferred relations (supports/contradicts/depends-on).
- Threshold edges to avoid a hairball (see §5.3).

### 3.5 Categorize (data-derived)
- Cluster Concepts (embeddings → HDBSCAN/k-means) to discover themes.
- Label clusters with an LLM ("name this cluster of ideas").
- Classify each Concept/Claim into functional categories (Product Idea / Issue / Question /
  Decision / Future Research / Fact) via LLM few-shot. **Categories are proposed from the
  data, then the user can rename/merge/pin them.**

### 3.6 Score
- `salience` = frequency × centrality (graph degree/PageRank) × recency.
- Feeds node sizing, default filters, and "what matters most" surfacing.

### 3.7 Store
- **Graph store** for topology (Neo4j, or SQLite+edges table for a lighter footprint).
- **Vector store** for embeddings (pgvector, LanceDB, or Chroma).
- **Blob/text store** for raw sources + chunks.
- A single Postgres with `pgvector` can cover graph-ish + vector + relational for a v1.

### 3.8 Serve
- API layer (REST/GraphQL) exposing: graph query, node detail + provenance, search,
  category browse, filters.

---

## 4. UX / Views

### 4.1 Graph view (the centerpiece)
- Force-directed layout; nodes = Concepts/Claims, edges = typed relations.
- **Node encoding:** size = salience, color = category, icon = type.
- **Edge encoding:** thickness = weight, style = relation type, arrow = direction.
- Interactions:
  - Click node → side panel with detail + **source snippets** (highlighted spans).
  - Hover → neighbors highlight, rest dim (focus+context).
  - Expand/collapse neighborhoods (progressive disclosure — don't render all at once).
  - Filter by category, type, date range, confidence, source.
  - Search box → zoom/pan to node.
  - "Path between" mode: pick two nodes, show connecting paths (great for "how are these
    related?").
  - Pin/lasso/group; save a view.
- Layout options: force, hierarchical (for dependencies), radial (ego network), timeline.

### 4.2 Dashboard / browse view
- **Category lanes:** Product Ideas | Issues | Questions | Decisions | Future Research…
  each a scrollable list of cards.
- Card = title, snippet, source count, salience, tags; click → detail + graph focus.
- Facet/filter sidebar: category, source, date, entity, confidence.
- Sort: salience, recency, most-connected, most-contested (supports vs contradicts).
- Topic index: the data-derived clusters as an at-a-glance grid with counts.

### 4.3 Source inspector (provenance panel)
- Given any node/edge, show the exact source chunks with the relevant span highlighted.
- "Open original" (PDF page, note, URL, transcript timestamp).
- Reverse view: open a Source → see everything extracted from it, highlighted inline.

### 4.4 Detail / entity page
- Full context for a Concept/Claim: definition, all sources, related nodes, timeline,
  contradictions, category.

### 4.5 Global search
- Hybrid search (keyword + semantic) over sources, concepts, claims. Results deep-link into
  graph and dashboard.

---

## 5. Hard Problems / Things to Consider

### 5.1 Extraction quality & trust
- LLM extraction hallucinates. Mitigate with: confidence scores, mandatory provenance,
  a "low-confidence" visual treatment, and easy user correction.
- Let users **verify/reject** extracted nodes and edges — feed corrections back.

### 5.2 Entity resolution / dedup
- The #1 thing that makes a graph feel smart or dumb. Same idea under different wording must
  merge; genuinely different ideas must not. Budget real effort here (embeddings + canonical
  forms + optional human merge UI).

### 5.3 Graph legibility (the hairball problem)
- A dense graph is useless. Solutions: edge thresholding, importance-based filtering,
  clustering into super-nodes, progressive expansion, and "focus mode" (ego networks).
- Default to showing top-N salient nodes; expand on demand.

### 5.4 Category taxonomy stability
- Data-derived categories drift as data grows. Support: pinning categories, merging,
  renaming, and re-running clustering without losing user edits (store user overrides
  separately from derived labels).

### 5.5 Incremental / re-ingestion
- Adding new sources shouldn't recompute the world. Design for incremental extraction,
  incremental clustering, and stable node IDs so saved views survive updates.

### 5.6 Temporal dimension
- Ideas evolve. Consider a time slider, `source_ts` on nodes, and `EVOLVES_INTO` edges to
  show how thinking changed. Useful for "what's new since last week?"

### 5.7 Scale & performance
- Graph rendering degrades past a few thousand visible nodes. Use WebGL renderers
  (Sigma.js / regl) not SVG for big graphs; server-side filtering; pagination on dashboard.

### 5.8 Contradiction & duplication surfacing
- A knowledge base's superpower is showing tension: which claims contradict, which ideas are
  duplicated across sources. Make `CONTRADICTS` / duplicate detection first-class.

### 5.9 Privacy / local-first
- If sources are personal/sensitive, prefer local-first storage and local or private-endpoint
  models. Be explicit about what leaves the machine (embeddings? raw text?).

### 5.10 Cost & latency of extraction
- LLM extraction over a large corpus is slow/expensive. Batch, cache by content hash, and
  make ingestion a background job with progress reporting.

### 5.11 Export & interop
- Let users export the graph (GraphML/JSON), a category as markdown, or a filtered view.
  Avoid lock-in; the knowledge should be portable.

---

## 6. Suggested Tech Stack (v1, lean)

| Layer | Option |
|-------|--------|
| Ingestion | Python workers; `unstructured`/`pymupdf` for PDFs |
| Extraction | LLM (structured JSON output) + spaCy for cheap NER |
| Embeddings | Local (e.g. `bge`/`nomic`) or hosted |
| Storage | Postgres + `pgvector` (graph edges as a table) OR Neo4j if graph-heavy |
| API | FastAPI (REST or GraphQL) |
| Frontend | React + Sigma.js/Cytoscape.js (graph) + a component lib for dashboard |
| Jobs | A queue (Celery/RQ) for background ingestion |

> For a fast prototype: SQLite + pgvector-like extension, a single FastAPI app, and
> Cytoscape.js can get you an interactive graph without standing up Neo4j.

---

## 7. Phased Roadmap

**Phase 0 — Spike:** Ingest one source type → chunk → LLM extract concepts+provenance →
render a static graph. Prove the provenance loop end-to-end.

**Phase 1 — Core:** Multi-source ingest, entity resolution, typed edges, graph view with
filters, source inspector.

**Phase 2 — Dashboard:** Data-derived categories/clusters, category lanes, facets, search.

**Phase 3 — Trust & scale:** Confidence UI, user corrections, incremental re-ingest, WebGL
rendering, contradiction surfacing.

**Phase 4 — Depth:** Temporal view, path-finding, saved views, export, dependency layouts.

---

## 8. Open Questions
- Single-user local tool, or shared/multi-user?
- Roughly how many sources / total volume at maturity? (drives storage + render tech)
- Which model(s) allowed for extraction (privacy constraints)?
- How much manual curation are you willing to do vs. fully automated?
- Is temporal/evolution tracking important, or a static snapshot enough for v1?
