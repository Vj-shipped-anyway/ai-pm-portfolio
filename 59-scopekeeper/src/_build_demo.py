"""Build demo.html from out/step_04_*. Run step_04_with_diff.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    with open(os.path.join(HERE, "out", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


grants, agents = read("step_04_grants.csv"), read("step_04_agents.csv")
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)


def embed(obj):
    return json.dumps(obj).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ScopeKeeper CLI: every grant against every call</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--remove:#b3261e;--narrow:#8a5a00;--keep:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--remove:#ff8a80;--narrow:#ffc266;--keep:#7fd49a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:28px 0 8px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:150px;flex:1 1 150px}.k b{font-size:20px;display:block}
.k span{color:var(--mut);font-size:13px}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.remove{color:var(--remove);font-weight:600}.narrow{color:var(--narrow);font-weight:600}.keep{color:var(--keep);font-weight:600}
.wrap{overflow-x:auto}table.g{min-width:760px}td.n{white-space:nowrap}
</style></head><body><main>
<h1>ScopeKeeper CLI: every grant against every call</h1>
<p class="s">Synthetic data. Each row is one grant held by one agent. The diff column is what <code>scopekeeper diff</code> proposes after reading 90 days of calls; the truth column is what the data generator planted. The same author wrote both, so the numbers are a ceiling.</p>
<div class="k" id="k"></div>
<div><label>Diff <select id="a"><option value="">all</option><option>remove</option><option>narrow</option><option>keep</option></select></label>
<label>Truth <select id="t"><option value="">all</option><option value="yes">needed</option><option value="no">not needed</option></select></label>
<label>Agent <select id="g"><option value="">all</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table class="g"><thead><tr><th>Agent</th><th>Scope</th><th>Diff</th><th>Annual review</th><th>Needed</th><th>Planted basis</th><th>Tagged calls</th><th>Credited calls</th><th>Reason</th></tr></thead><tbody id="b"></tbody></table></div>
<h2>Breadth by agent</h2>
<p class="s">Breadth is the share of an agent's entitlements that no call touched.</p>
<div class="wrap"><table><thead><tr><th>Agent</th><th>Grants</th><th>Reach</th><th>After</th><th>Cut</th><th>Breadth</th></tr></thead><tbody id="ag"></tbody></table></div>
<p class="s">Known limits: the quarterly grants shown as remove with truth needed, the unneeded grants kept on a sibling's untagged calls, and the two unneeded grants a smoke test touched. Source: <code>python3 step_04_with_diff.py</code>.</p>
</main>
<script>
var GRANTS=__GRANTS__, AGENTS=__AGENTS__, SUM=__SUM__;
function card(big,small){var d=document.createElement('div'),b=document.createElement('b'),s=document.createElement('span');b.textContent=big;s.textContent=small;d.appendChild(b);d.appendChild(s);document.getElementById('k').appendChild(d);}
card(SUM.unneeded_removed+' of '+SUM.unneeded,'unneeded grants removed (annual review: '+SUM.review_unneeded_removed+')');
card(SUM.reach_cut+' of '+SUM.reach_before,'entitlements cut');
card(SUM.newly_denied+' of '+SUM.calls,'calls newly denied in replay');
card(SUM.next_quarter_denied,'legitimate calls denied next quarter (known limit)');
var sel=document.getElementById('g');
AGENTS.map(function(r){return r.agent_id;}).sort().forEach(function(v){var o=document.createElement('option');o.textContent=v;o.value=v;sel.appendChild(o);});
function cell(tr,v,cls){var td=document.createElement('td');td.textContent=v;if(cls)td.className=cls;tr.appendChild(td);}
function draw(){var a=document.getElementById('a').value,t=document.getElementById('t').value,g=sel.value,b=document.getElementById('b');
b.textContent='';var c=0;
GRANTS.forEach(function(r){if((a&&r.action!==a)||(t&&r.needed!==t)||(g&&r.agent_id!==g))return;c++;var tr=document.createElement('tr');
cell(tr,r.agent_id,'n');cell(tr,r.scope,'');cell(tr,r.action,r.action);cell(tr,r.review,'');cell(tr,r.needed==='yes'?'needed':'not needed','');cell(tr,r.basis,'');cell(tr,r.calls_tagged,'n');cell(tr,r.calls_credited,'n');
cell(tr,r.reason+(r.after?'; keep '+r.after.split(';').join(', '):''),'');b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
['a','t','g'].forEach(function(id){document.getElementById(id).onchange=draw;});draw();
var ag=document.getElementById('ag');
AGENTS.forEach(function(r){var tr=document.createElement('tr');[r.agent_id,r.grants,r.reach,r.proposed,r.cut,r.breadth_pct+'%'].forEach(function(v){cell(tr,v,'n');});ag.appendChild(tr);});
</script></body></html>
"""
page = page.replace("__GRANTS__", embed(grants)).replace("__AGENTS__", embed(agents)).replace("__SUM__", embed(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
