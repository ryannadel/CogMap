import json, pathlib, os, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cogmap_paths import OUTPUT
DATA = OUTPUT / 'knowledge-base-viz-data.json'
OUT = OUTPUT / 'knowledge-base-viz.html'
data = DATA.read_text(encoding='utf-8')

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>CogMap \u2014 Idea Evolution</title>
<script>
  (() => {
    const param = new URLSearchParams(window.location.search).get("clawpilotTheme");
    const theme = param || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
  })();
</script>
<style>
:root{
  color-scheme:light;
  --cp-bg:#f7f4ef;--cp-bg-elevated:#fcfbf8;--cp-surface:#ffffff;--cp-surface-soft:#f5f5f5;
  --cp-border:#dedede;--cp-border-strong:#919191;--cp-text:#242424;--cp-text-muted:#5c5c5c;--cp-text-soft:#6f6f6f;
  --cp-accent:#b11f4b;--cp-accent-hover:#9a1a41;--cp-accent-soft:rgba(177,31,75,.08);--cp-accent-fg:#ffffff;
  --cp-success:#16a34a;--cp-danger:#dc2626;--cp-warning:#f59e0b;--cp-link:#0078d4;
  --cp-shadow:0 18px 48px rgba(0,0,0,.12);--cp-overlay:rgba(255,255,255,.8);
  --cp-panel:rgba(255,255,255,.86);--cp-panel-strong:rgba(255,255,255,.96);--cp-sheen:rgba(255,255,255,.55);
  --cp-highlight:rgba(177,31,75,.12);
  --c0:#b11f4b;--c1:#c26a2b;--c2:#b8902a;--c3:#5f8f3a;--c4:#2f8f78;--c5:#2f7fae;--c6:#4a5fb0;--c7:#7d4fa8;--c8:#a8477d;--c9:#7a6a55;
  --map-bg:#efe9df;
}
html[data-theme="dark"]{
  color-scheme:dark;
  --cp-bg:#3d3b3a;--cp-bg-elevated:#343231;--cp-surface:#292929;--cp-surface-soft:#2e2e2e;
  --cp-border:#474747;--cp-border-strong:#5f5f5f;--cp-text:#dedede;--cp-text-muted:#919191;--cp-text-soft:#b0b0b0;
  --cp-accent:#fd8ea1;--cp-accent-hover:#fb7b91;--cp-accent-soft:rgba(253,142,161,.14);--cp-accent-fg:#1a1a1a;
  --cp-success:#4ade80;--cp-danger:#f87171;--cp-warning:#fbbf24;--cp-link:#4da6ff;
  --cp-shadow:0 18px 48px rgba(0,0,0,.32);--cp-overlay:rgba(41,41,41,.88);
  --cp-panel:rgba(41,41,41,.72);--cp-panel-strong:rgba(41,41,41,.96);--cp-sheen:rgba(255,255,255,.04);
  --cp-highlight:rgba(253,142,161,.12);
  --c0:#fd8ea1;--c1:#e9a05f;--c2:#d8c05a;--c3:#8fc46a;--c4:#5ec4ab;--c5:#66b6e0;--c6:#8a9ae8;--c7:#b487e0;--c8:#e084b6;--c9:#c3b08e;
  --map-bg:#2b2926;
}
*{box-sizing:border-box}
body{margin:0;font-family:"Segoe UI",Aptos,Calibri,-apple-system,BlinkMacSystemFont,sans-serif;
  background:var(--cp-bg);color:var(--cp-text);font-size:14px;line-height:1.5}
code,.mono{font-family:Consolas,"Courier New",Courier,monospace}
header{display:flex;align-items:center;gap:16px;padding:14px 22px;border-bottom:1px solid var(--cp-border);
  background:var(--cp-bg-elevated);position:sticky;top:0;z-index:20}
.brand{font-weight:700;font-size:16px;letter-spacing:.2px}
.brand small{display:block;font-weight:400;color:var(--cp-text-muted);font-size:11px;letter-spacing:0}
.tabs{display:flex;gap:6px;margin-left:8px}
.tab{padding:7px 14px;border-radius:.625rem;border:1px solid transparent;background:transparent;color:var(--cp-text-muted);
  cursor:pointer;font-size:13px;font-weight:600}
.tab:hover{background:var(--cp-surface-soft);color:var(--cp-text)}
.tab.active{background:var(--cp-accent-soft);color:var(--cp-accent);border-color:var(--cp-accent-soft)}
.spacer{flex:1}
.search input{background:var(--cp-surface);border:1px solid var(--cp-border);color:var(--cp-text);
  border-radius:.625rem;padding:8px 12px;width:230px;font-size:13px}
main{display:grid;grid-template-columns:1fr 380px;height:calc(100vh - 59px)}
.stage{overflow:auto;padding:22px}
.inspector{border-left:1px solid var(--cp-border);background:var(--cp-bg-elevated);overflow:auto;padding:18px}
.view{display:none}.view.active{display:block}
h2.section{font-size:15px;margin:0 0 4px}
.sub{color:var(--cp-text-muted);font-size:12.5px;margin:0 0 16px;max-width:78ch}
/* flow map */
#flowWrap{background:var(--map-bg);border:1px solid var(--cp-border);border-radius:16px;padding:6px 6px 0;position:relative;overflow:auto}
.ribbon{cursor:pointer;transition:opacity .12s}
.ribbon.dim{opacity:.12}
.rlabel{font-size:12px;font-weight:700;paint-order:stroke;stroke:var(--map-bg);stroke-width:3px;pointer-events:none}
.lane-name{font-size:12.5px;font-weight:700}
.lane-sub{font-size:10px}
.tick-lead{stroke:var(--cp-border-strong);opacity:.5}
.tick-lbl{font-size:9.5px;paint-order:stroke;stroke:var(--map-bg);stroke-width:2.5px}
.tick:hover .tick-lbl{fill:var(--cp-accent);stroke:var(--map-bg)}
.evt:hover circle{stroke-width:2.4px}
.axis-tick text{fill:var(--cp-text-muted);font-size:10px}
.axis-tick line{stroke:var(--cp-border-strong);opacity:.5}
.anchor-lbl{fill:var(--cp-text);font-size:10px;font-weight:600;paint-order:stroke;stroke:var(--map-bg);stroke-width:3px}
.anchor-line{stroke:var(--cp-border-strong);stroke-dasharray:2 3;opacity:.55}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 4px}
.legend .li{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--cp-text-muted);cursor:pointer;padding:3px 7px;border-radius:6px;border:1px solid transparent}
.legend .li:hover{background:var(--cp-surface-soft)}
.legend .li.dim{opacity:.4}
.legend .sw{width:12px;height:12px;border-radius:3px}
/* insights */
.filterbar{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}
.fpill{font-size:12px;padding:5px 11px;border-radius:999px;border:1px solid var(--cp-border);background:var(--cp-surface);cursor:pointer;color:var(--cp-text-muted);font-weight:600}
.fpill.active{background:var(--cp-accent);border-color:var(--cp-accent);color:var(--cp-accent-fg)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.card{background:var(--cp-surface);border:1px solid var(--cp-border);border-radius:16px;padding:14px 15px;cursor:pointer;
  box-shadow:0 0 2px rgba(0,0,0,.12),0 1px 2px rgba(0,0,0,.14);transition:transform .08s,border-color .12s;border-left-width:4px}
.card:hover{transform:translateY(-2px);border-color:var(--cp-border-strong)}
.card .ttl{font-weight:700;font-size:13.5px;display:flex;gap:8px;align-items:flex-start;margin-bottom:6px}
.card .ico{font-size:16px;line-height:1}
.card .det{font-size:12.5px;color:var(--cp-text-muted)}
.card .tag{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;font-weight:700;color:var(--cp-text-soft)}
.spark{display:block;margin-top:8px}
/* explorer */
.row{display:flex;align-items:center;gap:12px;padding:9px 11px;border:1px solid var(--cp-border);border-radius:12px;
  background:var(--cp-surface);margin-bottom:8px;cursor:pointer}
.row:hover{border-color:var(--cp-border-strong)}
.row .lab{font-weight:600;flex:1;font-size:13px}
.row .meta{font-size:11px;color:var(--cp-text-muted);white-space:nowrap}
.dot{width:9px;height:9px;border-radius:50%;flex:none}
.mom{font-size:11px;font-weight:700}
.mom.up{color:var(--cp-success)}.mom.down{color:var(--cp-text-muted)}
/* inspector */
.ins-empty{color:var(--cp-text-muted);font-size:13px;text-align:center;margin-top:40px}
.ins-h{font-size:16px;font-weight:700;margin:0 0 6px}
.badges{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.badge{font-size:11px;padding:3px 9px;border-radius:999px;font-weight:600}
.b-cat{background:var(--cp-surface-soft);border:1px solid var(--cp-border);color:var(--cp-text)}
.b-obs{background:var(--cp-surface-soft);color:var(--cp-text-muted);border:1px solid var(--cp-border)}
.b-dec{background:rgba(22,163,74,.14);color:var(--cp-success)}
.b-pred{background:rgba(0,120,212,.14);color:var(--cp-link)}
.b-ten{background:rgba(220,38,38,.14);color:var(--cp-danger)}
.b-que{background:rgba(245,158,11,.16);color:var(--cp-warning)}
.kv{display:flex;gap:14px;margin:10px 0;font-size:12px;color:var(--cp-text-muted);flex-wrap:wrap}
.kv b{color:var(--cp-text);font-size:13px}
.mini-label{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--cp-text-soft);font-weight:700;margin:16px 0 7px}
.prov{border:1px solid var(--cp-border);border-radius:12px;padding:10px 11px;margin-bottom:8px;background:var(--cp-surface);cursor:pointer;transition:border-color .12s,background .12s}
.prov:hover{border-color:var(--cp-accent);background:var(--cp-accent-soft)}
.prov .src{font-size:11px;color:var(--cp-accent);font-weight:700;display:flex;justify-content:space-between;gap:8px}
.prov .txt{font-size:12.5px;margin-top:5px;color:var(--cp-text)}
.prov .loc{font-size:10.5px;color:var(--cp-text-muted);margin-top:5px;display:flex;justify-content:space-between;gap:8px;align-items:center}
.prov .more{font-size:10.5px;color:var(--cp-link);font-weight:700;white-space:nowrap}
.note-modal{position:fixed;inset:0;background:var(--cp-overlay);display:none;align-items:center;justify-content:center;z-index:60;padding:24px}
.note-modal.open{display:flex}
.note-card{background:var(--cp-surface);border:1px solid var(--cp-border);border-radius:16px;max-width:720px;width:100%;max-height:82vh;overflow:auto;box-shadow:var(--cp-shadow);padding:22px 26px;position:relative}
.note-close{position:absolute;top:10px;right:14px;border:none;background:transparent;font-size:24px;line-height:1;color:var(--cp-text-muted);cursor:pointer}
.note-close:hover{color:var(--cp-text)}
.note-meta{font-size:11.5px;color:var(--cp-accent);font-weight:700;margin-bottom:6px;padding-right:26px}
.note-title{font-size:12px;color:var(--cp-text-muted);margin-bottom:14px;padding-right:26px}
.note-body p{font-size:14px;line-height:1.62;color:var(--cp-text);margin:0 0 12px}
.note-body mark{background:var(--cp-highlight);color:var(--cp-text);padding:1px 3px;border-radius:3px;box-shadow:inset 0 -2px 0 var(--cp-accent-soft)}
.rel{display:inline-block;font-size:11.5px;padding:4px 9px;border-radius:999px;border:1px solid var(--cp-border);
  margin:0 5px 5px 0;cursor:pointer;background:var(--cp-surface);color:var(--cp-text)}
.rel:hover{border-color:var(--cp-accent);color:var(--cp-accent)}
.tension-side{border-left:3px solid var(--cp-border);padding-left:10px;margin:8px 0}
.tension-side.a{border-color:var(--cp-link)}.tension-side.b{border-color:var(--cp-danger)}
.tooltip{position:fixed;pointer-events:none;background:var(--cp-panel-strong);border:1px solid var(--cp-border);
  border-radius:10px;padding:8px 11px;font-size:12px;box-shadow:var(--cp-shadow);z-index:50;max-width:280px;display:none}
::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:var(--cp-border-strong);border-radius:6px}
</style>
</head>
<body>
<header>
  <div class="brand">CogMap<small>How your thinking evolved across the notebook \u2014 every claim traceable to source</small></div>
  <div class="tabs">
    <button class="tab active" data-view="flow">Knowledge march</button>
    <button class="tab" data-view="insights">Insights</button>
    <button class="tab" data-view="explorer">Explorer</button>
    <button class="tab" data-view="sources">Sources</button>
  </div>
  <div class="spacer"></div>
  <div class="search"><input id="q" placeholder="Search concepts & claims\u2026" /></div>
</header>
<main>
  <div class="stage">
    <section class="view active" id="view-flow"></section>
    <section class="view" id="view-insights"></section>
    <section class="view" id="view-explorer"></section>
    <section class="view" id="view-sources"></section>
  </div>
  <aside class="inspector" id="inspector"><div class="ins-empty">Select a stream, insight, or concept to see how it evolved and trace it back to the source.</div></aside>
</main>
<div class="tooltip" id="tip"></div>
<div class="note-modal" id="noteModal"><div class="note-card"><button class="note-close" id="noteClose">\u00d7</button><div class="note-meta" id="noteMeta"></div><div class="note-title" id="noteTitle"></div><div class="note-body" id="noteBody"></div></div></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const CATS = DATA.categories.map(c=>c.label);
const CATCOLOR = {}; CATS.forEach((c,i)=>CATCOLOR[c]='var(--c'+(i%10)+')');
const conceptById={},claimById={},chunkById={},sourceById={};
DATA.concepts.forEach(c=>conceptById[c.id]=c);
DATA.claims.forEach(c=>claimById[c.id]=c);
DATA.chunks.forEach(c=>chunkById[c.id]=c);
DATA.sources.forEach(s=>sourceById[s.id]=s);
const tip=document.getElementById('tip');
function showTip(html,x,y){tip.innerHTML=html;tip.style.display='block';tip.style.left=Math.min(x+14,innerWidth-290)+'px';tip.style.top=(y+14)+'px';}
function hideTip(){tip.style.display='none';}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function fmtDate(d){if(!d)return '\u2014';const dt=new Date(d);return dt.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});}

/* ---------- smoothing (Catmull-Rom -> bezier path) ---------- */
function smoothPath(pts){
  if(pts.length<2)return '';
  let d='M'+pts[0][0].toFixed(1)+','+pts[0][1].toFixed(1);
  for(let i=0;i<pts.length-1;i++){
    const p0=pts[i-1]||pts[i], p1=pts[i], p2=pts[i+1], p3=pts[i+2]||p2;
    const c1x=p1[0]+(p2[0]-p0[0])/6, c1y=p1[1]+(p2[1]-p0[1])/6;
    const c2x=p2[0]-(p3[0]-p1[0])/6, c2y=p2[1]-(p3[1]-p1[1])/6;
    d+=' C'+c1x.toFixed(1)+','+c1y.toFixed(1)+' '+c2x.toFixed(1)+','+c2y.toFixed(1)+' '+p2[0].toFixed(1)+','+p2[1].toFixed(1);
  }
  return d;
}

/* ---------- sparkline (position flow) ---------- */
function sparkline(timeline,color,w=120,h=26){
  const max=Math.max(1,...timeline);const n=timeline.length;
  const pts=timeline.map((v,i)=>[i/(n-1)*w, h-2 - (v/max)*(h-4)]);
  const d=smoothPath(pts);
  const area=d+` L${w},${h} L0,${h} Z`;
  return `<svg class="spark" width="${w}" height="${h}"><path d="${area}" fill="${color}" opacity="0.14"/><path d="${d}" fill="none" stroke="${color}" stroke-width="1.6"/></svg>`;
}

/* ---------- INSPECTOR ---------- */
function provBlock(p){
  const ch=chunkById[p.chunk_id]||{};const s=sourceById[p.source_id]||{};
  const loc=[ch.line?('line '+ch.line):null, ch.date_exact?('\uD83D\uDCC5 '+fmtDate(ch.date)):('pos '+Math.round((ch.order/DATA.chunks.length)*100)+'%'),
             p.char_span?('chars '+p.char_span[0]+'\u2013'+p.char_span[1]):null].filter(Boolean).join(' \u00b7 ');
  return `<div class="prov" data-note="${p.chunk_id}"><div class="src"><span>${esc(s.title||p.source_id)}</span><span>${esc(ch.heading||'')}</span></div>
    <div class="txt">\u201c${esc((ch.text||'').slice(0,300))}${(ch.text||'').length>300?'\u2026':''}\u201d</div>
    <div class="loc"><span>${loc}</span><span class="more">Read full note \u25b8</span></div></div>`;
}
/* ---------- full-note reading modal ---------- */
function noteContext(chunkId){
  const t=chunkById[chunkId]; if(!t) return null;
  const same=DATA.chunks.filter(c=>c.source_id===t.source_id).slice().sort((a,b)=>a.order-b.order);
  const idx=same.findIndex(c=>c.id===chunkId);
  if(idx<0) return {parts:[{c:t,target:true}],t};
  let lo=idx,hi=idx,bl=1100,bh=1100;
  while(lo>0){const L=(same[lo-1].text||'').length; if(bl-L<0)break; bl-=L; lo--;}
  while(hi<same.length-1){const L=(same[hi+1].text||'').length; if(bh-L<0)break; bh-=L; hi++;}
  const parts=[];
  for(let k=lo;k<=hi;k++)parts.push({c:same[k],target:same[k].id===chunkId});
  return {parts,t};
}
function openFullNote(chunkId){
  const ctx=noteContext(chunkId); if(!ctx) return;
  const t=ctx.t; const s=sourceById[t.source_id]||{};
  const meta=[s.title||t.source_id, t.line?('line '+t.line):null,
    t.date_exact?('\uD83D\uDCC5 '+fmtDate(t.date)):('pos '+Math.round((t.order/DATA.chunks.length)*100)+'%')].filter(Boolean).join(' \u00b7 ');
  const paras=[]; let cur=[]; let lastLine=undefined;
  ctx.parts.forEach((p,i)=>{
    const c=p.c;
    if(i>0 && (c.line==null || c.line!==lastLine)){ paras.push(cur); cur=[]; }
    lastLine=c.line;
    const body=esc(c.text||'');
    cur.push(p.target?('<mark>'+body+'</mark>'):body);
  });
  if(cur.length) paras.push(cur);
  document.getElementById('noteMeta').textContent=meta;
  document.getElementById('noteTitle').textContent=t.heading||'';
  document.getElementById('noteBody').innerHTML=paras.map(pp=>'<p>'+pp.join(' ')+'</p>').join('');
  document.getElementById('noteModal').classList.add('open');
}
function closeNote(){document.getElementById('noteModal').classList.remove('open');}
function statusBadge(st){const m={Observation:'b-obs',Decision:'b-dec',Prediction:'b-pred',Tension:'b-ten',Question:'b-que'};return `<span class="badge ${m[st]||'b-obs'}">${st}</span>`;}
function posPct(f){return Math.round((f||0)*100)+'%';}
function textWidthEstimate(s){
  return Array.from(s||'').reduce((w,ch)=>w+(ch===' '?3.7:/[A-Z0-9&]/.test(ch)?7.4:6.3),0);
}
function ellipsize(s,maxChars){
  s=s||'';
  return s.length>maxChars ? s.slice(0,Math.max(1,maxChars-1)).trimEnd()+'\u2026' : s;
}
function inspectConcept(c){
  const color=CATCOLOR[c.category];
  const chip=o=>`<span class="rel" data-cid="${o.id}">${esc(o.label)}</span>`;
  function group(pred){
    const seen={};
    DATA.edges.forEach(e=>{const o=pred(e);if(o&&conceptById[o]&&!seen[o])seen[o]=1;});
    return Object.keys(seen).map(id=>chip(conceptById[id])).join('');
  }
  const G=[
    ['Enables', e=>e.type==='ENABLES'&&e.source===c.id?e.target:null],
    ['Enabled by', e=>e.type==='ENABLES'&&e.target===c.id?e.source:null],
    ['Depends on', e=>e.type==='DEPENDS_ON'&&e.source===c.id?e.target:null],
    ['Leads to', e=>e.type==='CAUSES'&&e.source===c.id?e.target:null],
    ['Evolves into', e=>e.type==='EVOLVES_INTO'&&e.source===c.id?e.target:null],
    ['Part of', e=>e.type==='PART_OF'&&e.source===c.id?e.target:null],
    ['Includes', e=>e.type==='PART_OF'&&e.target===c.id?e.source:null],
    ['Competes with', e=>e.type==='COMPETES_WITH'&&(e.source===c.id||e.target===c.id)?(e.source===c.id?e.target:e.source):null],
    ['Related', e=>e.type==='RELATES_TO'&&(e.source===c.id||e.target===c.id)?(e.source===c.id?e.target:e.source):null],
  ];
  const relHtml=G.map(([lbl,pred])=>{const h=group(pred);return h?`<div class="mini-label">${lbl}</div>${h}`:'';}).join('');
  const third=Math.floor(c.timeline.length/3);
  const mom=c.timeline.slice(-third).reduce((a,b)=>a+b,0)-c.timeline.slice(0,third).reduce((a,b)=>a+b,0);
  document.getElementById('inspector').innerHTML=
    `<div class="ins-h">${esc(c.label)}</div>
     <div class="badges"><span class="badge b-cat" style="border-color:${color}">${esc(c.category)}</span>
       ${c.concept_type?`<span class="badge b-obs">${esc(c.concept_type)}</span>`:''}
       <span class="badge b-obs">${mom>0?'\u2197 rising':mom<0?'\u2198 earlier':'\u2192 steady'}</span>
       ${c.first_date?`<span class="badge b-obs">first dated ${fmtDate(c.first_date)}</span>`:''}</div>
     ${c.definition?`<div style="font-size:13px;color:var(--cp-text);margin:8px 0 4px;line-height:1.4">${esc(c.definition)}</div>`:''}
     <div class="mini-label">Presence across the notebook (start \u2192 end)</div>${sparkline(c.timeline,color,340,54)}
     <div class="kv"><span>First appears<br><b>${posPct(c.first_pos)}</b></span><span>Last appears<br><b>${posPct(c.last_pos)}</b></span>
       <span>Mentions<br><b>${c.mention_count}</b></span><span>Sources<br><b>${c.source_count}</b></span></div>
     ${c.aliases&&c.aliases.length>1?`<div class="mini-label">Merged aliases (${c.aliases.length})</div><div style="font-size:12px;color:var(--cp-text-muted)">${c.aliases.slice(0,16).map(esc).join(' \u00b7 ')}</div>`:''}
     ${relHtml}
     <div class="mini-label">Source provenance (${c.provenance.length})</div>${c.provenance.map(provBlock).join('')}`;
  bindRels();
}
function inspectClaim(c){
  document.getElementById('inspector').innerHTML=
    `<div class="badges">${statusBadge(c.status)}<span class="badge b-cat">${esc(c.category)}</span>${c.date?`<span class="badge b-obs">${fmtDate(c.date)}</span>`:''}</div>
     <div class="ins-h" style="font-size:14px;font-weight:600">\u201c${esc(c.label)}\u201d</div>
     ${c.concepts&&c.concepts.length?`<div class="mini-label">Concepts referenced</div>${c.concepts.map(id=>{const o=conceptById[id];return o?`<span class="rel" data-cid="${o.id}">${esc(o.label)}</span>`:''}).join('')}`:''}
     <div class="mini-label">Source provenance</div>${c.provenance.map(provBlock).join('')}`;
  bindRels();
}
function inspectContradiction(con){
  const a=claimById[con.a],b=claimById[con.b];const cc=conceptById[con.concept];
  document.getElementById('inspector').innerHTML=
    `<div class="badges"><span class="badge b-ten">\u26a1 Tension</span>${cc?`<span class="badge b-cat" data-cid="${cc.id}" style="cursor:pointer">${esc(cc.label)}</span>`:''}</div>
     ${con.summary?`<div style="font-size:13px;margin-bottom:10px">${esc(con.summary)}</div>`:''}
     <div class="mini-label">Two takes in tension</div>
     <div class="tension-side a"><div style="font-size:11px;color:var(--cp-link);font-weight:700">${a?a.status:''}</div>\u201c${esc(con.a_label)}\u201d</div>
     <div class="tension-side b"><div style="font-size:11px;color:var(--cp-danger);font-weight:700">${b?b.status:''}</div>\u201c${esc(con.b_label)}\u201d</div>
     <div class="mini-label">Source provenance</div>${con.provenance.map(provBlock).join('')}`;
  bindRels();
}
function bindRels(){document.querySelectorAll('#inspector [data-cid]').forEach(el=>el.onclick=()=>{const c=conceptById[el.getAttribute('data-cid')];if(c)inspectConcept(c);});
  document.querySelectorAll('#inspector [data-note]').forEach(el=>el.onclick=(e)=>{e.stopPropagation();openFullNote(el.getAttribute('data-note'));});}
function openNode(id){if(conceptById[id])inspectConcept(conceptById[id]);else if(claimById[id])inspectClaim(claimById[id]);}

/* ---------- FLOW MAP (Minard-style flowing ribbons over reading progression) ---------- */
let hiddenCats=new Set();
let focusCat=null;
const NP=DATA.metadata.np;
const _peak=t=>{let wi=0,wm=-1;t.forEach((v,i)=>{if(v>wm){wm=v;wi=i;}});return wi;};
function buildSeries(){
  if(!focusCat){
    return DATA.river.filter(r=>!hiddenCats.has(r.category))
      .map(r=>({key:r.category,label:r.category,color:CATCOLOR[r.category],timeline:r.timeline,first_pos:r.first_pos,total:r.total,drill:true,
                tops:r.top_concepts.slice(0,5).map(c=>c.label),cid:(r.top_concepts[0]||{}).id,
                concepts:DATA.concepts.filter(c=>c.category===r.category)}));
  }
  const cs=DATA.concepts.filter(c=>c.category===focusCat).sort((a,b)=>b.salience-a.salience).slice(0,8);
  return cs.map((c,i)=>({key:c.id,label:c.label,color:'var(--c'+(i%10)+')',timeline:c.timeline,first_pos:c.first_pos,
                         total:c.mention_count,drill:false,tops:[c.label],cid:c.id,concepts:[c]}));
}
// events layer: emerging concepts + tensions, positioned by reading order
function eventsFor(catKey){
  const evs=[];
  DATA.insights.filter(i=>i.type==='Emerging'&&i.node&&conceptById[i.node]).forEach(i=>{
    const c=conceptById[i.node]; if(focusCat? c.id===catKey : c.category===catKey) evs.push({icon:'\u2728',type:'Emerging',pos:c.first_pos,label:c.label,node:c.id});
  });
  DATA.contradictions.forEach(con=>{
    const c=conceptById[con.concept]; if(!c) return;
    if(focusCat? c.id===catKey : c.category===catKey) evs.push({icon:'\u26a1',type:'Tension',pos:c.timeline?_peak(c.timeline)/(NP-1):c.first_pos,label:con.summary||('Tension: '+c.label),con:con.id});
  });
  return evs;
}
function renderFlow(){
  const stage=document.querySelector('.stage');
  const series=buildSeries();
  series.sort((a,b)=>b.total-a.total);
  const nL=series.length;
  const laneLabels=series.map(s=>s.label).concat(['evidence density']);
  const leftGutter=Math.ceil(Math.min(320,Math.max(210,Math.max(...laneLabels.map(textWidthEstimate))+28)));
  const m={t:86,r:32,b:18,l:leftGutter};
  const W=Math.max(m.l+620+m.r,stage.clientWidth-44);
  const laneH=Math.max(52,Math.min(74,Math.floor(420/Math.max(1,nL))+34));
  const bandH=64, bandGap=18;
  const plotW=W-m.l-m.r;
  const H=m.t+nL*laneH+bandGap+bandH+m.b;
  const x=f=>m.l+f*plotW;               // f in [0,1]
  const xi=i=>x(i/(NP-1));
  // global thickness scale
  let gmax=1; series.forEach(s=>s.timeline.forEach(v=>{if(v>gmax)gmax=v;}));
  const half=v=>Math.sqrt(v/gmax)*(laneH*0.40);   // sqrt keeps thin lanes visible
  let svg='';
  // date anchors (vertical guide lines + top labels)
  const anchorRows=[-Infinity,-Infinity,-Infinity];
  (DATA.metadata.date_anchors||[]).slice().sort((a,b)=>a.pos-b.pos).forEach(a=>{
    const ax=x(a.pos);
    const label=new Date(a.date).toLocaleDateString(undefined,{month:'short',day:'numeric'});
    const lw=Math.max(42,textWidthEstimate(label)+12);
    let row=anchorRows.findIndex(end=>ax-lw/2>end+6);
    if(row<0) row=anchorRows.indexOf(Math.min(...anchorRows));
    anchorRows[row]=ax+lw/2;
    const labelY=36+row*14;
    svg+=`<line class="anchor-line" x1="${ax.toFixed(1)}" y1="${m.t-6}" x2="${ax.toFixed(1)}" y2="${m.t+nL*laneH}"/>
      <text class="anchor-lbl" x="${ax.toFixed(1)}" y="${labelY}" text-anchor="middle">${label}</text>`;
  });
  const lanes=[], allLabels=[], allEvents=[];
  series.forEach((s,k)=>{
    const cy=m.t+k*laneH+laneH/2;
    const laneTop=m.t+k*laneH, laneBot=laneTop+laneH;
    const before=s.first_pos*(NP-1);
    const top=[],bot=[];
    for(let i=0;i<NP;i++){
      const gate = i<Math.floor(before)?0:(i===Math.floor(before)?(before%1):1);
      const th=half(s.timeline[i])*gate;
      top.push([xi(i),cy-th]); bot.push([xi(i),cy+th]);
    }
    const d=smoothPath(top)+' L'+bot.slice().reverse().map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' L')+' Z';
    lanes.push({key:s.key,label:s.label,d,color:s.color,cy,total:s.total,tops:s.tops,cid:s.cid,drill:s.drill,first_pos:s.first_pos});
    // left lane label
    const laneLabel=ellipsize(s.label,Math.floor((m.l-24)/6.6));
    allLabels.push(`<text x="${m.l-14}" y="${cy-2}" text-anchor="end" class="lane-name" fill="var(--cp-text)"><title>${esc(s.label)}</title>${esc(laneLabel)}</text>
      <text x="${m.l-14}" y="${cy+13}" text-anchor="end" class="lane-sub" fill="var(--cp-text-muted)">${s.total} mentions</text>`);
    // concept branch-tick labels (Minard-style event labels) at peaks
    if(!focusCat){
      const tops=(s.concepts||[]).slice().sort((a,b)=>b.salience-a.salience).slice(0,4)
        .map(c=>({c,pi:_peak(c.timeline)})).sort((a,b)=>a.pi-b.pi);
      tops.forEach((o,idx)=>{
        const px=xi(o.pi), up=idx%2===0?-1:1;
        const rawTy=cy+up*(half(o.c.timeline[o.pi])+13);
        const ty=up<0?Math.max(laneTop+17,rawTy):Math.min(laneBot-17,rawTy);
        allLabels.push(`<g class="tick" data-cid="${o.c.id}"><line x1="${px.toFixed(1)}" y1="${cy.toFixed(1)}" x2="${px.toFixed(1)}" y2="${ty.toFixed(1)}" class="tick-lead"/>
          <circle cx="${px.toFixed(1)}" cy="${cy.toFixed(1)}" r="2.4" fill="${s.color}"/>
          <text x="${px.toFixed(1)}" y="${(ty+(up<0?-2:9)).toFixed(1)}" text-anchor="middle" class="tick-lbl" fill="var(--cp-text-muted)">${esc(ellipsize(o.c.label,22))}</text></g>`);
      });
    }
    // events (emerging, tension)
    eventsFor(s.key).forEach(ev=>{
      const px=x(ev.pos);
      allEvents.push(`<g class="evt" data-type="${ev.type}" ${ev.node?`data-cid="${ev.node}"`:''} ${ev.con?`data-con="${ev.con}"`:''} data-lbl="${esc(ev.label)}">
        <circle cx="${px.toFixed(1)}" cy="${cy.toFixed(1)}" r="9" fill="var(--map-bg)" stroke="${ev.type==='Tension'?'var(--cp-danger)':'var(--cp-warning)'}" stroke-width="1.4"/>
        <text x="${px.toFixed(1)}" y="${(cy+3.5).toFixed(1)}" text-anchor="middle" style="font-size:11px">${ev.icon}</text></g>`);
    });
  });
  const laneBands=lanes.map(r=>`<path class="ribbon" d="${r.d}" fill="${r.color}" fill-opacity="0.82" stroke="var(--map-bg)" stroke-width="0.7" data-key="${esc(r.key)}"/>`).join('');
  // lower evidence-density band (Minard temperature analog)
  const byPos=new Array(NP).fill(0); series.forEach(s=>s.timeline.forEach((v,i)=>byPos[i]+=v));
  const bmax=Math.max(1,...byPos);
  const bTop=m.t+nL*laneH+bandGap, bBot=bTop+bandH;
  const bpts=byPos.map((v,i)=>[xi(i), bBot-(v/bmax)*(bandH-6)]);
  const bandPath=smoothPath(bpts)+` L${xi(NP-1).toFixed(1)},${bBot} L${xi(0).toFixed(1)},${bBot} Z`;
  let band=`<text x="${m.l-14}" y="${bTop+bandH/2}" text-anchor="end" class="lane-sub" fill="var(--cp-text-muted)">evidence density</text>
    <path d="${bandPath}" fill="var(--cp-text-soft)" opacity="0.18"/><path d="${smoothPath(bpts)}" fill="none" stroke="var(--cp-text-soft)" stroke-width="1.3" opacity="0.6"/>`;
  (DATA.metadata.date_anchors||[]).forEach(a=>{const ax=x(a.pos);band+=`<line x1="${ax.toFixed(1)}" y1="${bTop}" x2="${ax.toFixed(1)}" y2="${bBot}" class="anchor-line"/>`;});
  const legendItems=focusCat? series.map(s=>({key:s.key,label:s.label,color:s.color,total:s.total}))
                            : DATA.river.map(r=>({key:r.category,label:r.category,color:CATCOLOR[r.category],total:r.total}));
  const legend=legendItems.map(r=>`<div class="li ${(!focusCat&&hiddenCats.has(r.key))?'dim':''}" data-key="${esc(r.key)}"><span class="sw" style="background:${r.color}"></span>${esc(r.label)} <span style="opacity:.6">(${r.total})</span></div>`).join('');
  const head = focusCat
    ? `<h2 class="section"><span class="rel" id="backBtn" style="margin-right:8px">\u2190 all themes</span>Inside: ${esc(focusCat)}</h2>
       <p class="sub">Each concept in <b>${esc(focusCat)}</b> as its own lane across the notebook (reading order, left \u2192 right). Lane thickness = mentions; a lane branches in where the concept first appears. \u2728 marks where an idea emerges. Click a lane to trace it to source.</p>`
    : `<h2 class="section">Knowledge march</h2>
       <p class="sub">One lane per theme, flowing <b>left \u2192 right through your notebook</b> (reading order, with real \uD83D\uDCC5 dates marked on top). Lane thickness = evidence volume at that point (the <b>trend</b>); tick labels mark where key concepts peak; \u2728 = an idea emerging, \u26a1 = a tension (the <b>events</b>). The band below is overall evidence density. <b>Click a lane to drill into its concepts.</b></p>`;
  document.getElementById('view-flow').innerHTML=
    `${head}
     <div id="flowWrap"><svg width="${W}" height="${H}" id="flowSvg">
       <text x="${m.l}" y="18" class="axis-tick" fill="var(--cp-text-muted)" style="font-size:10px">\u25b6 start of notebook</text>
       <text x="${W-m.r}" y="18" text-anchor="end" class="axis-tick" fill="var(--cp-text-muted)" style="font-size:10px">most recent \u25b6</text>
       ${svg}${laneBands}${allLabels.join('')}${allEvents.join('')}${band}</svg></div>
     <div class="legend">${legend}</div>`;
  const back=document.getElementById('backBtn'); if(back) back.onclick=()=>{focusCat=null;renderFlow();};
  document.querySelectorAll('#view-flow .ribbon').forEach(el=>{
    const key=el.getAttribute('data-key');const r=lanes.find(x=>x.key===key);
    el.onmousemove=(e)=>showTip(`<b>${esc(r.label)}</b> \u00b7 ${r.total} mentions<br>${r.drill?'<span style="color:var(--cp-text-muted)">Top: </span>'+r.tops.join(', ')+'<br><i style="color:var(--cp-text-soft)">click to drill in</i>':'<i style="color:var(--cp-text-soft)">click to trace to source</i>'}`,e.clientX,e.clientY);
    el.onmouseleave=hideTip;
    el.onmouseenter=()=>document.querySelectorAll('#view-flow .ribbon').forEach(o=>o.classList.toggle('dim',o!==el));
    el.addEventListener('mouseleave',()=>document.querySelectorAll('#view-flow .ribbon').forEach(o=>o.classList.remove('dim')));
    el.onclick=()=>{ if(r.drill){focusCat=key;renderFlow();if(r.cid)inspectConcept(conceptById[r.cid]);} else if(r.cid){inspectConcept(conceptById[r.cid]);} };
  });
  document.querySelectorAll('#view-flow .tick').forEach(el=>{
    const cid=el.getAttribute('data-cid');
    el.style.cursor='pointer';
    el.onclick=()=>{const c=conceptById[cid];if(c)inspectConcept(c);};
  });
  document.querySelectorAll('#view-flow .evt').forEach(el=>{
    el.style.cursor='pointer';
    el.onmousemove=(e)=>showTip(`<b>${el.getAttribute('data-type')}</b><br>${esc(el.getAttribute('data-lbl'))}`,e.clientX,e.clientY);
    el.onmouseleave=hideTip;
    el.onclick=()=>{const con=el.getAttribute('data-con');if(con){const c=DATA.contradictions.find(x=>x.id===con);if(c)return inspectContradiction(c);}const cid=el.getAttribute('data-cid');if(cid&&conceptById[cid])inspectConcept(conceptById[cid]);};
  });
  document.querySelectorAll('#view-flow .legend .li').forEach(el=>{
    el.onclick=()=>{const k=el.getAttribute('data-key');
      if(focusCat){const c=conceptById[k];if(c)inspectConcept(c);}
      else{if(hiddenCats.has(k))hiddenCats.delete(k);else hiddenCats.add(k);renderFlow();}
    };
  });
}

/* ---------- INSIGHTS ---------- */
let insightFilter='All';
function renderInsights(){
  const types=['All',...Array.from(new Set(DATA.insights.map(i=>i.type)))];
  const bar=types.map(t=>`<button class="fpill ${t===insightFilter?'active':''}" data-f="${t}">${t}${t==='All'?' ('+DATA.insights.length+')':''}</button>`).join('');
  const list=DATA.insights.filter(i=>insightFilter==='All'||i.type===insightFilter);
  const cards=list.map((ins,idx)=>{
    const cat=ins.category;const color=cat?CATCOLOR[cat]:'var(--cp-accent)';
    const node=ins.node?conceptById[ins.node]:null;
    return `<div class="card" data-i="${idx}" style="border-left-color:${color}">
      <div class="ttl"><span class="ico">${ins.icon}</span><span>${esc(ins.title)}</span></div>
      <div class="tag">${ins.type}</div>
      <div class="det">${esc(ins.detail)}</div>
      ${node?sparkline(node.timeline,color,300,26):''}</div>`;}).join('');
  document.getElementById('view-insights').innerHTML=
    `<h2 class="section">Emergent insights</h2>
     <p class="sub">The push layer: themes rising through your notebook, ideas that emerge late, concepts that bridge domains, genuine tensions, and open questions \u2014 computed from ${DATA.metadata.counts.concepts} concepts. Click any card for full provenance.</p>
     <div class="filterbar">${bar}</div><div class="cards">${cards}</div>`;
  document.querySelectorAll('#view-insights .fpill').forEach(b=>b.onclick=()=>{insightFilter=b.getAttribute('data-f');renderInsights();});
  document.querySelectorAll('#view-insights .card').forEach(el=>el.onclick=()=>{
    const ins=list[+el.getAttribute('data-i')];
    if(ins.contradiction){const con=DATA.contradictions.find(c=>c.id===ins.contradiction);if(con)return inspectContradiction(con);}
    if(ins.node)openNode(ins.node);});
}

/* ---------- EXPLORER ---------- */
let expSort='salience';
function renderExplorer(q){
  q=(q||'').toLowerCase().trim();
  let items=DATA.concepts.map(c=>{
    const third=Math.floor(c.timeline.length/3);
    const mom=c.timeline.slice(-third).reduce((a,b)=>a+b,0)-c.timeline.slice(0,third).reduce((a,b)=>a+b,0);
    return {c,mom};
  });
  if(q)items=items.filter(o=>o.c.label.toLowerCase().includes(q)||(o.c.aliases||[]).some(a=>a.includes(q))||o.c.category.toLowerCase().includes(q));
  items.sort((a,b)=> expSort==='momentum'? b.mom-a.mom : b.c.salience-a.c.salience);
  items=items.slice(0,120);
  const rows=items.map(o=>{const c=o.c,color=CATCOLOR[c.category];
    return `<div class="row" data-cid="${c.id}"><span class="dot" style="background:${color}"></span>
      <span class="lab">${esc(c.label)}</span>${sparkline(c.timeline,color,90,22)}
      <span class="mom ${o.mom>0?'up':'down'}">${o.mom>0?'\u2197':'\u2192'}${o.mom>0?'+'+o.mom:''}</span>
      <span class="meta">${esc(c.category)} \u00b7 ${c.mention_count} mentions</span></div>`;}).join('');
  document.getElementById('view-explorer').innerHTML=
    `<h2 class="section">Concept explorer</h2>
     <p class="sub">${DATA.metadata.counts.concepts} resolved concepts (aliases merged). Sorted by <button class="fpill ${expSort==='salience'?'active':''}" data-s="salience">salience</button> <button class="fpill ${expSort==='momentum'?'active':''}" data-s="momentum">momentum</button>. Each sparkline shows where the idea lives across the notebook.</p>
     ${rows||'<p class="sub">No matches.</p>'}`;
  document.querySelectorAll('#view-explorer [data-s]').forEach(b=>b.onclick=()=>{expSort=b.getAttribute('data-s');renderExplorer(document.getElementById('q').value);});
  document.querySelectorAll('#view-explorer .row').forEach(el=>el.onclick=()=>inspectConcept(conceptById[el.getAttribute('data-cid')]));
}

/* ---------- SOURCES ---------- */
function renderSources(){
  const rows=DATA.sources.map(s=>{
    const chs=DATA.chunks.filter(c=>c.source_id===s.id);
    const dated=chs.filter(c=>c.date_exact);
    const concepts=DATA.concepts.filter(c=>c.provenance.some(p=>p.source_id===s.id)).length;
    const claims=DATA.claims.filter(c=>c.provenance.some(p=>p.source_id===s.id)).length;
    return `<div class="card" style="cursor:default;border-left-color:var(--cp-accent)">
      <div class="ttl"><span>${esc(s.title)}</span></div>
      <div class="det mono" style="font-size:11px">${esc(s.path)}</div>
      <div class="kv"><span>Chunks<br><b>${chs.length}</b></span><span>Dated<br><b>${dated.length}</b></span>
        <span>Concepts<br><b>${concepts}</b></span><span>Claims<br><b>${claims}</b></span></div></div>`;}).join('');
  const cnt=DATA.metadata.counts;
  document.getElementById('view-sources').innerHTML=
    `<h2 class="section">Sources &amp; provenance backbone</h2>
     <p class="sub">Every concept, claim and insight resolves to one of these sources. Nothing is asserted without a traceable chunk. The flow axis is real reading order; ${DATA.metadata.anchor_dates} explicit calendar dates are pinned as anchors.</p>
     <div class="cards">${rows}</div>
     <div class="mini-label">Corpus</div>
     <div class="det" style="font-size:12.5px;color:var(--cp-text-muted)">${cnt.chunks} chunks \u00b7 ${cnt.concepts} concepts \u00b7 ${cnt.claims} claims \u00b7 ${cnt.typed_relations||cnt.relations} typed relations \u00b7 ${cnt.evolves} evolution links \u00b7 ${cnt.contradictions} tensions \u00b7 ${cnt.insights} insights. Claim status: ${Object.entries(DATA.metadata.status_counts).map(([k,v])=>k+' '+v).join(' \u00b7 ')}.</div>`;
}

/* ---------- nav + search ---------- */
function setView(v){
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.getAttribute('data-view')===v));
  document.querySelectorAll('.view').forEach(el=>el.classList.toggle('active',el.id==='view-'+v));
  if(v==='flow')renderFlow();
}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>setView(t.getAttribute('data-view')));
document.getElementById('q').addEventListener('input',e=>{setView('explorer');renderExplorer(e.target.value);});
window.addEventListener('resize',()=>{if(document.getElementById('view-flow').classList.contains('active'))renderFlow();});
renderFlow();renderInsights();renderExplorer('');renderSources();
document.getElementById('noteClose').onclick=closeNote;
document.getElementById('noteModal').onclick=e=>{if(e.target.id==='noteModal')closeNote();};
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeNote();});
</script>
</body>
</html>'''

# Decode the \\uXXXX escapes in the TEMPLATE only (data JSON must stay untouched).
HTML = HTML.encode('utf-8').decode('unicode_escape')
# recombine surrogate pairs (e.g. emoji written as \\uD83D\\uDCC5) into astral chars
HTML = HTML.encode('utf-16','surrogatepass').decode('utf-16')
HTML = HTML.replace('__DATA__', data)
OUT.write_text(HTML, encoding='utf-8')
print('wrote', OUT, OUT.stat().st_size, 'bytes')
