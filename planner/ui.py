"""Writes out/index.html: a self-contained dashboard (no server, no internet needed).
Tabs: Plan | Inbox (every message + status) | Rejected | Trace | Runs (tokens, areas)."""
import html
import json

TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="6">
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
<header><h1>Hackathon Planner <span class="sub" style="font-size:14px">· reads the messages, plans the event, explains every decision</span></h1></header>
<div class="wrap">
<div class="kpis" id="kpis"></div>
<nav id="nav"></nav>
<section id="t-plan"></section><section id="t-inbox" class="hide"></section><section id="t-rej" class="hide"></section>
<section id="t-trace" class="hide"></section><section id="t-runs" class="hide"></section>
</div>
<script>
const S = __DATA__;
const P = S.plan, fmt = n => n==null?'-':'Rs '+Number(n).toLocaleString('en-PK');
const esc = s => String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const src = id => id?`<span class="chip">msg #${id}</span>`:'';
const tabs=[['plan','Plan'],['inbox','Inbox ('+S.messages.length+')'],['rej','Rejected ('+S.rejected.length+')'],['trace','Trace'],['runs','Runs & tokens']];
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
<div style="margin:6px 0">“${esc(r.text)}”</div><div><b>Why:</b> ${esc(r.reason)}</div><div class="sub">The plan was kept valid; nothing from this message was applied.</div></div>`).join('')
 :'<div class="card">No messages rejected yet.</div>';

// ---------- TRACE
document.getElementById('t-trace').innerHTML=S.runs.map((r,i)=>`<div class="card" style="margin-bottom:12px"><h3>${esc(r.label)} <span class="sub">${r.calls} model call(s) · ${r.tokens.total} tokens · ${r.secs}s</span></h3>
${r.events.map(e=>e.kind==='call'?`<details ${i===S.runs.length-1?'open':''}><summary>MODEL CALL #${e.no} · ${esc(e.model)} · area=<span class="chip">${e.area}</span> · tokens in ${e.usage.prompt} / out ${e.usage.completion} / total ${e.usage.total}</summary>
<div class="sub">Input</div><pre>${esc(e.input)}</pre><div class="sub">Output</div><pre>${esc(e.output)}</pre></details>`
 : e.kind==='reject'?`<div class="codeev bad">REJECTED #${e.msg} [${esc(e.rule)}] ${esc(e.reason)}</div>`
 :`<div class="codeev">[code · ${e.area}] ${esc(e.msg)}</div>`).join('')}</div>`).join('')
 +`<details><summary>Raw printed trace</summary><pre style="max-height:600px">${esc(S.trace_lines.join('\n'))}</pre></details>`;

// ---------- RUNS
document.getElementById('t-runs').innerHTML=`<div class="card"><table><tr><th>Run</th><th>Model calls</th><th>Areas that called a model</th><th>Areas re-planned (code)</th><th class="r">Tokens</th><th class="r">Time</th></tr>
${S.runs.map(r=>`<tr><td>${esc(r.label)}</td><td>${r.calls}</td><td>${r.model_areas.map(a=>`<span class="chip">${a}</span>`).join('')}</td>
<td>${(r.areas_replanned||[]).map(a=>`<span class="chip">${a}</span>`).join('')||'<span class="sub">none</span>'}</td><td class="r">${r.tokens.total}</td><td class="r">${r.secs}s</td></tr>`).join('')}
<tr><td><b>Total</b></td><td>${S.runs.reduce((a,r)=>a+r.calls,0)}</td><td></td><td></td><td class="r"><b>${S.tokens_total}</b></td><td></td></tr></table>
<p class="sub">Only the reading step uses a model. Venue, schedule, food, judging and budget are pure code, so a new message costs one small model call and re-plans only the areas whose numbers changed.</p></div>`;
show(tabs.some(t=>t[0]===cur)?cur:'plan');
</script></body></html>"""


def write(st, path):
    data = json.dumps(st, ensure_ascii=False).replace("</", "<\\/")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(TEMPLATE.replace("__DATA__", data))
