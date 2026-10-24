"""Build demo.html from out/step_04_results.json. Run step_04_with_action.py first. Run (from src/): python3 _build_demo.py"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_results.json"), encoding="utf-8") as fh:
    data = json.load(fh)
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Intake Tier Action: 160 synthetic issues</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--bad:#b3261e;--warn:#8a5a00;--ok:#1e6b3a;--sel:#eef3fb}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--bad:#ff8a80;--warn:#ffc266;--ok:#7fd49a;--sel:#1d2733}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:18px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:640px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top;white-space:nowrap}
tbody tr{cursor:pointer}tbody tr.on{background:var(--sel)}
.TIERED{color:var(--ok);font-weight:600}.NEEDS_INFO{color:var(--warn);font-weight:600}.off{color:var(--bad);font-weight:600}
.wrap{overflow-x:auto}pre{white-space:pre-wrap;word-break:break-word;border:1px solid var(--line);border-radius:8px;padding:10px;margin:0;font-size:13px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media (max-width:700px){.two{grid-template-columns:1fr}}
</style></head><body><main>
<h1>Intake Tier Action: 160 synthetic issues</h1>
<p class="s">Each row is an intake issue as an issue form would render it. The reference tier is the rubric applied to the true attributes I planted; the tool tier is what the command printed. Click a row to see the body and the comment.</p>
<div class="k" id="k"></div>
<div><label>Decision <select id="d"><option value="">all</option><option>TIERED</option><option>NEEDS_INFO</option></select></label>
<label>Tool tier <select id="t"><option value="">any</option><option value="differs">differs from the reference</option><option value="same">equals the reference</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Issue</th><th>Body</th><th>Declared</th><th>Step 2</th><th>Tool</th><th>Reference</th><th>Decision</th><th>Labels</th></tr></thead><tbody id="b"></tbody></table></div>
<h2 id="h">Pick a row</h2>
<div class="two"><div><p class="s">Issue body</p><pre id="body"></pre></div><div><p class="s">Comment the Action would post</p><pre id="cmt"></pre></div></div>
<p class="s">Known misses: tiers differ from the reference where the form and the catalog both understate a data class, where a vendor is left off the form and the registry is silent, and where a customer-facing answer is unsure. Source: <code>python3 step_04_with_action.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
var k=document.getElementById('k');
[[SUM.tiered+' of '+SUM.issues,'tiered'],[SUM.needs_info+' of '+SUM.issues,'sent to needs-info'],[SUM.correct+' of '+SUM.issues,'tier equals reference (step 2: '+SUM.step2_correct+')'],[SUM.high_found+' of '+SUM.high_tier,'tier 3-4 found']].forEach(function(x){var d=document.createElement('div');var b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function show(r,tr){document.getElementById('h').textContent='Issue '+r.issue+': '+r.title;document.getElementById('body').textContent=r.body;document.getElementById('cmt').textContent=r.comment;
Array.prototype.forEach.call(document.querySelectorAll('tbody tr'),function(x){x.className='';});tr.className='on';}
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,b=document.getElementById('b');while(b.firstChild){b.removeChild(b.firstChild);}var c=0;
ROWS.forEach(function(r){var diff=r.tier!==null&&r.tier!==r.reference;if((d&&r.decision!==d)||(t==='differs'&&!diff)||(t==='same'&&(r.tier===null||diff)))return;c++;var tr=document.createElement('tr');tr.tabIndex=0;
[r.issue,r.kind,r.declared===null?'':r.declared,r.step2_tier,r.tier===null?'':r.tier,r.reference,r.decision,r.labels.join(', ')].forEach(function(v,i){var td=document.createElement('td');td.textContent=v;if(i===6)td.className=v;if(i===4&&diff)td.className='off';tr.appendChild(td);});
tr.onclick=function(){show(r,tr);};tr.onkeydown=function(e){if(e.key==='Enter'){show(r,tr);}};b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('d').onchange=draw;document.getElementById('t').onchange=draw;draw();
</script></body></html>
"""
page = page.replace("__ROWS__", json.dumps(data["rows"]).replace("<", "\\u003c")).replace("__SUM__", json.dumps(data["summary"]))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
