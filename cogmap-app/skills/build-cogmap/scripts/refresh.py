"""refresh.py -- one-command, resumable refresh of the knowledge-base visualization.

Value: change a source (notes clean text / spec), run this, and the view is
rebuilt -- re-extracting ONLY the notes that actually changed (incremental),
re-clustering / re-synthesizing only when the concept graph moved.

It is Copilot-in-the-loop: the LLM stages (extraction, entity resolution,
synthesis) are performed by Copilot sub-agents. This script does every
deterministic stage itself and, whenever an LLM stage is required, it writes the
inputs, prints a machine-readable ACTION block, and exits with code 10. After the
agent(s) finish, just run refresh.py again -- it detects the outputs and
continues. When nothing is left to do it rebuilds the HTML and exits 0.

Flags:
  --from-onex     re-extract the .onex -> clean text first (best-effort ~66%)
  --with-resolve  re-run entity resolution when the concept set changed
  --with-synth    re-run insight synthesis when the graph changed
  --skip-resolve  reuse existing resolution even if stale (new concepts -> singletons)
  --skip-synth    reuse existing insights even if stale
"""
import json, re, hashlib, pathlib, subprocess, sys, os, time, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cogmap_paths import WORK, OUTPUT, PIPELINE
STATE = WORK
ROOT = OUTPUT
EX = STATE / 'v3_extract'
DELTA = STATE / 'refresh_delta'
CACHE = STATE / 'refresh_cache'
EX.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)
STATEF = CACHE / 'state.json'
DATA = ROOT / 'knowledge-base-viz-data.json'
BUDGET = 26000
PY = sys.executable
ARGS = set(sys.argv[1:])

def sha1s(s): return hashlib.sha1(s.encode('utf-8', 'ignore')).hexdigest()

def safe_rmtree(p):
    """Robust against transient Windows/OneDrive/AV locks on the directory."""
    p = pathlib.Path(p)
    for _ in range(6):
        try:
            shutil.rmtree(p); return
        except FileNotFoundError:
            return
        except (PermissionError, OSError):
            time.sleep(0.5)
    # last resort: empty it file-by-file, then drop the dir if possible
    try:
        for f in sorted(p.rglob('*'), reverse=True):
            try: f.unlink()
            except Exception:
                try: f.rmdir()
                except Exception: pass
        p.rmdir()
    except Exception:
        pass


def run(script):
    env = dict(os.environ); env['PYTHONIOENCODING'] = 'utf-8'
    r = subprocess.run([PY, str(PIPELINE / script)], env=env, cwd=str(STATE),
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        print(f'--- {script} FAILED ---\n{r.stdout}\n{r.stderr}'); sys.exit(1)
    return r.stdout.strip()


def open_result(html):
    """Auto-open the finished visualization in the default browser.

    Suppressed with `--no-open` or COGMAP_NO_OPEN=1 (for headless/CI/agent runs).
    Best-effort: a failure to launch a browser never fails the build.
    """
    if '--no-open' in ARGS or os.environ.get('COGMAP_NO_OPEN'):
        return
    html = pathlib.Path(html)
    if not html.exists():
        return
    uri = html.resolve().as_uri()
    try:
        if sys.platform == 'darwin':
            subprocess.Popen(['open', str(html)])
        elif os.name == 'nt':
            os.startfile(str(html))  # noqa: S606 - trusted local path
        elif sys.platform.startswith('linux'):
            subprocess.Popen(['xdg-open', str(html)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            import webbrowser; webbrowser.open(uri)
        print('Opened {} in your browser.'.format(html.name))
    except Exception:
        try:
            import webbrowser; webbrowser.open(uri)
            print('Opened {} in your browser.'.format(html.name))
        except Exception:
            print('Open it manually: {}'.format(html))


def load_state():
    if STATEF.exists():
        return json.loads(STATEF.read_text(encoding='utf-8'))
    return {}

def covered_chunk_ids():
    """Union of chunk ids referenced by any existing extraction file."""
    ids = set()
    for f in EX.glob('extract_*.json'):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        for c in d.get('concepts', []):
            ids.update(c.get('chunk_ids', []) or [])
        for c in d.get('claims', []):
            if c.get('chunk_id'): ids.add(c['chunk_id'])
        for r in d.get('relations', []):
            ids.update(r.get('evidence_chunk_ids', []) or [])
    return ids

def save_state(s):
    CACHE.mkdir(exist_ok=True)
    STATEF.write_text(json.dumps(s, indent=1), encoding='utf-8')

def action(kind, payload, human):
    (CACHE).mkdir(exist_ok=True)
    (CACHE / 'action.json').write_text(json.dumps({'action': kind, **payload}, indent=1), encoding='utf-8')
    print('\n' + '=' * 68)
    print(f'ACTION NEEDED: {kind}')
    print('=' * 68)
    print(human)
    print('(details written to refresh_cache/action.json; re-run refresh.py after)')
    sys.exit(10)

# ---------------- extraction batch helpers ----------------
def write_delta_batches(master, miss_ids):
    if DELTA.exists(): safe_rmtree(DELTA)
    DELTA.mkdir()
    by_id = {c['id']: c for c in master['chunks']}
    miss = sorted(miss_ids, key=lambda i: by_id[i]['order'])
    batches = []; cur = []; cur_len = 0
    for i in miss:
        c = by_id[i]
        item = {'chunk_id': c['id'], 'order': c['order'], 'source': c['source_id'],
                'heading': c['heading'], 'date': c.get('date'), 'date_exact': c.get('date_exact', False),
                'text': c['text']}
        if cur and cur_len + len(c['text']) > BUDGET:
            batches.append(cur); cur = []; cur_len = 0
        cur.append(item); cur_len += len(c['text'])
    if cur: batches.append(cur)
    man = {'batches': []}
    for n, b in enumerate(batches):
        inp = DELTA / f'pending_{n:02d}.json'
        inp.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding='utf-8')
        man['batches'].append({'input': str(inp), 'output': str(DELTA / f'extract_{n:02d}.json'),
                               'chunk_ids': [x['chunk_id'] for x in b]})
    (DELTA / 'manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    return man

def outputs_ready(man):
    for b in man['batches']:
        p = pathlib.Path(b['output'])
        if not p.exists(): return False
        try: json.loads(p.read_text(encoding='utf-8'))
        except Exception: return False
    return True

def ingest(man, state):
    stamp = str(int(time.time()))
    ids = set()
    for i, b in enumerate(man['batches']):
        out = json.loads(pathlib.Path(b['output']).read_text(encoding='utf-8'))
        (EX / f'extract_delta_{stamp}_{i:02d}.json').write_text(
            json.dumps(out, ensure_ascii=False), encoding='utf-8')
        ids.update(b['chunk_ids'])
    state['extracted_ids'] = sorted(set(state.get('extracted_ids', [])) | ids)
    # Delete the manifest FIRST as the completion marker: if the subsequent dir
    # cleanup is blocked (Windows/OneDrive lock), a surviving manifest must not
    # cause this batch to be re-ingested (which would duplicate extractions and
    # inflate edge weights) on the next run.
    try: (DELTA / 'manifest.json').unlink()
    except FileNotFoundError: pass
    safe_rmtree(DELTA)
    return len(ids)

# ---------------- fingerprints ----------------
def raw_fp():
    raw = json.loads((STATE / 'v3_raw_concepts.json').read_text(encoding='utf-8'))
    return sha1s('|'.join(sorted(c['name'] for c in raw)))

def resolve_uncovered():
    raw = set(c['name'].lower() for c in json.loads((STATE / 'v3_raw_concepts.json').read_text(encoding='utf-8')))
    rp = STATE / 'v3_resolved.json'
    res = json.loads(rp.read_text(encoding='utf-8')) if rp.exists() else {'concepts': []}
    members = set()
    for c in res.get('concepts', []):
        for m in c.get('members', []): members.add(m.lower())
    return sorted(raw - members)

def graph_fp():
    d = json.loads(DATA.read_text(encoding='utf-8'))
    parts = sorted(c['canonical'] for c in d['concepts'])
    parts += sorted(f"{e['type']}:{e['source']}:{e['target']}" for e in d['edges'])
    return sha1s('|'.join(parts))

def insights_cover_graph():
    """True only if the existing insights reference concept ids that still exist in
    the current assembled graph, so stale/demo insights don't suppress the synth gate."""
    try:
        syn = json.loads((STATE / 'v3_insights.json').read_text(encoding='utf-8'))
    except Exception:
        return False
    refs = set()
    for s in syn.get('insights', []):
        if s.get('node'): refs.add(s['node'])
    for s in syn.get('synthesis', []):
        for n in (s.get('nodes') or []): refs.add(n)
    if not refs:
        return False
    try:
        ids = {c['id'] for c in json.loads(DATA.read_text(encoding='utf-8'))['concepts']}
    except Exception:
        return False
    return len(refs & ids) >= max(1, len(refs) // 2)

def build_synth_input():
    d = json.loads(DATA.read_text(encoding='utf-8'))
    by = {c['id']: c for c in d['concepts']}
    def lbl(i): return by[i]['label'] if i in by else i
    third = max(1, d['metadata']['np'] // 3)
    concepts = [{'id': c['id'], 'label': c['label'], 'category': c['category'],
                 'definition': c['definition'], 'salience': c['salience'], 'mentions': c['mention_count'],
                 'first': f"{round(c['first_pos']*100)}%", 'last': f"{round(c['last_pos']*100)}%",
                 'early': sum(c['timeline'][:third]), 'late': sum(c['timeline'][-third:])}
                for c in sorted(d['concepts'], key=lambda c: -c['salience'])[:120]]
    ev = [[lbl(e['source']), lbl(e['target'])] for e in d['edges'] if e['type'] == 'EVOLVES_INTO']
    en = [[lbl(e['source']), lbl(e['target'])] for e in d['edges'] if e['type'] == 'ENABLES'][:80]
    con = [{'a': c['a_label'], 'b': c['b_label'], 'summary': c.get('summary', '')} for c in d['contradictions']]
    cand = [{'type': i['type'], 'node': i.get('node'), 'title': i['title']}
            for i in d['insights'] if i['type'] != 'Synthesis']
    (STATE / 'v3_synth_input.json').write_text(json.dumps(
        {'concepts': concepts, 'evolves_into': ev, 'enables': en, 'contradictions': con,
         'existing_insight_candidates': cand, 'categories': [c['label'] for c in d['categories']]},
        ensure_ascii=False, indent=1), encoding='utf-8')

# ---------------- main ----------------
def run_soft(script):
    """Like run(), but never aborts: returns the CompletedProcess so the caller can
    decide. Used for best-effort stages (e.g. .onex conversion) that may legitimately
    recover nothing without dooming the whole refresh."""
    env = dict(os.environ); env['PYTHONIOENCODING'] = 'utf-8'
    return subprocess.run([PY, str(PIPELINE / script)], env=env, cwd=str(STATE),
                          capture_output=True, text=True, encoding='utf-8')

def main():
    from cogmap_paths import APP, SOURCES
    print('workspace: {}'.format(APP))
    print('  sources: {}'.format(SOURCES))
    print('  output:  {}'.format(OUTPUT))
    if '--from-onex' in ARGS:
        print('extracting .onex -> clean text (best-effort)...')
        r = run_soft('extract_onex.py')
        if r.stdout.strip():
            print(r.stdout.strip())
        if r.returncode != 0:
            if r.stderr.strip():
                print(r.stderr.strip())
            print('WARNING: .onex conversion recovered no usable text; continuing with '
                  'any .md/.txt notes already in sources/.')

    print('prep: chunking sources...')
    run('v3_prep.py')
    master = json.loads((STATE / 'v3_chunks_master.json').read_text(encoding='utf-8'))
    current = [c['id'] for c in master['chunks']]
    cset = set(current)

    if not current:
        print('\nNo notes found in sources/. Drop .md or .txt files into the '
              'sources/ folder (or convert a .onex with --from-onex) and re-run.')
        sys.exit(0)

    state = load_state()
    first_run = not state.get('seeded')
    if first_run:
        # Seed only the chunks that shipped/prior extractions ACTUALLY cover, so a
        # fresh clone left unchanged is a no-op, but a user who dropped in their own
        # notes (different chunk ids) gets those extracted instead of an empty graph.
        covered = covered_chunk_ids()
        seeded_ids = [c for c in current if c in covered]
        state = {'seeded': True, 'extracted_ids': seeded_ids, 'resolve_fp': None, 'synth_fp': None}
        if seeded_ids:
            print(f'first run: seeding baseline ({len(seeded_ids)}/{len(current)} chunks already extracted)')
        else:
            print('first run: no prior extractions cover these notes -> will extract all notes')
            # A shipped demo corpus was replaced with the user's own notes: the demo's
            # resolution/insights belong to a different graph. Drop them so they can't
            # leak demo categories/insight nodes into the user's graph and so the
            # resolve/synth gates fire correctly on the new corpus.
            for p in (STATE / 'v3_resolved.json', STATE / 'v3_insights.json'):
                if p.exists():
                    print(f'  clearing stale demo artifact: {p.name}')
                    try: p.unlink()
                    except Exception: pass
    # prune stale extracted ids
    state['extracted_ids'] = sorted(set(state.get('extracted_ids', [])) & cset)
    removed = len(cset) and (len(current) - len(state['extracted_ids']))

    # ---------- EXTRACTION ----------
    man_path = DELTA / 'manifest.json'
    if man_path.exists():
        man = json.loads(man_path.read_text(encoding='utf-8'))
        if outputs_ready(man):
            n = ingest(man, state); save_state(state)
            print(f'ingested {n} newly extracted chunks')
        else:
            done = sum(pathlib.Path(b['output']).exists() for b in man['batches'])
            action('extract', {'manifest': str(man_path), 'batches': man['batches']},
                   f"{done}/{len(man['batches'])} extraction batches done. Run an extraction agent for "
                   f"each pending refresh_delta/pending_NN.json -> refresh_delta/extract_NN.json.")
    miss = sorted(cset - set(state['extracted_ids']))
    if miss:
        man = write_delta_batches(master, miss)
        nb = len(man['batches'])
        save_state(state)
        action('extract', {'manifest': str(DELTA / 'manifest.json'), 'batches': man['batches']},
               f"{len(miss)} new/changed chunks -> {nb} extraction batch(es).\n"
               f"For each refresh_delta/pending_NN.json, run a general-purpose agent that reads the batch\n"
               f"(json.load), extracts concepts/claims/relations in the v3 schema, and writes\n"
               f"refresh_delta/extract_NN.json. Then re-run refresh.py.")
    save_state(state)

    # ---------- AGGREGATE ----------
    print('aggregate: merging extractions...')
    print('  ' + run('v3_aggregate.py').replace('\n', '\n  '))
    rfp = raw_fp()
    # The existing resolution is a valid baseline only if it actually covers the
    # current concept set. This prevents a shipped/stale v3_resolved.json from
    # suppressing the resolve gate (which would leave the user's concepts as
    # uncategorized singletons even with --with-resolve).
    uncov = resolve_uncovered()
    have_resolved = not uncov
    if state.get('resolve_fp') is None and have_resolved:
        state['resolve_fp'] = rfp  # seed baseline only when the resolution fits the corpus
    resolve_stale = (not have_resolved) or (rfp != state.get('resolve_fp'))

    # ---------- RESOLVE (gated) ----------
    if resolve_stale:
        if '--with-resolve' in ARGS:
            if not uncov:
                state['resolve_fp'] = rfp; save_state(state)
                print('resolution now covers all concepts')
            else:
                (CACHE).mkdir(exist_ok=True)
                (CACHE / 'resolve_new_names.json').write_text(json.dumps(uncov, ensure_ascii=False, indent=1), encoding='utf-8')
                action('resolve', {'raw_concepts': str(STATE / 'v3_raw_concepts.json'),
                                   'existing': str(STATE / 'v3_resolved.json'),
                                   'new_names': str(CACHE / 'resolve_new_names.json'), 'uncovered': len(uncov)},
                       f"{len(uncov)} concept name(s) are not yet clustered. Run an Opus resolver agent that\n"
                       f"assigns every name in v3_raw_concepts.json to exactly one canonical concept in\n"
                       f"v3_resolved.json (extend it; the {len(uncov)} new names are listed in\n"
                       f"refresh_cache/resolve_new_names.json). Reuse an existing category string when one\n"
                       f"fits, else coin a concise thematic category (aim for ~5-10 balanced categories\n"
                       f"overall). Overwrite v3_resolved.json, then re-run refresh.py --with-resolve.")
        elif '--skip-resolve' not in ARGS:
            print('  NOTE: concept set changed; run `refresh.py --with-resolve` for best clustering '
                  '(new concepts will be singletons otherwise).')

    # ---------- ASSEMBLE ----------
    print('assemble: building data json...')
    print('  ' + run('v3_assemble.py').replace('\n', '\n  '))
    gfp = graph_fp()
    # Existing insights are a valid baseline only if they reference concepts that
    # still exist in the current graph (a swapped corpus invalidates demo insights).
    have_insights = insights_cover_graph()
    if state.get('synth_fp') is None and have_insights:
        state['synth_fp'] = gfp  # seed baseline only when insights fit the graph
    synth_stale = (not have_insights) or (gfp != state.get('synth_fp'))

    # ---------- SYNTH (gated) ----------
    if synth_stale:
        if '--with-synth' in ARGS:
            if state.get('synth_pending') == gfp and (STATE / 'v3_insights.json').stat().st_mtime > state.get('synth_token', 0):
                state['synth_fp'] = gfp; state.pop('synth_pending', None); save_state(state)
                print('synthesis refreshed; re-assembling to inject...')
                print('  ' + run('v3_assemble.py').replace('\n', '\n  '))
            else:
                build_synth_input()
                state['synth_pending'] = gfp; state['synth_token'] = time.time(); save_state(state)
                action('synth', {'synth_input': str(STATE / 'v3_synth_input.json'),
                                 'out': str(STATE / 'v3_insights.json')},
                       "Graph changed. Run an Opus synthesis agent over v3_synth_input.json to produce\n"
                       "v3_insights.json (polished insight narratives + cross-cutting synthesis cards,\n"
                       "each referencing concept ids that exist in the input). Then re-run.")
        elif '--skip-synth' not in ARGS:
            print('  NOTE: graph changed; run `refresh.py --with-synth` to refresh insight narratives.')

    # ---------- BUILD ----------
    print('build: rendering HTML...')
    print('  ' + run('build_v2.py'))
    save_state(state)
    print('\nDONE. chunks={} tracked-extracted={}'.format(len(current), len(state['extracted_ids'])))
    print('Hard-refresh the browser (Ctrl+Shift+R) to see the update.')
    open_result(OUTPUT / 'knowledge-base-viz.html')

if __name__ == '__main__':
    main()
