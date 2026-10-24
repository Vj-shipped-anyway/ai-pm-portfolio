"""Build demo.html from out/step_04_decisions.csv. Run step_04_with_gate.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
rows = list(csv.DictReader(open(os.path.join(HERE, "out", "step_04_decisions.csv"), encoding="utf-8")))
summary = json.load(open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8"))
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tool Schema Drift: 67 pull requests, one gate</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--block:#b3261e;--review:#8a5a00;--allow:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--block:#ff8a80;--review:#ffc266;--allow:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.BLOCK{color:var(--block);font-weight:600}.REVIEW{color:var(--review);font-weight:600}.ALLOW{color:var(--allow);font-weight:600}
.wrap{overflow-x:auto}td:nth-child(-n+5){white-space:nowrap}table{min-width:720px}
</style></head><body><main>
<h1>Tool Schema Drift: 67 pull requests, one gate</h1>
<p class="s">Synthetic data. Each row is a pull request that changes one tool schema. The truth is the change I planted; the decision is what the gate printed.</p>
<div class="k" id="k"></div>
<div><label>Decision <select id="d"><option value="">all</option><option>BLOCK</option><option>REVIEW</option><option>ALLOW</option></select></label>
<label>Planted truth <select id="t"><option value="">all</option><option value="breaking">breaking</option><option value="behavior_risk">behavior_risk</option><option value="non_breaking">non_breaking</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>PR</th><th>Tool</th><th>Planted change</th><th>Truth</th><th>Decision</th><th>Broken calls</th><th>Findings</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: the meaning_flip rows (no number or unit in the new wording) and the unit_scale rows (same unit word, new scale) are allowed. Source: <code>python3 step_04_with_gate.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
var k=document.getElementById('k');
[[SUM.breaking_blocked+' of '+SUM.breaking,'breaking blocked'],[SUM.behavior_risk_flagged+' of '+SUM.behavior_risk,'behavior-risk flagged'],[SUM.harmless_blocked+' of '+SUM.harmless,'harmless blocked'],[SUM.to_read+' of '+SUM.pull_requests,'to read']].forEach(function(x){var d=document.createElement('div');d.innerHTML='<b>'+x[0]+'</b>'+x[1];k.appendChild(d);});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,b=document.getElementById('b');b.innerHTML='';var c=0;
ROWS.forEach(function(r){if((d&&r.decision!==d)||(t&&r.truth!==t))return;c++;var tr=document.createElement('tr');
[r.pr_id,r.tool,r.change_kind,r.truth,r.decision,r.broken_calls,r.findings].forEach(function(v,i){var td=document.createElement('td');td.textContent=v;if(i===4)td.className=v;tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('d').onchange=draw;document.getElementById('t').onchange=draw;draw();
</script></body></html>
"""
page = page.replace("__ROWS__", json.dumps(rows)).replace("__SUM__", json.dumps(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
