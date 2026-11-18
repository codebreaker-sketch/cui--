"""Writes out/index.html: a self-contained dashboard (no server, no internet needed).
Tabs: Plan | Inbox (every message + status) | Rejected | Trace | Runs (tokens, areas)."""
import html
import json

TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hackathon Planner</title>
<style>
:root{--bg:#f6f7fb;--card:#fff;--ink:#14162b;--mut:#646a86;--line:#e3e6f0;--acc:#3b5bfd;--ok:#12a150;--bad:#d93848;--warn:#c98a00;--chip:#eef1ff}
@media (prefers-color-scheme:dark){:root{--bg:#0f1120;--card:#181b30;--ink:#e9ebf8;--mut:#9aa0c0;--line:#2a2e4a;--acc:#7d93ff;--ok:#3fd17f;--bad:#ff6b7a;--warn:#ffc24a;--chip:#232848}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
header{padding:18px 20px 0;max-width:1200px;margin:auto}h1{margin:0;font-size:22px}
.sub{color:var(--mut)}.wrap{max-width:1200px;margin:auto;padding:12px 20px 40px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}.kpi b{display:block;font-size:20px}
.kpi span{color:var(--mut);font-size:12px}
nav{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 14px}nav button{border:1px solid var(--line);background:var(--card);color:var(--ink);
padding:8px 14px;border-radius:999px;cursor:pointer;font-weight:600}nav button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.card h3{margin:0 0 8px;font-size:15px;display:flex;justify-content:space-between;align-items:center}
table{width:100%;border-collapse:collapse}td,th{padding:6px 4px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
td.r{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.chip{display:inline-block;font-size:11px;padding:2px 8px;border-radius:999px;background:var(--chip);color:var(--acc);font-weight:600;margin:1px}
.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}
.st-accepted{background:color-mix(in srgb,var(--ok) 15%,transparent);color:var(--ok)}
.st-rejected,.st-partly{background:color-mix(in srgb,var(--bad) 15%,transparent);color:var(--bad)}
.st-ignored{background:var(--chip);color:var(--mut)}
.bar{height:10px;background:var(--chip);border-radius:6px;overflow:hidden;margin:8px 0}.bar i{display:block;height:100%;background:var(--acc)}
.tl{position:relative;margin-top:6px}.slot{display:flex;gap:10px;padding:6px 0;border-bottom:1px dashed var(--line)}
.slot .t{width:150px;color:var(--mut);font-variant-numeric:tabular-nums}.k-break,.k-meal{color:var(--warn)}.k-judging{color:var(--acc)}
pre{white-space:pre-wrap;word-break:break-word;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:8px;max-height:320px;overflow:auto;font-size:12px}
details{border:1px solid var(--line);border-radius:10px;padding:8px 12px;margin:8px 0;background:var(--card)}summary{cursor:pointer;font-weight:600}
.msg{border-left:4px solid var(--line);padding:8px 12px;margin:8px 0;background:var(--card);border-radius:8px}
.msg.rejected,.msg.partly{border-left-color:var(--bad)}.msg.accepted{border-left-color:var(--ok)}
.codeev{color:var(--mut);font-family:ui-monospace,Consolas,monospace;font-size:12px;padding:2px 0}
.rej{border:1px solid var(--bad);border-radius:12px;padding:12px;margin:10px 0;background:color-mix(in srgb,var(--bad) 7%,var(--card))}
.hide{display:none}
</style></head><body>
<header style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap"><h1>Hackathon Planner <span class="sub" style="font-size:14px">· reads the messages, plans the event, explains every decision</span></h1>
<button id="lang" title="Language / Zubaan" style="border:1px solid var(--line);background:var(--card);color:var(--ink);padding:7px 14px;border-radius:999px;cursor:pointer;font-weight:600">Roman Urdu</button></header>
<div class="wrap">
<div class="kpis" id="kpis"></div>
<nav id="nav"></nav>
<section id="t-plan"></section><section id="t-inbox" class="hide"></section><section id="t-rej" class="hide"></section>
<section id="t-trace" class="hide"></section><section id="t-runs" class="hide"></section><section id="t-new" class="hide"></section>
</div>
<script>
const S = __DATA__;
let LANG='en';try{LANG=localStorage.getItem('lang')||'en'}catch(e){}
const UR={
 'reads the messages, plans the event, explains every decision':'messages parhta hai, event plan karta hai, har faisla samjhata hai',
 'Hackathon Planner':'Hackathon Planner','Runs & tokens':'Runs aur tokens','+ New message':'+ Naya message','Inbox':'Inbox',
 'Rejected':'Rad shuda','Trace':'Trace','Plan':'Plan','checks pass':'checks pass','people to seat & feed':'logon ko bithana aur khilana',
 'left in budget':'budget mein baqi','messages rejected':'messages rad kiye','tokens, all runs':'tokens, tamam runs','INVALID':'GHALAT','VALID':'DURUST',
 'Constraints & decisions in force':'Laagu shartein aur faislay','Other constraints noted':'Doosri shartein (note ki gayi)',
 'Checks':'Checks','Venue':'Jagah (Venue)','Food':'Khana','Judging':'Judging','Schedule':'Schedule','Budget':'Budget',
 'Correct figures':'Figures durust','Within budget':'Budget ke andar','Venue fits':'Jagah kaafi hai','Schedule valid':'Schedule durust',
 'Enough judges':'Judges kaafi hain','All areas covered':'Tamam areas shamil','PASS':'THEEK','FAIL':'NAKAAM',
 'seats for':'seats, logon ke liye:','people':'log','full':'bhara hua','Why not the others':'Baqi kyun nahi','No valid venue':'Koi durust jagah nahi',
 'per head':'fi kas','alternative':'mutabadil','students':'students','judges':'judges','staff':'staff','teams each':'teams har judge',
 'judging block':'judging block','confirmed':'confirmed','on standby':'standby par','cover for late/absent judges':'late/ghair hazir judges ki jagah',
 'Total':'Kul','Left':'Baqi','Declined':'Mana kiya','out of date':'purana (out of date)','replaced by':'ki jagah aya',
 'Message #':'Message #','rejected · rule':'rad kiya gaya · rule','Why:':'Wajah:',
 'The plan was kept valid; nothing from this message was applied.':'Plan durust rakha gaya; is message ki koi cheez laagu nahi ki gayi.',
 'No messages rejected yet.':'Abhi tak koi message rad nahi hua.','facts extracted':'nikaale gaye facts',
 'accepted':'qabool','partly rejected':'jazvi rad','rejected':'rad','ignored':'nazar andaz','not read':'parha nahi gaya',
 'model call(s)':'model call(s)','Raw printed trace':'Asal printed trace','Input':'Input','Output':'Output',
 'Run':'Run','Model calls':'Model calls','Areas that called a model':'Jin areas ne model call kiya','Predicted (before run)':'Pesh-goi (run se pehle)',
 'Areas re-planned (code)':'Dobara plan hue areas (code)','Tokens':'Tokens','Time':'Waqt','none':'koi nahi',
 'Only the reading step uses a model. Venue, schedule, food, judging and budget are pure code, so a new message costs one small model call and re-plans only the areas whose numbers changed.':
 'Sirf reading step model use karta hai. Venue, schedule, khana, judging aur budget sirf code hain, is liye naya message sirf aik chhoti model call leta hai aur sirf wohi areas dobara plan hote hain jin ke numbers badle.',
 'Submit a new message':'Naya message bhejein',
 "Goes through the same pipeline as":'Wohi pipeline jo',
 "one 'reading' model call per message, then code re-plans and validates. A message that would break the plan is rejected and the plan is kept.":
 "har message par aik 'reading' model call, phir code plan aur validation karta hai. Jo message plan tor de woh rad hota hai aur plan wesa hi rehta hai.",
 'Run update':'Update chalayein','Upload a .txt file':'.txt file upload karein',
 'A whole pack starts a fresh plan; a file with new message(s) is an update. Drag the file here or':'Poora pack naya plan banata hai; naye message(s) wali file update hai. File yahan drag karein ya',
 'Files:':'Files:','running (max 120 s)...':'chal raha hai (zyada se zyada 120 s)...','done · reload dashboard':'mukammal · dashboard reload karein',
 'e.g. Finance here. The printing bill came in at Rs 15,000, not Rs 10,000.':'maslan: Finance here. Printing ka bill Rs 15,000 aya, Rs 10,000 nahi.',
 'Opening & briefing':'Aaghaz aur briefing','Build session':'Build session','Lunch':'Lunch','Closing & prizes':'Ikhtitaam aur inamaat',
 'Judging (teams at tables, judges rotate)':'Judging (teams tables par, judges ghoomtay hain)','min':'min',
 'Already spent':'Pehle se kharch','Judge honorarium':'Judges ka honorarium','Approved request':'Manzoor shuda request',
 'Contingency reserve':'Hangami reserve','lacks required':'mein zaroori cheez nahi:','not available':'dastiyab nahi','needed':'chahiye',
 'only a wish from':'sirf aik khwahish:','nobody with budget authority approved it, so it is not paid for':'budget ke ikhtiyar wale kisi ne manzoor nahi kiya, is liye paisa nahi diya gaya',
 'does not fit in the budget with essentials first':'zaroori cheezon ke baad budget mein gunjaish nahi',
 'Language / Zubaan':'Zubaan / Language'
};
const UR_PAIRS=Object.entries(UR).sort((a,b)=>b[0].length-a[0].length);
const T=s=>LANG==='ur'&&UR[s]?UR[s]:s;
const RULES=LANG==='ur'?{
 'R-COVER':'R-COVER: kisi ki di hui tadaad (khana, seats, judges) plan ki zaroorat se kam hai.',
 'R-AUTH':'R-AUTH: bhejne wale ko yeh setting badalne ka ikhtiyar nahi.',
 'R-STALE':'R-STALE: yeh message us fact se purana hai jise badalna chahta hai.',
 'R-VALID':'R-VALID: isay maanne se 6 checks mein se koi nakaam ho jata.'}:{
 'R-COVER':'R-COVER: a promised quantity (food, seats, judges) is below what the plan needs.',
 'R-AUTH':'R-AUTH: the sender has no authority over this setting.',
 'R-STALE':'R-STALE: the message is older than the fact it tries to replace.',
 'R-VALID':'R-VALID: accepting it would make one of the 6 checks fail.'};
const P = S.plan, fmt = n => n==null?'-':'Rs '+Number(n).toLocaleString('en-PK');
const esc = s => String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const src = id => id?`<span class="chip">msg #${id}</span>`:'';
const served=location.protocol.startsWith('http');
const tabs=[['plan','Plan'],['inbox','Inbox ('+S.messages.length+')'],['rej','Rejected ('+S.rejected.length+')'],['trace','Trace'],['runs','Runs & tokens']].concat(served?[['new','+ New message']]:[]);
let cur=(location.hash||'#plan').slice(1);
function show(t){cur=t;location.hash=t;tabs.forEach(([k])=>{document.getElementById('t-'+k).classList.toggle('hide',k!==t)});
 document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('on',b.dataset.t===t))}
document.getElementById('nav').innerHTML=tabs.map(([k,l])=>`<button data-t="${k}" onclick="show('${k}')">${l}</button>`).join('');
const b=P.budget, pct=b.limit?Math.min(100,Math.round(b.total/b.limit*100)):0;
const okN=P.checks.filter(c=>c.ok).length;
document.getElementById('kpis').innerHTML=[
 [P.valid?'<span class="ok">VALID</span>':'<span class="bad">INVALID</span>', okN+'/'+P.checks.length+' checks pass'],
 [P.people,'people to seat & feed'],[fmt(b.total),'of '+fmt(b.limit)+' ('+pct+'%)'],[fmt(b.left),'left in budget'],
 [S.rejected.length,'messages rejected'],[S.tokens_total.toLocaleString(),'tokens, all runs']
].map(([v,l])=>`<div class="kpi"><b>${v}</b><span>${l}</span></div>`).join('');

// ---------- PLAN
const v=P.venue,f=P.food,j=P.judging,s=P.schedule,hc=P.headcount;
document.getElementById('t-plan').innerHTML=`<div class="grid">
<div class="card"><h3>Checks <span class="${P.valid?'ok':'bad'}">${okN}/${P.checks.length}</span></h3><table>${P.checks.map(c=>`<tr><td>${c.ok?'<b class="ok">PASS</b>':'<b class="bad">FAIL</b>'}</td><td><b>${esc(c.check)}</b><br><span class="sub">${esc(c.why)}</span></td></tr>`).join('')}</table></div>
<div class="card"><h3>Venue ${v?src(v.src):''}</h3>${v?`<div style="font-size:20px;font-weight:700">${esc(v.name)}</div>
<div class="sub">${v.cap} seats for ${P.people} people · ${fmt(v.cost)} ${(v.feat||[]).map(x=>`<span class="chip">${esc(x)}</span>`).join('')}</div>
<div class="bar"><i style="width:${Math.min(100,P.people/v.cap*100)}%"></i></div><div class="sub">${Math.round(P.people/v.cap*100)}% full</div>`:'<b class="bad">No valid venue</b>'}
${P.venue_rejected.length?`<details><summary>Why not the others (${P.venue_rejected.length})</summary>${P.venue_rejected.map(r=>`<div class="sub">✗ ${esc(r)}</div>`).join('')}</details>`:''}</div>
<div class="card"><h3>Food ${f?src(f.src):''}</h3>${f?`<div style="font-size:20px;font-weight:700">${f.boxes} × ${esc(f.name)}</div>
<div class="sub">${esc(f.tier)} @ ${fmt(f.pph)} per head = <b>${fmt(f.cost)}</b></div>
<div class="sub">${hc.students} students + ${j.judges_used} judges + ${hc.staff} staff${hc.extra?' + '+hc.extra+' extra':''}</div>
${f.alternatives.map(a=>`<div class="sub">alternative: ${esc(a.tier)} @ ${fmt(a.pph)} = ${fmt(a.cost)}</div>`).join('')}`:'<b class="bad">No food option</b>'}</div>
<div class="card"><h3>Judging</h3><div style="font-size:20px;font-weight:700">${j.judges_used} judges · ${j.teams} teams</div>
<div class="sub">${j.teams_per_judge} teams each × ${j.min_per_team} min = ${j.block_min}-min judging block (max ${j.max_teams_per_judge}/judge)</div>
<div class="sub">${j.judges_confirmed} confirmed → ${j.reserve_judges} on standby (cover for late/absent judges)</div></div>
<div class="card" style="grid-column:1/-1"><h3>Schedule <span class="sub">${s.start} – ${s.end} · ${s.duration_min} min</span></h3><div class="tl">
${s.slots.map(x=>`<div class="slot"><div class="t">${x.start} – ${x.end}</div><div class="k-${x.kind}"><b>${esc(x.what)}</b> <span class="sub">${x.min} min</span></div></div>`).join('')}</div></div>
<div class="card" style="grid-column:1/-1"><h3>Budget <span class="sub">${fmt(b.total)} of ${fmt(b.limit)}</span></h3>
<div class="bar"><i style="width:${pct}%;background:${pct>100?'var(--bad)':'var(--acc)'}"></i></div>
<table>${b.lines.map(l=>`<tr><td>${esc(l.item)} ${src(l.src)}</td><td class="r">${fmt(l.amt)}</td></tr>`).join('')}
<tr><td><b>Total</b></td><td class="r"><b>${fmt(b.total)}</b></td></tr><tr><td class="sub">Left</td><td class="r ok">${fmt(b.left)}</td></tr></table>
${b.declined.map(d=>`<div class="warn">Declined: ${esc(d.item)} ${fmt(d.amt)} — ${esc(d.why)} ${src(d.src)}</div>`).join('')}</div>
<div class="card" style="grid-column:1/-1"><h3>Constraints &amp; decisions in force</h3>
<table>${Object.entries(S.world.set).map(([k,x])=>`<tr><td>${esc(k.replace(/_/g,' '))}</td><td class="r"><b>${esc(typeof x.v==='number'?x.v.toLocaleString():x.v)}</b></td><td>${src(x.msg)} <span class="sub">${esc(x.from||'')}</span></td></tr>`).join('')}
${(P.needs||[]).map(n=>`<tr><td>${esc(n.area)} rule: ${esc(n.kind)}</td><td class="r"><b>${esc(n.what||'')}${n.v!=null?' '+n.v:''}</b></td><td>${src(n.msg)}</td></tr>`).join('')}
${(S.world.superseded||[]).map(x=>`<tr><td class="sub" colspan="3">out of date: ${esc(x.what)} from msg #${x.msg} replaced by msg #${x.by}</td></tr>`).join('')}</table></div>
${P.notes.length?`<div class="card" style="grid-column:1/-1"><h3>Other constraints noted</h3>${P.notes.map(n=>`<div><span class="chip">${esc(n.area)}</span> ${esc(n.text)} ${src(n.msg)}</div>`).join('')}</div>`:''}
</div>`;

// ---------- INBOX
document.getElementById('t-inbox').innerHTML=S.messages.map(m=>{const st=(m.status||'').split(' ')[0];
 return `<div class="msg ${st}"><div><b>#${m.id}</b> ${esc(m.from)} <span class="sub">${esc(m.role)} · ${esc(m.date||'')}</span>
 <span class="chip st-${st}">${esc(m.status||'')}</span> ${(m.areas||[]).map(a=>`<span class="chip">${a}</span>`).join('')}</div>
 <div style="margin:4px 0">${esc(m.text)}</div>${m.reason?`<div class="sub">→ ${esc(m.reason)}</div>`:''}
 <details><summary class="sub">facts extracted (${m.f.length})</summary><pre>${esc(JSON.stringify(m.f,null,1))}</pre></details></div>`}).join('');

// ---------- REJECTED
document.getElementById('t-rej').innerHTML=S.rejected.length?S.rejected.map(r=>`<div class="rej"><b class="bad">Message #${r.msg} rejected · rule ${esc(r.rule)}</b>
<div style="margin:6px 0">“${esc(r.text)}”</div><div><b>Why:</b> ${esc(r.reason)}</div><div class="sub">${esc(RULES[r.rule]||'')}</div><div class="sub">The plan was kept valid; nothing from this message was applied.</div></div>`).join('')
 :'<div class="card">No messages rejected yet.</div>';

// ---------- TRACE
document.getElementById('t-trace').innerHTML=S.runs.map((r,i)=>`<div class="card" style="margin-bottom:12px"><h3>${esc(r.label)} <span class="sub">${r.calls} model call(s) · ${r.tokens.total} tokens · ${r.secs}s</span></h3>
${r.events.map(e=>e.kind==='call'?`<details ${i===S.runs.length-1?'open':''}><summary>MODEL CALL #${e.no} · ${esc(e.model)} · area=<span class="chip">${e.area}</span> · tokens in ${e.usage.prompt} / out ${e.usage.completion} / total ${e.usage.total}</summary>
<div class="sub">Input</div><pre>${esc(e.input)}</pre><div class="sub">Output</div><pre>${esc(e.output)}</pre></details>`
 : e.kind==='reject'?`<div class="codeev bad">REJECTED #${e.msg} [${esc(e.rule)}] ${esc(e.reason)}</div>`
 :`<div class="codeev">[code · ${e.area}] ${esc(e.msg)}</div>`).join('')}</div>`).join('')
 +`<details><summary>Raw printed trace</summary><pre style="max-height:600px">${esc(S.trace_lines.join('\n'))}</pre></details>`;

// ---------- RUNS
document.getElementById('t-runs').innerHTML=`<div class="card"><table><tr><th>Run</th><th>Model calls</th><th>Areas that called a model</th><th>Predicted (before run)</th><th>Areas re-planned (code)</th><th class="r">Tokens</th><th class="r">Time</th></tr>
${S.runs.map(r=>`<tr><td>${esc(r.label)}</td><td>${r.calls}</td><td>${r.model_areas.map(a=>`<span class="chip">${a}</span>`).join('')}</td>
<td>${(r.areas_predicted||[]).map(a=>`<span class="chip">${a}</span>`).join('')||'<span class="sub">-</span>'}</td><td>${(r.areas_replanned||[]).map(a=>`<span class="chip">${a}</span>`).join('')||'<span class="sub">none</span>'}</td><td class="r">${r.tokens.total}</td><td class="r">${r.secs}s</td></tr>`).join('')}
<tr><td><b>Total</b></td><td>${S.runs.reduce((a,r)=>a+r.calls,0)}</td><td></td><td></td><td></td><td class="r"><b>${S.tokens_total}</b></td><td></td></tr></table>
<p class="sub">Only the reading step uses a model. Venue, schedule, food, judging and budget are pure code, so a new message costs one small model call and re-plans only the areas whose numbers changed.</p></div>`;
document.getElementById('t-new').innerHTML=`<div class="card"><h3>Submit a new message</h3>
<p class="sub">Goes through the same pipeline as <code>python main.py</code>: one 'reading' model call per message, then code re-plans and validates. A message that would break the plan is rejected and the plan is kept.</p>
<textarea id="nm" rows="6" style="width:100%;font:inherit;padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink)" placeholder="e.g. Finance here. The printing bill came in at Rs 15,000, not Rs 10,000."></textarea>
<p><button id="nb" style="padding:8px 16px;border-radius:999px;border:0;background:var(--acc);color:#fff;font-weight:600;cursor:pointer">Run update</button> <span id="ns" class="sub"></span></p>
<div id="drop" style="border:2px dashed var(--line);border-radius:12px;padding:18px;text-align:center;margin:10px 0">
<b>Upload a .txt file</b><br><span class="sub">A whole pack starts a fresh plan; a file with new message(s) is an update. Drag the file here or</span>
<input type="file" id="nf" accept=".txt,text/plain"></div><pre id="no" class="hide"></pre>
<p class="sub">Files: <a href="/out/final_plan.json">final_plan.json</a> · <a href="/out/execution_trace.json">execution_trace.json</a> · <a href="/out/rejected_messages.json">rejected_messages.json</a> · <a href="/out/final_report.txt">final_report.txt</a></p></div>`;
async function send(url,payload){const nb=document.getElementById('nb');nb.disabled=true;
 document.getElementById('ns').textContent=T('running (max 120 s)...');
 const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json()).catch(e=>({output:String(e)}));
 const o=document.getElementById('no');o.classList.remove('hide');o.textContent=r.output||r.error;
 document.getElementById('ns').innerHTML='<a href="#plan" onclick="setTimeout(()=>location.reload(),50)">'+T('done · reload dashboard')+'</a>';nb.disabled=false}
const nb=document.getElementById('nb');if(nb)nb.onclick=()=>{const t=document.getElementById('nm').value.trim();if(t)send('/api/message',{text:t})};
function upload(f){if(!f)return;f.text().then(t=>send('/api/upload',{name:f.name,text:t}))}
const nf=document.getElementById('nf');if(nf)nf.onchange=()=>upload(nf.files[0]);
const dz=document.getElementById('drop');if(dz){dz.ondragover=e=>{e.preventDefault();dz.style.borderColor='var(--acc)'};
 dz.ondragleave=()=>dz.style.borderColor='var(--line)';dz.ondrop=e=>{e.preventDefault();upload(e.dataTransfer.files[0])}}
show(tabs.some(t=>t[0]===cur)?cur:'plan');
// ---------- LANGUAGE: English / Roman Urdu (interface text only; trace lines stay exactly as printed)
function translate(root){if(LANG!=='ur')return;const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:n=>n.parentElement.closest('pre,textarea,code')?2:1});
 const nodes=[];while(w.nextNode())nodes.push(w.currentNode);
 for(const n of nodes){let s=n.nodeValue;for(const [en,ur] of UR_PAIRS){if(s.includes(en))s=s.split(en).join(ur)}n.nodeValue=s}
 document.querySelectorAll('[placeholder]').forEach(e=>e.placeholder=T(e.placeholder))}
document.getElementById('lang').textContent=LANG==='ur'?'English':'Roman Urdu';
document.getElementById('lang').onclick=()=>{try{localStorage.setItem('lang',LANG==='ur'?'en':'ur')}catch(e){}location.reload()};
translate(document.body);
if(!served)setTimeout(()=>location.reload(),8000);
</script></body></html>"""


def write(st, path):
    data = json.dumps(st, ensure_ascii=False).replace("</", "<\\/")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(TEMPLATE.replace("__DATA__", data))
