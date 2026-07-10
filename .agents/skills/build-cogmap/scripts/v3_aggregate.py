import json, re, pathlib, os, sys
from collections import defaultdict, Counter
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cogmap_paths import WORK
STATE = WORK
EX = STATE / 'v3_extract'

master = json.loads((STATE/'v3_chunks_master.json').read_text(encoding='utf-8'))
valid_ids = {c['id'] for c in master['chunks']}

def norm_name(n):
    n = re.sub(r'\s+',' ', (n or '').strip().lower())
    n = n.strip('.,;:"\u201c\u201d')
    return n

concepts_raw = {}      # norm_name -> {name, types:Counter, defs:[], aliases:set, chunk_ids:set, freq}
claims_all = []
relations_all = []
dropped_chunkrefs = 0

files = sorted(EX.glob('extract_*.json'))
for f in files:
    try:
        e = json.loads(f.read_text(encoding='utf-8'))
    except Exception as ex:
        print('PARSE FAIL', f.name, ex); continue
    for c in e.get('concepts', []):
        key = norm_name(c.get('name'))
        if not key or len(key) < 2: continue
        rec = concepts_raw.setdefault(key, {'name':key,'types':Counter(),'defs':[],'aliases':set(),'chunk_ids':set(),'freq':0})
        if c.get('type'): rec['types'][c['type']] += 1
        if c.get('definition'): rec['defs'].append(c['definition'])
        for a in c.get('aliases',[]) or []:
            if a: rec['aliases'].add(a)
        for cid in c.get('chunk_ids',[]) or []:
            if cid in valid_ids: rec['chunk_ids'].add(cid)
        rec['freq'] += 1
    for cl in e.get('claims', []):
        cid = cl.get('chunk_id')
        if cid not in valid_ids:
            dropped_chunkrefs += 1; continue
        claims_all.append({'text':cl.get('text','')[:240],'status':cl.get('status','Observation'),
                           'concepts':[norm_name(x) for x in cl.get('concepts',[]) or []],
                           'chunk_id':cid,'date':cl.get('date')})
    for r in e.get('relations', []):
        s,t = norm_name(r.get('source')), norm_name(r.get('target'))
        if not s or not t or s==t: continue
        ev=[x for x in (r.get('evidence_chunk_ids') or []) if x in valid_ids]
        relations_all.append({'source':s,'target':t,'type':r.get('type','relates_to'),
                              'evidence':ev,'rationale':(r.get('rationale') or '')[:160]})

# serialize raw concepts for resolver (compact)
raw_out = []
for k,v in sorted(concepts_raw.items(), key=lambda kv:-len(kv[1]['chunk_ids'])):
    raw_out.append({'name':v['name'],
                    'type':(v['types'].most_common(1)[0][0] if v['types'] else 'theme'),
                    'definition':(sorted(v['defs'],key=len)[len(v['defs'])//2] if v['defs'] else ''),
                    'aliases':sorted(v['aliases'])[:6],
                    'mentions':len(v['chunk_ids'])})

(STATE/'v3_raw_concepts.json').write_text(json.dumps(raw_out,ensure_ascii=False,indent=1),encoding='utf-8')
# cache full aggregate (with chunk_ids) for assembly
cache = {'concepts':{k:{'name':v['name'],'type':(v['types'].most_common(1)[0][0] if v['types'] else 'theme'),
                        'definition':(sorted(v['defs'],key=len)[len(v['defs'])//2] if v['defs'] else ''),
                        'aliases':sorted(v['aliases']),'chunk_ids':sorted(v['chunk_ids'])} for k,v in concepts_raw.items()},
         'claims':claims_all,'relations':relations_all}
(STATE/'v3_aggregate.json').write_text(json.dumps(cache,ensure_ascii=False),encoding='utf-8')

print('extract files', len(files))
print('unique raw concepts', len(concepts_raw))
print('claims', len(claims_all), 'relations', len(relations_all))
print('dropped bad chunkrefs (claims)', dropped_chunkrefs)
rt=Counter(r['type'] for r in relations_all); print('rel types', dict(rt))
st=Counter(c['status'] for c in claims_all); print('claim status', dict(st))
