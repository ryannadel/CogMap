import json, re, hashlib, pathlib, datetime, os, sys
from collections import defaultdict
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cogmap_paths import SOURCES, WORK
STATE = WORK
BATCH_DIR = STATE / 'v3_batches'
BATCH_DIR.mkdir(exist_ok=True)

# Any of these file types dropped into sources/ is ingested as notes.
SUPPORTED = {'.md': 'markdown', '.markdown': 'markdown', '.txt': 'text', '.text': 'text'}
# Year used when a note has a month/day but no explicit year (override with env).
DEFAULT_YEAR = int(os.environ.get('COGMAP_DEFAULT_YEAR') or os.environ.get('OSLER_DEFAULT_YEAR') or datetime.date.today().year)
YEAR_MIN, YEAR_MAX = 2000, datetime.date.today().year + 1

# ---------- text utils ----------
def clean_text(s):
    s = re.sub(r'HYPERLINK\s+"([^"]+)"', ' ', s)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = s.replace('\u2011', '-')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def is_readable(s):
    if len(s) < 30: return False
    printable = sum(1 for c in s if c.isprintable()) / max(1, len(s))
    letters = sum(1 for c in s if c.isalpha()) / max(1, len(s))
    weird = sum(1 for c in s if ord(c) > 127 and c not in '\u201c\u201d\u2018\u2019\u2014\u2013\u2026\u00e9\u00c9\u00e8\u00c8\u00e1\u00c1\u00ed\u00cd\u00f3\u00d3\u00fa\u00da\u00fc\u00dc\u00f1\u00d1') / max(1, len(s))
    return printable > 0.92 and letters > 0.35 and weird < 0.08

def sha(prefix, text):
    return prefix + '_' + hashlib.sha1(text.encode('utf-8', errors='ignore')).hexdigest()[:12]

# ---------- date parsing ----------
MONTHS = {m.lower():i for i,m in enumerate(
    ['January','February','March','April','May','June','July','August','September','October','November','December'], start=1)}
MONTH_ABBR = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'sept':9,'oct':10,'nov':11,'dec':12}
def infer_year(month): return DEFAULT_YEAR
def safe_date(y, m, d):
    try: return datetime.date(y, m, min(d, 28))
    except Exception: return None
def parse_dates(text):
    found=[]; t=text
    for mo in re.finditer(r'\b(20\d{2})-(\d{1,2})-(\d{1,2})\b', t):
        d=safe_date(int(mo.group(1)),int(mo.group(2)),int(mo.group(3)));
        if d: found.append(d)
    for mo in re.finditer(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s*(20\d{2})\b', t, re.I):
        d=safe_date(int(mo.group(3)),MONTHS[mo.group(1).lower()],int(mo.group(2)))
        if d: found.append(d)
    for mo in re.finditer(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2})\b', t, re.I):
        m=MONTH_ABBR[mo.group(1).lower()]; d=safe_date(infer_year(m),m,int(mo.group(2)))
        if d: found.append(d)
    for mo in re.finditer(r'\b(\d{1,2})/(\d{1,2})(?:/(20\d{2}|\d{2}))?\b', t):
        mm,dd=int(mo.group(1)),int(mo.group(2))
        if not (1<=mm<=12 and 1<=dd<=31): continue
        yy=mo.group(3)
        if yy:
            y=int(yy) if len(yy)==4 else 2000+int(yy)
            if not (YEAR_MIN<=y<=YEAR_MAX): y=infer_year(mm)
        else: y=infer_year(mm)
        d=safe_date(y,mm,dd)
        if d: found.append(d)
    for mo in re.finditer(r'\b(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(20\d{2})\b', t):
        d=safe_date(int(mo.group(3)),int(mo.group(1)),int(mo.group(2)))
        if d: found.append(d)
    for mo in re.finditer(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b', t, re.I):
        d=safe_date(int(mo.group(2)),MONTHS[mo.group(1).lower()],15)
        if d: found.append(d)
    found=[d for d in found if YEAR_MIN<=d.year<=YEAR_MAX]
    return found

# ---------- source -> chunks ----------
def chunks_from_markdown(path):
    text=path.read_text(encoding='utf-8', errors='ignore')
    out=[]; heading=path.name; buf=[]; pos=0; start=0
    for line in text.splitlines()+['']:
        if line.startswith('#') or (not line.strip() and buf):
            if buf:
                raw='\n'.join(buf).strip()
                if raw: out.append({'heading':heading,'text':clean_text(raw),'start':start,'end':start+len(raw),'line':None})
                buf=[]
            if line.startswith('#'): heading=clean_text(line.lstrip('#').strip()); start=pos
        elif line.strip():
            if not buf: start=pos
            buf.append(line)
        pos+=len(line)+1
    return out

def _emit(out, raw, heading, line_no):
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', raw) if len(raw) > 900 else [raw]
    for part in parts:
        part = clean_text(part)
        if is_readable(part):
            out.append({'heading': heading, 'text': part, 'start': 0, 'end': len(part), 'line': line_no})

def chunks_from_text(path):
    """Format-agnostic plain-text notes. Auto-detects prose (blank-line-separated
    paragraphs) vs. one-entry-per-line notebooks and chunks accordingly."""
    text = path.read_text(encoding='utf-8', errors='ignore')
    lines = text.splitlines()
    nonempty = [l for l in lines if l.strip()]
    blanks = sum(1 for l in lines if not l.strip())
    para_mode = blanks >= max(3, 0.15 * max(1, len(nonempty)))
    out = []
    if para_mode:
        cursor = 0
        for u in re.split(r'\n\s*\n', text):
            start = text.find(u, cursor); start = start if start >= 0 else cursor
            line_no = text.count('\n', 0, start) + 1
            cursor = start + len(u)
            raw = clean_text(re.sub(r'^\s*\d+\.\s*', '', u.replace('\n', ' ')))
            _emit(out, raw, path.stem, line_no)
    else:
        for i, line in enumerate(lines, start=1):
            raw = clean_text(re.sub(r'^\s*\d+\.\s*', '', line))
            _emit(out, raw, path.stem, i)
    return out

def _slug(s):
    s = re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')
    return s or 'source'

def _natkey(p):
    # Natural sort so part2 < part10, and a leading date/number orders correctly.
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', p.name.lower())]

def discover_sources():
    """Every supported file dropped into sources/ becomes a note source.
    File order (natural-sorted by name) defines the global reading order that the
    timeline interpolates over -- prefix filenames with a date/number to control it."""
    files = sorted(
        (p for p in SOURCES.rglob('*')
         if p.is_file() and p.suffix.lower() in SUPPORTED and p.name.lower() != 'readme.md'),
        key=_natkey,
    )
    srcs, used = [], set()
    for p in files:
        kind = SUPPORTED[p.suffix.lower()]
        base = 'source_' + _slug(p.stem); sid = base; n = 2
        while sid in used:
            sid = f'{base}_{n}'; n += 1
        used.add(sid)
        ch = chunks_from_markdown(p) if kind == 'markdown' else chunks_from_text(p)
        if not ch:
            # A file that yields no readable chunks (e.g. an empty or image-only note)
            # contributes nothing; skip it so it can't show up as a phantom source.
            print(f'skip: {p.name} produced no readable chunks', file=sys.stderr)
            continue
        srcs.append({'id': sid, 'title': p.stem, 'path': p.name, 'kind': kind, '_chunks': ch})
    return srcs

sources = discover_sources()

chunks=[]; norm_seen={}; order=0
for s in sources:
    for idx,ch in enumerate(s['_chunks']):
        # Full normalized text (not a 200-char prefix): so distinct notes sharing a
        # prefix don't collide/drop, and editing anywhere in a note changes its id
        # and triggers re-extraction.
        norm=re.sub(r'[^a-z0-9 ]','',ch['text'].lower()); norm=re.sub(r'\s+',' ',norm).strip()
        if norm in norm_seen:
            chunks[norm_seen[norm]]['dup_count']+=1; continue
        cid=sha('chunk', f"{s['id']}:{norm}")
        rec={'id':cid,'source_id':s['id'],'heading':ch['heading'],'text':ch['text'],
             'char_span':[ch['start'],ch['end']],'line':ch['line'],'order':order,'dup_count':1,
             'dates':[d.isoformat() for d in parse_dates(ch['text'])]}
        norm_seen[norm]=len(chunks); chunks.append(rec); order+=1

# ---------- dates: anchor on explicit dates, interpolate over global reading order ----------
ordered=sorted(chunks,key=lambda c:c['order'])
anchors=[(pos, datetime.date.fromisoformat(min(c['dates']))) for pos,c in enumerate(ordered) if c['dates']]
if anchors:
    fixed=[]; last=None
    for pos,d in anchors:
        if last and d<last: d=last
        fixed.append((pos,d)); last=d
    anchors=fixed
    def interp(pos):
        if pos<=anchors[0][0]: return anchors[0][1]
        if pos>=anchors[-1][0]: return anchors[-1][1]
        for (p0,d0),(p1,d1) in zip(anchors,anchors[1:]):
            if p0<=pos<=p1:
                if p1==p0: return d0
                frac=(pos-p0)/(p1-p0); days=(d1-d0).days
                return d0+datetime.timedelta(days=round(days*frac))
        return anchors[-1][1]
    for pos,c in enumerate(ordered):
        c['date']=(datetime.date.fromisoformat(min(c['dates'])) if c['dates'] else interp(pos)).isoformat()
        c['date_exact']=bool(c['dates'])
else:
    for c in ordered: c['date']=None; c['date_exact']=False

# ---------- master + batches ----------
master={'sources':[{k:s[k] for k in ('id','title','path','kind')} for s in sources],'chunks':chunks}
(STATE/'v3_chunks_master.json').write_text(json.dumps(master,ensure_ascii=False),encoding='utf-8')

# batch by cumulative char budget, keep reading order, don't split sources across a batch boundary awkwardly
BUDGET=26000
batches=[]; cur=[]; cur_len=0
for c in sorted(chunks,key=lambda c:c['order']):
    item={'chunk_id':c['id'],'order':c['order'],'source':c['source_id'],'heading':c['heading'],'date':c.get('date'),'date_exact':c.get('date_exact',False),'text':c['text']}
    if cur and cur_len+len(c['text'])>BUDGET:
        batches.append(cur); cur=[]; cur_len=0
    cur.append(item); cur_len+=len(c['text'])
if cur: batches.append(cur)

for i,b in enumerate(batches):
    (BATCH_DIR/f'batch_{i:02d}.json').write_text(json.dumps(b,ensure_ascii=False,indent=1),encoding='utf-8')

print('chunks',len(chunks),'batches',len(batches))
print('batch char sizes',[sum(len(x['text']) for x in b) for b in batches])
print('exact-dated chunks',sum(1 for c in chunks if c.get('date_exact')))
