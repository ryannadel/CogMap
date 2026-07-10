import json, re, math, hashlib, pathlib, datetime, os, sys
from collections import defaultdict, Counter
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cogmap_paths import WORK, OUTPUT
STATE = WORK
OUT = OUTPUT / 'knowledge-base-viz-data.json'

def sha(prefix, text): return prefix+'_'+hashlib.sha1(text.encode('utf-8','ignore')).hexdigest()[:12]

master = json.loads((STATE/'v3_chunks_master.json').read_text(encoding='utf-8'))
agg = json.loads((STATE/'v3_aggregate.json').read_text(encoding='utf-8'))
_res_path = STATE/'v3_resolved.json'
resolved = json.loads(_res_path.read_text(encoding='utf-8')) if _res_path.exists() else {'concepts': []}
sources = master['sources']
chunks = master['chunks']
chunks_by_id = {c['id']:c for c in chunks}

# Categories are whatever the resolver assigned -- derived from the data, not fixed.
_res_cats = [c.get('category') for c in resolved.get('concepts', []) if c.get('category')]
CATSET = set(_res_cats)
DEFAULT_CAT = Counter(_res_cats).most_common(1)[0][0] if _res_cats else 'General'

raw_concepts = agg['concepts']   # norm_name -> {name,type,definition,aliases,chunk_ids}
raw_names = set(raw_concepts.keys())

# ---- build canonical map from resolver, with lossless singleton fallback ----
name2canon = {}
canon_recs = {}
for c in resolved.get('concepts', []):
    canon = (c.get('canonical') or '').strip().lower()
    if not canon: continue
    if canon in canon_recs:  # merge dup canonical keys
        canon_recs[canon]['members'].update(m.lower() for m in c.get('members',[]))
        continue
    cat = c.get('category') if c.get('category') in CATSET else None
    canon_recs[canon] = {'canonical':canon,'label':c.get('label') or canon.title(),
        'type':c.get('type') or 'theme','category':cat or DEFAULT_CAT,
        'definition':c.get('definition') or '','members':set(m.lower() for m in c.get('members',[]))}
for canon,rec in canon_recs.items():
    for m in rec['members']:
        if m in raw_names and m not in name2canon:
            name2canon[m] = canon
# fallback: any raw name not mapped becomes its own canonical
unmapped = [n for n in raw_names if n not in name2canon]
for n in unmapped:
    canon = n
    if canon in canon_recs:
        canon = n+'#'+sha('x',n)[:4]
    rc = raw_concepts[n]
    canon_recs[canon] = {'canonical':canon,'label':n.title(),'type':rc.get('type','theme'),
        'category':DEFAULT_CAT,'definition':rc.get('definition',''),'members':{n}}
    name2canon[n]=canon
print('resolver clusters', len(resolved.get('concepts',[])), 'canonical after fallback', len(canon_recs), 'unmapped singletons', len(unmapped))

# ---- reading-position axis ----
NP = 40
orders = [c['order'] for c in chunks]; OMIN,OMAX=min(orders),max(orders)
def pos_bin(o): return min(NP-1, int((o-OMIN)/(OMAX-OMIN+1)*NP))
def pos_frac(o): return round((o-OMIN)/max(1,(OMAX-OMIN)),4)
date_anchors=[]; _seen=set()
for c in sorted(chunks,key=lambda c:c['order']):
    if c.get('date_exact') and c.get('date') and c['date'] not in _seen:
        date_anchors.append({'pos':pos_frac(c['order']),'bin':pos_bin(c['order']),'date':c['date']}); _seen.add(c['date'])
dated=[c for c in chunks if c.get('date')]
DATE_MIN=min(datetime.date.fromisoformat(c['date']) for c in dated) if dated else datetime.date.today()-datetime.timedelta(days=180)
DATE_MAX=max(datetime.date.fromisoformat(c['date']) for c in dated) if dated else datetime.date.today()

# ---- assemble canonical concepts ----
concepts=[]; concept_id_by_canon={}
for canon,rec in canon_recs.items():
    cids=set()
    for m in rec['members']:
        if m in raw_concepts: cids |= set(raw_concepts[m]['chunk_ids'])
    cids=[x for x in cids if x in chunks_by_id]
    if not cids: continue
    cid=sha('concept',canon); concept_id_by_canon[canon]=cid
    flow=[0]*NP; exact=[]
    for x in cids:
        ch=chunks_by_id[x]; flow[pos_bin(ch['order'])]+=1
        if ch.get('date_exact') and ch.get('date'): exact.append(ch['date'])
    src_set=set(chunks_by_id[x]['source_id'] for x in cids)
    orders_c=[chunks_by_id[x]['order'] for x in cids]
    first_pos=pos_frac(min(orders_c)); last_pos=pos_frac(max(orders_c)); recency=round(last_pos,3)
    prov=[{'source_id':chunks_by_id[x]['source_id'],'chunk_id':x,'char_span':chunks_by_id[x]['char_span']}
          for x in sorted(cids,key=lambda x:(chunks_by_id[x]['order'],x))[:16]]
    aliases=sorted(set().union(*[set(raw_concepts[m]['aliases'])|{m} for m in rec['members'] if m in raw_concepts]))
    sal=round(math.log1p(len(cids))*(1+len(src_set)*0.2)*(0.7+0.6*recency),3)
    concepts.append({'id':cid,'type':'Concept','label':rec['label'],'canonical':canon,'aliases':aliases[:24],
        'concept_type':rec['type'],'definition':rec['definition'],'category':rec['category'],
        'salience':sal,'confidence':round(min(0.95,0.55+0.05*len(cids)),2),'source_count':len(src_set),
        'mention_count':len(cids),'timeline':flow,'first_pos':first_pos,'last_pos':last_pos,'recency':recency,
        'first_date':min(exact) if exact else None,'last_date':max(exact) if exact else None,'provenance':prov})
concepts_by_id={c['id']:c for c in concepts}
# Minard lanes = the categories actually present, ordered by concept count.
CATS = [cat for cat,_ in Counter(c['category'] for c in concepts).most_common()] or [DEFAULT_CAT]
def cid_for(name): 
    canon=name2canon.get(name); return concept_id_by_canon.get(canon) if canon else None

# ---- claims ----
claims=[]; seen_claim=set()
for cl in agg['claims']:
    ch=chunks_by_id.get(cl['chunk_id'])
    if not ch: continue
    txt=cl['text'].strip()
    if len(txt)<12: continue
    key=(cl['chunk_id'], txt[:60].lower())
    if key in seen_claim: continue
    seen_claim.add(key)
    cinids=[cid_for(n) for n in cl['concepts']]; cinids=[x for x in dict.fromkeys(cinids) if x][:6]
    # category from majority of linked concepts else spec/agentic default
    cats=[concepts_by_id[x]['category'] for x in cinids if x in concepts_by_id]
    cat=Counter(cats).most_common(1)[0][0] if cats else DEFAULT_CAT
    st=cl['status'] if cl['status'] in ('Observation','Prediction','Decision','Question','Tension') else 'Observation'
    cid=sha('claim',cl['chunk_id']+txt[:50])
    claims.append({'id':cid,'type':'Claim','label':txt[:240],'status':st,'category':cat,
        'date':(ch.get('date') if ch.get('date_exact') else None) or (cl.get('date') if cl.get('date') else None),
        'salience':round(0.8+min(3,len(cinids)/2),3),'confidence':0.75,'concepts':cinids,
        'provenance':[{'source_id':ch['source_id'],'chunk_id':ch['id'],'char_span':ch['char_span']}]})
claims_by_id={c['id']:c for c in claims}

# ---- edges (typed, resolved, deduped) ----
TYPE_MAP={'enables':'ENABLES','causes':'CAUSES','depends_on':'DEPENDS_ON','part_of':'PART_OF',
          'refines':'EVOLVES_INTO','competes_with':'COMPETES_WITH','contradicts':'CONTRADICTS','relates_to':'RELATES_TO'}
agg_edges={}
for r in agg['relations']:
    a=cid_for(r['source']); b=cid_for(r['target'])
    if not a or not b or a==b: continue
    et=TYPE_MAP.get(r['type'],'RELATES_TO')
    # for symmetric-ish types sort endpoints; keep direction for enables/causes/depends_on/part_of/evolves_into
    directed = et in ('ENABLES','CAUSES','DEPENDS_ON','PART_OF','EVOLVES_INTO')
    key=(et, a, b) if directed else (et,)+tuple(sorted((a,b)))
    e=agg_edges.get(key)
    ev=[x for x in r['evidence'] if x in chunks_by_id]
    if not e:
        agg_edges[key]={'type':et,'source':key[1],'target':key[2],'weight':1,'ev':set(ev),'rat':r.get('rationale','')}
    else:
        e['weight']+=1; e['ev']|=set(ev)
edges=[]
for key,e in agg_edges.items():
    ev=sorted((x for x in e['ev'] if x in chunks_by_id),key=lambda x:(chunks_by_id[x]['order'],x))[:6]
    prov=[{'source_id':chunks_by_id[x]['source_id'],'chunk_id':x,'char_span':chunks_by_id[x]['char_span']} for x in ev]
    edges.append({'id':sha('edge',e['type']+e['source']+e['target']),'source':e['source'],'target':e['target'],
        'type':e['type'],'weight':e['weight'],'confidence':round(min(0.9,0.5+0.08*e['weight']),2),
        'rationale':e['rat'],'provenance':prov})

# ---- contradictions from CONTRADICTS edges + tension claims ----
contradictions=[]
for e in edges:
    if e['type']!='CONTRADICTS': continue
    a=concepts_by_id.get(e['source']); b=concepts_by_id.get(e['target'])
    if not a or not b: continue
    contradictions.append({'id':sha('con',e['source']+e['target']),'type':'CONTRADICTS','a':e['source'],'b':e['target'],
        'concept':e['source'],'confidence':e['confidence'],'a_label':a['label'],'b_label':b['label'],
        'summary':e.get('rationale') or f"Tension between {a['label']} and {b['label']}",'provenance':e['provenance']})
# supplement with tension claims sharing a concept with a non-tension claim
concept_to_claims=defaultdict(list)
for c in claims:
    for cc in c['concepts']: concept_to_claims[cc].append(c)
seenc=set(); tension_claims=[c for c in claims if c['status']=='Tension']
for tc in tension_claims:
    for cc in tc['concepts']:
        placed=False
        for other in concept_to_claims[cc]:
            if other['id']==tc['id'] or other['status'] in ('Tension','Question'): continue
            k=tuple(sorted((tc['id'],other['id'])))
            if k in seenc: continue
            seenc.add(k)
            cobj=concepts_by_id.get(cc)
            contradictions.append({'id':sha('con',tc['id']+other['id']),'type':'CONTRADICTS','a':other['id'] if False else cc,'b':cc,
                'concept':cc,'confidence':0.55,'a_label':other['label'],'b_label':tc['label'],
                'summary':f"Opposing takes on {cobj['label'] if cobj else 'a theme'}",
                'provenance':other['provenance'][:1]+tc['provenance'][:1]}); placed=True; break
        if placed: break
# de-dupe contradictions by id
_seen=set(); contradictions=[c for c in contradictions if not (c['id'] in _seen or _seen.add(c['id']))][:24]

# ---- river ----
river=[]
for cat in CATS:
    cc=[c for c in concepts if c['category']==cat]
    tl=[0]*NP
    for c in cc:
        for i,v in enumerate(c['timeline']): tl[i]+=v
    if sum(tl)==0: continue
    river.append({'category':cat,'timeline':tl,'total':sum(tl),
        'first_pos':min((c['first_pos'] for c in cc),default=0.0),
        'top_concepts':[{'id':c['id'],'label':c['label'],'salience':c['salience']} for c in sorted(cc,key=lambda c:-c['salience'])[:10]]})

# ---- insights (deterministic candidates; refined narrative later by synth) ----
insights=[]; third=max(1,NP//3)
for c in concepts:
    c['_mom']=sum(c['timeline'][-third:])-sum(c['timeline'][:third])
for c in sorted([c for c in concepts if c['_mom']>0 and c['mention_count']>=4],key=lambda c:-c['_mom'])[:6]:
    insights.append({'type':'Rising','icon':'\u2197','title':f"Rising: {c['label']}",
        'detail':f"Recurs far more in the later parts of your notebook than the early ({sum(c['timeline'][:third])} early \u2192 {sum(c['timeline'][-third:])} late) \u2014 a theme gaining momentum.",
        'node':c['id'],'category':c['category'],'provenance':c['provenance'][:3]})
for c in sorted([c for c in concepts if c['first_pos']>=(NP-third)/NP and c['mention_count']>=3],key=lambda c:-c['salience'])[:6]:
    insights.append({'type':'Emerging','icon':'\u2728','title':f"Newly emerging: {c['label']}",
        'detail':"Appears only late in your notebook and already recurring \u2014 a fresh line of thinking to watch.",
        'node':c['id'],'category':c['category'],'provenance':c['provenance'][:3]})
deg=defaultdict(set)
for e in edges:
    ca=concepts_by_id.get(e['source']); cb=concepts_by_id.get(e['target'])
    if ca and cb and ca['category']!=cb['category']:
        deg[e['source']].add(cb['category']); deg[e['target']].add(ca['category'])
for cidk,cs in sorted(deg.items(),key=lambda kv:-len(kv[1]))[:6]:
    c=concepts_by_id.get(cidk)
    if not c or len(cs)<2: continue
    insights.append({'type':'Bridge','icon':'\u2727','title':f"Bridging idea: {c['label']}",
        'detail':f"Connects {len(cs)} different areas ({', '.join(sorted(cs)[:3])}\u2026). Ideas that link domains are often where insight emerges.",
        'node':cidk,'category':c['category'],'provenance':c['provenance'][:3]})
for con in contradictions[:8]:
    cobj=concepts_by_id.get(con['concept'])
    insights.append({'type':'Tension','icon':'\u26a1','title':con.get('summary') or f"Tension around {cobj['label'] if cobj else 'a theme'}",
        'detail':f"\u201c{con['a_label'][:120]}\u201d  \u2194  \u201c{con['b_label'][:120]}\u201d",
        'node':con.get('concept'),'contradiction':con['id'],'provenance':con['provenance']})
for c in sorted([c for c in claims if c['status']=='Question'],key=lambda c:-c['salience'])[:6]:
    insights.append({'type':'Question','icon':'\u2753','title':'Open question','detail':c['label'],'node':(c['concepts'][0] if c['concepts'] else None),'category':c['category'],'provenance':c['provenance']})

# optional synth override of insight narrative
synth_path=STATE/'v3_insights.json'
if synth_path.exists():
    try:
        syn=json.loads(synth_path.read_text(encoding='utf-8'))
        by_node={}
        for s in syn.get('insights',[]):
            by_node[(s.get('type'),s.get('node'))]=s
        for ins in insights:
            s=by_node.get((ins['type'],ins.get('node')))
            if s:
                if s.get('title'): ins['title']=s['title']
                if s.get('detail'): ins['detail']=s['detail']
        # synthesis insights: cross-cutting, provenance derived from referenced concept nodes
        synth_cards=[]
        for s in syn.get('synthesis',[]):
            nodes=[n for n in (s.get('nodes') or []) if n in concepts_by_id]
            if not s.get('title') or not s.get('detail'): continue
            prov=[]; seen_ch=set()
            for n in nodes:
                for p in concepts_by_id[n]['provenance']:
                    if p['chunk_id'] not in seen_ch: prov.append(p); seen_ch.add(p['chunk_id'])
                    if len(prov)>=6: break
            cat=Counter(concepts_by_id[n]['category'] for n in nodes).most_common(1)[0][0] if nodes else None
            synth_cards.append({'type':'Synthesis','icon':'\U0001f4a1','title':s['title'][:140],'detail':s['detail'][:400],
                'node':(nodes[0] if nodes else None),'nodes':nodes,'category':cat,'provenance':prov[:6]})
        # place synthesis cards at the very top (highest-value emergent reasoning)
        insights = synth_cards + insights
    except Exception as ex:
        print('synth load skipped', ex)

# ---- assemble ----
categories=[{'id':sha('cat',n),'type':'Category','label':n} for n in CATS]
counts={'sources':len(sources),'chunks':len(chunks),'concepts':len(concepts),'claims':len(claims),
        'categories':len(categories),'relations':sum(1 for e in edges if e['type']=='RELATES_TO'),
        'typed_relations':len(edges),'evolves':sum(1 for e in edges if e['type']=='EVOLVES_INTO'),
        'contradictions':len(contradictions),'insights':len(insights)}
status_counts=Counter(c['status'] for c in claims)
out={'metadata':{'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'generator':'v3 (LLM semantic extraction + entity resolution + typed relations + synthesized insights)',
      'value_prop':'evolution of ideas across the notebook + emergent insights, every node traceable to source',
      'axis':'reading progression through the notebook (chunk order); real dates shown as anchors',
      'date_min':DATE_MIN.isoformat(),'date_max':DATE_MAX.isoformat(),'np':NP,'date_anchors':date_anchors,
      'anchor_dates':len(date_anchors),'method':'per-chunk LLM extraction over 15 batches; Opus entity resolution; typed relation synthesis',
      'status_counts':dict(status_counts),'counts':counts,
      'completeness_note':'Concepts, claims and relations are LLM-extracted with source provenance and cross-batch entity resolution. Flow axis is real reading order; explicit calendar dates pinned as anchors.'},
     'sources':sources,
     'chunks':[{'id':c['id'],'source_id':c['source_id'],'heading':c['heading'],'text':c['text'],'char_span':c['char_span'],'line':c['line'],'order':c['order'],'date':c.get('date'),'date_exact':c.get('date_exact',False),'dup_count':c['dup_count']} for c in chunks],
     'categories':categories,
     'concepts':[{k:v for k,v in c.items() if not k.startswith('_')} for c in concepts],
     'claims':claims,'edges':edges,'contradictions':contradictions,'river':river,'insights':insights}
OUT.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print('counts',json.dumps(counts))
print('edge types',dict(Counter(e['type'] for e in edges)))
print('status',dict(status_counts))
print('river lanes',len(river),'insights',len(insights),'contradictions',len(contradictions))
print('bytes',OUT.stat().st_size)
