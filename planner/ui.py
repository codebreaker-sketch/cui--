"""Writes out/index.html: a self-contained dashboard built ONLY from the saved state (real plan, real trace).
Sections: plan rows for the 5 areas, schedule bar, ticket (status, cost, calls, tokens), budget bar, six checks,
tabs for Trace / Rejected / Message pack / Runs & tokens / Constraints, and (when served by server.py)
a box to type or upload new messages. English / Roman Urdu switch."""
import json

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Hackathon Planner</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap">
<style>
:root{color-scheme:dark;--glass:rgba(22,22,28,.72);--line:rgba(255,255,255,.09);--txt:#f4f4f7;--mut:#9a9aa8;--pur:#7c3aed;--pur2:#a78bfa;--ok:#34d399;--warn:#fbbf24;--bad:#f87171;--r:18px;--card:rgba(22,22,28,.85)}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:#050507;color:var(--txt);font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;font-size:14px;min-height:100vh;overflow-x:hidden}
.bg{position:fixed;inset:0;z-index:0;pointer-events:none;background:radial-gradient(55% 45% at 88% 15%,rgba(124,58,237,.6),transparent 70%),radial-gradient(50% 40% at 5% 100%,rgba(91,33,182,.55),transparent 70%),repeating-linear-gradient(118deg,rgba(167,139,250,.2) 0 1px,transparent 1px 9px);animation:drift 14s ease-in-out infinite alternate}
@keyframes drift{to{background-position:0 0,30px -20px,60px 0}}
.wrap{position:relative;z-index:1;max-width:1120px;margin:0 auto;padding:16px}
header{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.logo{font-weight:800;font-size:18px;letter-spacing:-.3px}.logo i{font-style:normal;color:var(--pur2)}
.pill{background:rgba(255,255,255,.07);border:1px solid var(--line);color:var(--txt);border-radius:10px;padding:8px 14px;font:inherit;font-size:13px;cursor:pointer;transition:background .2s;text-decoration:none}
.pill:hover{background:rgba(255,255,255,.14)}
.shell{background:var(--glass);border:1px solid var(--line);border-radius:28px;padding:18px;backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);box-shadow:0 30px 80px rgba(0,0,0,.5)}
.main{display:grid;grid-template-columns:1.05fr 1fr;gap:18px}
@media(max-width:820px){.main{grid-template-columns:1fr}}
h1{font-size:34px;line-height:1.1;margin:6px 0 12px;letter-spacing:-.8px;font-weight:700}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}
.chip{background:rgba(255,255,255,.07);border:1px solid var(--line);border-radius:999px;padding:5px 11px;font-size:12px;color:var(--mut)}
.chip b{color:var(--txt);font-weight:600}
.box{background:rgba(255,255,255,.05);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.row{display:flex;align-items:center;gap:12px;padding:12px 14px;border-bottom:1px solid var(--line);animation:down .4s both}
.row:last-child{border-bottom:0}
.row .ic{width:34px;height:34px;border-radius:10px;background:rgba(124,58,237,.2);display:grid;place-items:center;font-size:16px;flex:none}
.row .nm{font-weight:600}.row .vl{color:var(--mut);font-size:13px;margin-top:2px}.row .body{flex:1;min-width:0}
.dot{width:10px;height:10px;border-radius:50%;background:#555;flex:none}
.dot.ok{background:var(--ok);box-shadow:0 0 0 4px rgba(52,211,153,.18)}.dot.bad{background:var(--bad);animation:pulse 1s infinite}
@keyframes pulse{50%{box-shadow:0 0 0 6px rgba(248,113,113,.25)}}
.label{font-size:12px;color:var(--mut);margin:14px 0 6px}
.tl{display:flex;gap:3px;height:34px}
.tl div{border-radius:8px;font-size:10px;display:grid;place-items:center;overflow:hidden;white-space:nowrap;color:#0a0a0f;font-weight:600;transform-origin:left;animation:grow .5s both}
@keyframes grow{from{transform:scaleX(0);opacity:0}}
.tlkey{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:11px;color:var(--mut);margin-top:6px}
.stage{background:#000;border-radius:var(--r);padding:22px;border:1px solid var(--line)}
.ticket{aspect-ratio:16/10;min-height:190px;border-radius:16px;padding:18px 22px;color:#0a0a0f;position:relative;display:flex;flex-direction:column;justify-content:space-between;
background:linear-gradient(115deg,#9fd8ff,#c9a7ff,#ffb3e6,#ffe08a,#9dffc8,#9fd8ff);background-size:300% 300%;animation:holo 9s linear infinite;
-webkit-mask:radial-gradient(circle 13px at 0 50%,#0000 98%,#000) left/51% 100% no-repeat,radial-gradient(circle 13px at 100% 50%,#0000 98%,#000) right/51% 100% no-repeat;
mask:radial-gradient(circle 13px at 0 50%,#0000 98%,#000) left/51% 100% no-repeat,radial-gradient(circle 13px at 100% 50%,#0000 98%,#000) right/51% 100% no-repeat}
.ticket.badt{background:linear-gradient(115deg,#ffb4b4,#ffd6a5,#ffb4b4);background-size:300% 300%}
@keyframes holo{to{background-position:300% 0}}
.ticket small{font-weight:700;letter-spacing:.12em;font-size:10px}
.ticket h2{margin:4px 0 0;font-size:30px;line-height:1;font-weight:800;letter-spacing:-.5px;text-transform:uppercase}
.tstats{display:flex;gap:14px;align-items:flex-end;justify-content:space-between;flex-wrap:wrap}
.tstats div span{display:block;font-size:10px;font-weight:700;letter-spacing:.08em;opacity:.7}
.tstats div b{font-size:17px;font-variant-numeric:tabular-nums}
.bars{height:26px;width:70px;background:repeating-linear-gradient(90deg,#0a0a0f 0 2px,transparent 2px 4px,#0a0a0f 4px 5px,transparent 5px 8px)}
.seg{display:flex;height:14px;border-radius:8px;overflow:hidden;gap:2px;background:rgba(255,255,255,.06)}
.seg i{display:block;animation:grow .8s both}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:8px;font-size:12px;color:var(--mut)}
.legend s{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;text-decoration:none}
.checks{display:grid;grid-template-columns:1fr 1fr;gap:6px 14px;font-size:13px}
.checks div{display:flex;gap:8px;align-items:center;color:var(--mut)}
.checks div.on{color:var(--txt)}.checks div.on::before{content:"✓";color:var(--ok);font-weight:700}.checks div.off{color:var(--bad)}.checks div.off::before{content:"✗";font-weight:700}
.alert{margin-top:12px;padding:11px 14px;border-radius:12px;background:rgba(248,113,113,.14);border:1px solid rgba(248,113,113,.4);font-size:13px;animation:down .35s,shake .4s .35s}
@keyframes down{from{opacity:0;transform:translateY(-8px)}}
@keyframes shake{25%{transform:translateX(-4px)}75%{transform:translateX(4px)}}
.bottom{margin-top:18px}
.tabs{display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap}
.tab{background:transparent;border:1px solid var(--line);color:var(--mut);padding:8px 14px;border-radius:999px;font:inherit;cursor:pointer}
.tab.on{background:#fff;color:#0a0a0f;font-weight:600;border-color:#fff}
.panel{display:none}.panel.on{display:block}
.call{padding:12px 14px;border-bottom:1px solid var(--line);animation:down .35s both}.call:last-child{border-bottom:0}
.call .top{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.num{background:var(--pur);border-radius:8px;padding:2px 8px;font-weight:700;font-size:12px}
.tag{background:rgba(167,139,250,.2);color:var(--pur2);border-radius:6px;padding:2px 8px;font-size:12px}
.tag.code{background:rgba(255,255,255,.08);color:var(--mut)}.tag.rej{background:rgba(248,113,113,.18);color:var(--bad)}
.tok{margin-left:auto;color:var(--mut);font-size:12px;font-variant-numeric:tabular-nums}
.runh{padding:12px 14px;background:rgba(124,58,237,.12);font-weight:700;display:flex;gap:10px;flex-wrap:wrap;justify-content:space-between}
.codeev{font:12px/1.5 ui-monospace,Menlo,Consolas,monospace;color:var(--mut);padding:3px 14px}
.codeev.bad{color:#ffb4b4}
details{margin-top:6px;color:var(--mut)}summary{cursor:pointer;font-size:12px}
pre{white-space:pre-wrap;word-break:break-word;margin:6px 0 0;font:12px/1.5 ui-monospace,Menlo,Consolas,monospace;color:#d7d7e0;background:rgba(0,0,0,.35);padding:10px;border-radius:10px;max-height:340px;overflow:auto}
.total{padding:14px;font-weight:700;display:flex;justify-content:space-between;background:rgba(124,58,237,.18)}
.total span{font-variant-numeric:tabular-nums}
.msg{padding:12px 14px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:flex-start;animation:down .35s both}
.msg:last-child{border-bottom:0}.msg .meta{font-size:12px;color:var(--mut)}
.stamp{margin-left:auto;flex:none;font-size:11px;font-weight:700;border:2px solid;border-radius:6px;padding:2px 8px;transform:rotate(-4deg);text-transform:uppercase;letter-spacing:.05em}
.stamp.used{color:var(--ok)}.stamp.stale{color:var(--warn)}.stamp.rej{color:var(--bad)}.stamp.irr{color:var(--mut)}
.reason{font-size:12px;color:#ffb4b4;margin-top:3px}.why2{font-size:12px;color:var(--mut);margin-top:3px}
table{width:100%;border-collapse:collapse}td,th{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:13px}
th{color:var(--mut);font-weight:600}td.r,th.r{text-align:right;font-variant-numeric:tabular-nums}
.compose{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap}
.compose textarea{flex:1;min-width:220px;min-height:46px;resize:vertical;background:rgba(255,255,255,.06);border:1px dashed rgba(255,255,255,.25);border-radius:12px;color:var(--txt);padding:10px 12px;font:inherit;transition:border-color .2s,transform .2s}
.compose textarea:focus{outline:0;border-color:var(--pur2);transform:scale(1.005)}
.drop{margin-top:10px;border:1px dashed rgba(255,255,255,.25);border-radius:12px;padding:12px;text-align:center;color:var(--mut);font-size:13px;transition:border-color .2s,background .2s}
.drop.over{border-color:var(--pur2);background:rgba(167,139,250,.1)}
.slip{font-size:12px;color:var(--mut);margin-top:8px}
.ex{font-size:12px;color:var(--pur2);cursor:pointer;text-decoration:underline;margin-right:10px;background:none;border:0;font-family:inherit;padding:0}
.note{font-size:11px;color:var(--mut);text-align:center;margin-top:14px}
.hide{display:none!important}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head>
<body><div class="bg"></div>
<div class="wrap">
<header><div class="logo">Event<i>Planner</i> · Islamabad</div>
<div style="display:flex;gap:8px;flex-wrap:wrap"><button class="pill" id="lang">Roman Urdu</button><button class="pill" id="copy">Copy plan + trace</button></div></header>
<div class="shell">
 <div class="main">
  <section>
   <h1>Hackathon plan</h1>
   <div class="chips" id="chips"></div>
   <div class="box" id="rows"></div>
   <div class="label">Schedule</div>
   <div class="tl" id="tl"></div><div class="tlkey" id="tlkey"></div>
   <div id="alert"></div>
  </section>
  <section>
   <div class="stage"><div class="ticket" id="ticket">
     <div><small id="tk-sub"></small><h2 id="tk-title"></h2></div>
     <div class="tstats"><div><span>TOTAL COST</span><b id="tk-cost">0</b></div><div><span>MODEL CALLS</span><b id="tk-calls">0</b></div>
     <div><span>TOKENS</span><b id="tk-tok">0</b></div><div class="bars"></div></div></div></div>
   <div class="label">Budget</div><div class="seg" id="seg"></div><div class="legend" id="legend"></div>
   <div class="label">Six checks</div><div class="checks" id="checks"></div>
  </section>
 </div>
 <div class="bottom">
  <div class="tabs" id="tabs"></div>
  <div class="panel box" id="p-trace"></div>
  <div class="panel box" id="p-rej"></div>
  <div class="panel box" id="p-inbox"></div>
  <div class="panel box" id="p-runs"></div>
  <div class="panel box" id="p-cons"></div>
  <div id="composer" class="hide">
   <div class="compose"><textarea id="newmsg" placeholder="Paste a new message here (email, WhatsApp, notice)…"></textarea>
   <button class="pill" id="send" style="min-width:110px">Update plan</button></div>
   <div class="drop" id="drop">Drop a .txt file here, or <input type="file" id="nf" accept=".txt,text/plain"> · a whole pack starts a fresh plan; new message(s) update it</div>
   <div style="margin-top:8px"><span class="slip">Examples:</span> <button class="ex" data-t="Finance here. The printing bill came in at Rs 15,000, not Rs 10,000.">a change</button><button class="ex" data-t="Caterer: I have rounded your order down to 100 boxes to keep the cost low.">a wrong message</button></div>
   <pre id="out" class="hide"></pre>
  </div>
  <div class="slip" id="slip"></div>
 </div>
</div>
<p class="note" id="foot">Everything on this page comes from the saved plan and trace (out/final_plan.json, out/execution_trace.json).</p>
</div>
<script>
const S=__DATA__;
let LANG='en';try{LANG=localStorage.getItem('lang')||'en'}catch(e){}
const UR={
 'Hackathon plan':'Hackathon ka plan','Schedule':'Schedule','Budget':'Budget','Six checks':'Chhe checks','TOTAL COST':'KUL KHARCHA','MODEL CALLS':'MODEL CALLS','TOKENS':'TOKENS',
 'ALL SIX CHECKS PASSED':'CHHE KE CHHE CHECKS PASS','SOME CHECKS FAIL':'KUCH CHECKS FAIL','The plan is valid':'Plan durust hai','The plan needs work':'Plan mein masla hai',
 'Copy plan + trace':'Plan + trace copy karein','Copied':'Copy ho gaya','Trace':'Trace','Rejected messages':'Rad kiye gaye messages','Message pack':'Messages',
 'Runs & tokens':'Runs aur tokens','Constraints':'Shartein','Students':'Students','Teams':'Teams','Staff':'Staff','Judges':'Judges','Extra':'Extra','To feed':'Khana kitnon ka','Length':'Dauraniya',
 'Venue':'Jagah (Venue)','Food':'Khana','Judging':'Judging','Total tokens':'Kul tokens','no model call':'model call nahi','REJECTED':'RAD',
 'Used':'Istemal hua','Out of date':'Purana','Rejected':'Rad','Not relevant':'Ghair mutaliq','Partly rejected':'Jazvi rad','Not read':'Parha nahi gaya',
 'Correct figures':'Figures durust','Within budget':'Budget ke andar','Venue fits':'Jagah kaafi hai','Schedule valid':'Schedule durust','Enough judges':'Judges kaafi hain','All areas covered':'Tamam areas shamil',
 'Update plan':'Plan update karein','Examples:':'Misaalein:','a change':'aik tabdeeli','a wrong message':'aik ghalat message',
 'Paste a new message here (email, WhatsApp, notice)…':'Naya message yahan paste karein (email, WhatsApp, notice)…',
 'Drop a .txt file here, or':'.txt file yahan drop karein, ya','a whole pack starts a fresh plan; new message(s) update it':'poora pack naya plan banata hai; naye messages plan update karte hain',
 'Nothing rejected.':'Kuch rad nahi hua.','Why:':'Wajah:','The plan was kept valid; nothing from this message was applied.':'Plan durust rakha gaya; is message ki koi cheez laagu nahi hui.',
 'Run':'Run','Areas that called a model':'Jin areas ne model call kiya','Predicted (before run)':'Pesh-goi (run se pehle)','Areas re-planned (code)':'Dobara plan hue areas (code)','Tokens':'Tokens','Time':'Waqt','Total':'Kul',
 'Setting':'Setting','Value':'Qeemat','From':'Kis ne','out of date':'purana','replaced by':'ki jagah aya',
 'Latest rejection':'Aakhri rad shuda message','Prediction for the last update':'Pichhle update ki pesh-goi','Actual':'Asal',
 'Everything on this page comes from the saved plan and trace (out/final_plan.json, out/execution_trace.json).':'Is page par sab kuch save shuda plan aur trace se aata hai (out/final_plan.json, out/execution_trace.json).',
 'running (max 120 s)…':'chal raha hai (zyada se zyada 120 s)…','done, reloading…':'mukammal, reload ho raha hai…','left':'baqi','of':'mein se',
 'Already spent':'Pehle se kharch','Judge honorarium':'Judges ka honorarium','Approved request':'Manzoor shuda request','Contingency reserve':'Hangami reserve',
 'Opening & briefing':'Aaghaz aur briefing','Build session':'Build session','Lunch':'Lunch','Closing & prizes':'Ikhtitaam aur inamaat','Judging (teams at tables, judges rotate)':'Judging',
 'only a wish from':'sirf aik khwahish:','nobody with budget authority approved it, so it is not paid for':'budget ke ikhtiyar wale kisi ne manzoor nahi kiya, is liye paisa nahi diya gaya',
 'Declined':'Mana kiya','none':'koi nahi','min':'min','log out':'log out'
};
const UR_PAIRS=Object.entries(UR).sort((a,b)=>b[0].length-a[0].length);
const T=s=>LANG==='ur'&&UR[s]?UR[s]:s;
const RULES=LANG==='ur'?{'R-COVER':'R-COVER: kisi ki di hui tadaad (khana, seats, judges) plan ki zaroorat se kam hai.','R-AUTH':'R-AUTH: bhejne wale ko yeh setting badalne ka ikhtiyar nahi.',
 'R-STALE':'R-STALE: yeh message us fact se purana hai jise badalna chahta hai.','R-VALID':'R-VALID: isay maanne se 6 checks mein se koi nakaam ho jata.','R-CONFLICT':'R-CONFLICT: yeh message pehle se maujood fact se takrata hai.'}
 :{'R-COVER':'R-COVER: a promised quantity (food, seats, judges) is below what the plan needs.','R-AUTH':'R-AUTH: the sender has no authority over this setting.',
 'R-STALE':'R-STALE: the message is older than the fact it tries to replace.','R-VALID':'R-VALID: accepting it would make one of the 6 checks fail.','R-CONFLICT':'R-CONFLICT: the message contradicts an established fact.'};
const $=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const rs=n=>n==null?'–':'Rs '+Math.round(n).toLocaleString('en-US');
const P=S.plan,b=P.budget,hc=P.headcount,j=P.judging,s=P.schedule,v=P.venue,f=P.food;
const COLORS=['#a78bfa','#f472b6','#fbbf24','#34d399','#60a5fa','#f87171','#fb923c','#22d3ee','#c084fc'];
const served=location.protocol.startsWith('http');
const check=n=>P.checks.find(c=>c.check===n)||{ok:false,why:''};

// chips
$('#chips').innerHTML=[['Students',hc.students],['Teams',hc.teams],['Judges',j.judges_used],['Staff',hc.staff]].concat(hc.extra?[['Extra',hc.extra]]:[])
 .concat([['To feed',P.people],['Length',(s.duration_min/60)+' h']]).map(c=>`<span class="chip">${c[0]} <b>${esc(c[1])}</b></span>`).join('');
// five area rows
const AREAS=[['venue','🏛️','Venue',v?`${v.name} · seats ${v.cap} for ${P.people} · ${rs(v.cost)}`:'No valid venue','Venue fits'],
 ['schedule','🕒','Schedule',`${s.start} – ${s.end} · ${s.slots.length} blocks · ${s.duration_min} min`,'Schedule valid'],
 ['food','🍱','Food',f?`${f.boxes} × ${f.name} @ ${rs(f.pph)} = ${rs(f.cost)}`:'No food option','Correct figures'],
 ['judging','⚖️','Judging',`${j.judges_used} judges needed of ${j.judges_confirmed??'?'} confirmed · ${j.teams_per_judge} teams each × ${j.min_per_team} min`,'Enough judges'],
 ['budget','💰','Budget',`${rs(b.total)} of ${rs(b.limit)} · ${rs(b.left)} left`,'Within budget']];
$('#rows').innerHTML=AREAS.map((a,i)=>`<div class="row" style="animation-delay:${i*60}ms"><div class="ic">${a[1]}</div><div class="body"><div class="nm">${a[2]}</div><div class="vl">${esc(a[3])}</div></div><span class="dot ${check(a[4]).ok?'ok':'bad'}" title="${esc(check(a[4]).why)}"></span></div>`).join('');
// schedule bar
$('#tl').innerHTML=s.slots.map((x,i)=>`<div style="flex:${x.min};background:${COLORS[i%COLORS.length]};animation-delay:${i*70}ms" title="${esc(x.start+' – '+x.end+' · '+x.what+' · '+x.min+' min')}">${x.min>=30?esc(x.what.split(' (')[0]):''}</div>`).join('');
$('#tlkey').innerHTML=s.slots.map((x,i)=>`<span><b style="color:${COLORS[i%COLORS.length]}">●</b> ${esc(x.start)} ${esc(x.what.split(' (')[0])} (${x.min} min)</span>`).join('');
// latest rejection alert
const lastRej=S.rejected[S.rejected.length-1];
if(lastRej)$('#alert').innerHTML=`<div class="alert"><b>Latest rejection</b> · msg #${lastRej.msg} [${esc(lastRej.rule)}]<br>${esc(lastRej.reason)}</div>`;
// ticket
const calls=S.runs.reduce((a,r)=>a+r.calls,0);
$('#ticket').classList.toggle('badt',!P.valid);
$('#tk-sub').textContent=P.valid?'ALL SIX CHECKS PASSED':'SOME CHECKS FAIL';
$('#tk-title').innerHTML=P.valid?'The plan<br>is valid':'The plan<br>needs work';
// budget bar
const lim=b.limit||b.total||1;
$('#seg').innerHTML=b.lines.map((l,i)=>`<i style="width:${l.amt/lim*100}%;background:${COLORS[i%COLORS.length]};animation-delay:${i*60}ms" title="${esc(l.item)}: ${rs(l.amt)}"></i>`).join('');
$('#legend').innerHTML=b.lines.map((l,i)=>`<span><s style="background:${COLORS[i%COLORS.length]}"></s>${esc(l.item)} ${rs(l.amt)}</span>`).join('')
 +b.declined.map(d=>`<span style="color:var(--warn)">Declined: ${esc(d.item)} ${rs(d.amt)} — ${esc(d.why)}</span>`).join('');
// checks
$('#checks').innerHTML=P.checks.map(c=>`<div class="${c.ok?'on':'off'}" title="${esc(c.why)}">${esc(c.check)}</div>`).join('');

// tabs
const TABS=[['trace','Trace'],['rej','Rejected messages'],['inbox','Message pack'],['runs','Runs & tokens'],['cons','Constraints']];
let cur=(location.hash||'#trace').slice(1);if(!TABS.some(t=>t[0]===cur))cur='trace';
$('#tabs').innerHTML=TABS.map(([k,l])=>`<button class="tab" data-p="${k}">${l}${k==='rej'?` <span>(${S.rejected.length})</span>`:k==='inbox'?` <span>(${S.messages.length})</span>`:''}</button>`).join('');
function show(t){cur=t;history.replaceState(null,'','#'+t);document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x.dataset.p===t));
 document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('on',p.id==='p-'+t))}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>show(t.dataset.p));

// TRACE: exactly the recorded events (real model calls + code decisions + rejections)
$('#p-trace').innerHTML=S.runs.map((r,ri)=>`<div class="runh"><span>${esc(r.label)}</span><span class="tok">${r.calls} model call(s) · ${r.tokens.total} tokens · ${r.secs}s</span></div>`+
 r.events.map(e=>e.kind==='call'?`<div class="call"><div class="top"><span class="num">#${e.no}</span><b>${esc(e.model)}</b><span class="tag">${esc(e.area)}</span><span class="tok">in ${e.usage.prompt} · out ${e.usage.completion} · ${e.usage.total} tokens · ${e.secs}s</span></div>
  <details><summary>Input and output</summary><pre>INPUT:\n${esc(e.input)}\n\nOUTPUT:\n${esc(e.output)}</pre></details></div>`
 :e.kind==='reject'?`<div class="codeev bad"><span class="tag rej">REJECTED</span> #${e.msg} [${esc(e.rule)}] ${esc(e.reason)}</div>`
 :`<div class="codeev"><span class="tag code">no model call</span> ${esc(e.area)} · ${esc(e.msg)}</div>`).join('')).join('')
 +`<details style="padding:0 14px 10px"><summary>Raw printed trace</summary><pre>${esc(S.trace_lines.join('\n'))}</pre></details>`
 +`<div class="total"><div>Total tokens</div><span>${S.tokens_total.toLocaleString('en-US')}</span></div>`;

// REJECTED
$('#p-rej').innerHTML=S.rejected.length?S.rejected.slice().reverse().map(r=>`<div class="msg"><div><b>Message #${r.msg}</b> <span class="meta">· [${esc(r.rule)}]</span>
 <div class="meta">“${esc(r.text)}”</div><div class="reason">Why: ${esc(r.reason)}</div>
 ${String(r.rule).split('+').map(x=>`<div class="why2">${esc(RULES[x]||'')}</div>`).join('')}<div class="why2">The plan was kept valid; nothing from this message was applied.</div></div><span class="stamp rej">Rejected</span></div>`).join('')
 :`<div class="msg">Nothing rejected.</div>`;

// MESSAGE PACK with stamps
const staleIds=new Set((S.world.superseded||[]).map(x=>x.msg));
const stamp=m=>{const st=(m.status||'');if(st==='rejected')return['rej','Rejected'];if(st.startsWith('partly'))return['rej','Partly rejected'];
 if(st==='ignored')return['irr','Not relevant'];if(st==='not read')return['irr','Not read'];if(staleIds.has(m.id))return['stale','Out of date'];return['used','Used']};
$('#p-inbox').innerHTML=S.messages.map(m=>{const [k,l]=stamp(m);return `<div class="msg"><div><b>${m.id}. ${esc(m.from)}</b> <span class="meta">· ${esc(m.role)}${m.date?' · '+esc(m.date):''} ${(m.areas||[]).map(a=>`<span class="tag">${a}</span>`).join(' ')}</span>
 <div class="meta">${esc(m.text)}</div>${m.reason?`<div class="reason">${esc(m.reason)}</div>`:''}
 <details><summary>facts extracted (${m.f.length})</summary><pre>${esc(JSON.stringify(m.f,null,1))}</pre></details></div><span class="stamp ${k}">${l}</span></div>`}).join('');

// RUNS
$('#p-runs').innerHTML=`<table><tr><th>Run</th><th>Model calls</th><th>Areas that called a model</th><th>Predicted (before run)</th><th>Areas re-planned (code)</th><th class="r">Tokens</th><th class="r">Time</th></tr>
${S.runs.map(r=>`<tr><td>${esc(r.label)}</td><td>${r.calls}</td><td>${r.model_areas.map(a=>`<span class="tag">${a}</span>`).join(' ')}</td>
<td>${(r.areas_predicted||[]).map(a=>`<span class="tag">${a}</span>`).join(' ')||'–'}</td><td>${(r.areas_replanned||[]).map(a=>`<span class="tag">${a}</span>`).join(' ')||'none'}</td>
<td class="r">${r.tokens.total}</td><td class="r">${r.secs}s</td></tr>`).join('')}
<tr><td><b>Total</b></td><td>${calls}</td><td></td><td></td><td></td><td class="r"><b>${S.tokens_total}</b></td><td></td></tr></table>`;

// CONSTRAINTS
$('#p-cons').innerHTML=`<table><tr><th>Setting</th><th class="r">Value</th><th>From</th></tr>
${Object.entries(S.world.set).map(([k,x])=>`<tr><td>${esc(k.replace(/_/g,' '))}</td><td class="r"><b>${esc(typeof x.v==='number'?x.v.toLocaleString('en-US'):x.v)}</b></td><td>msg #${x.msg} · ${esc(x.from||'')}</td></tr>`).join('')}
${(P.needs||[]).map(n=>`<tr><td>${esc(n.area)} rule: ${esc(n.kind)}</td><td class="r"><b>${esc(n.what||'')}${n.v!=null?' '+n.v:''}</b></td><td>msg #${n.msg}</td></tr>`).join('')}
${(P.notes||[]).map(n=>`<tr><td>note (${esc(n.area)})</td><td colspan="2">${esc(n.text)} · msg #${n.msg}</td></tr>`).join('')}
${(S.world.superseded||[]).map(x=>`<tr><td colspan="3" style="color:var(--mut)">out of date: ${esc(x.what)} from msg #${x.msg} replaced by msg #${x.by}</td></tr>`).join('')}</table>`;

// prediction slip for the last update
const lastRun=S.runs[S.runs.length-1];
if(S.runs.length>1)$('#slip').innerHTML=`Prediction for the last update: model calls in <b>${lastRun.model_areas.join(', ')}</b> (${lastRun.calls} call) · Actual: <b>${lastRun.calls?lastRun.model_areas.join(', '):'none'}</b> ✓ · areas re-planned by code: ${(lastRun.areas_replanned||[]).join(', ')||'none'}`;

// composer (only when served by server.py)
if(served){$('#composer').classList.remove('hide');
 async function sendTo(url,payload){const o=$('#out');o.classList.remove('hide');o.textContent=T('running (max 120 s)…');$('#send').disabled=true;
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json()).catch(e=>({output:String(e)}));
  o.textContent=(r.output||r.error||'')+'\n'+T('done, reloading…');$('#send').disabled=false;setTimeout(()=>location.reload(),1200)}
 $('#send').onclick=()=>{const t=$('#newmsg').value.trim();if(t)sendTo('/api/message',{text:t})};
 const up=file=>{if(file)file.text().then(t=>sendTo('/api/upload',{name:file.name,text:t}))};
 $('#nf').onchange=()=>up($('#nf').files[0]);
 const dz=$('#drop');dz.ondragover=e=>{e.preventDefault();dz.classList.add('over')};dz.ondragleave=()=>dz.classList.remove('over');
 dz.ondrop=e=>{e.preventDefault();dz.classList.remove('over');up(e.dataTransfer.files[0])};
 document.querySelectorAll('.ex').forEach(x=>x.onclick=()=>{$('#newmsg').value=x.dataset.t;$('#newmsg').focus()});
}
// copy
$('#copy').onclick=async()=>{const txt=JSON.stringify({plan:P,rejected:S.rejected,runs:S.runs.map(r=>({label:r.label,calls:r.calls,tokens:r.tokens})),total_tokens:S.tokens_total},null,2);
 try{await navigator.clipboard.writeText(txt);$('#copy').textContent=T('Copied')+' ✓'}catch(e){$('#copy').textContent='Copy blocked'}setTimeout(()=>$('#copy').textContent=T('Copy plan + trace'),1800)};
show(cur);
// language
function translate(root){if(LANG!=='ur')return;const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:n=>n.parentElement.closest('pre,textarea,code,script,style')?2:1});
 const nodes=[];while(w.nextNode())nodes.push(w.currentNode);
 for(const n of nodes){let t=n.nodeValue;for(const [en,ur] of UR_PAIRS){if(t.includes(en))t=t.split(en).join(ur)}n.nodeValue=t}
 document.querySelectorAll('[placeholder]').forEach(e=>e.placeholder=T(e.placeholder))}
$('#lang').textContent=LANG==='ur'?'English':'Roman Urdu';
$('#lang').onclick=()=>{try{localStorage.setItem('lang',LANG==='ur'?'en':'ur')}catch(e){}location.reload()};
translate(document.body);
// count-up numbers on the ticket
function count(el,to,fmt){const t0=performance.now();(function f(t){const k=Math.min(1,(t-t0)/900),e=1-Math.pow(1-k,3);el.textContent=fmt(Math.round(to*e));if(k<1)requestAnimationFrame(f)})(t0)}
count($('#tk-cost'),b.total,rs);count($('#tk-calls'),calls,n=>n);count($('#tk-tok'),S.tokens_total,n=>n.toLocaleString('en-US'));
if(!served)setTimeout(()=>location.reload(),15000);
</script></body></html>"""


def write(st, path):
    data = json.dumps(st, ensure_ascii=False).replace("</", "<\\/")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(TEMPLATE.replace("__DATA__", data))
