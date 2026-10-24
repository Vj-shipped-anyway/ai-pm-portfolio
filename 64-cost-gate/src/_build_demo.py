"""Build demo.html from out/step_04_decisions.csv and out/step_04_summary.json. Run step_04_with_cost_gate.py first.
Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_decisions.csv"), encoding="utf-8", newline="") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)


def js(obj) -> str:
    return json.dumps(obj).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cost Gate: 40 change requests, one budget</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--fail:#b3261e;--warn:#8a5a00;--pass:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--fail:#ff8a80;--warn:#ffc266;--pass:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:720px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.FAIL{color:var(--fail);font-weight:600}.WARN{color:var(--warn);font-weight:600}.PASS{color:var(--pass);font-weight:600}
.wrap{overflow-x:auto}td:nth-child(-n+6){white-space:nowrap}
</style></head><body><main>
<h1>Cost Gate: 40 change requests, one budget</h1>
<p class="s">Synthetic data. Each row is a change request with its own eval run of 236 items. The truth is what the generating parameters say about cost per correct answer; the decision is what the gate printed from the sampled rows. Ratios are against the ceiling: 1.000 is exactly at budget.</p>
<div class="k" id="k"></div>
<div><label>Decision <select id="d"><option value="">all</option><option>FAIL</option><option>WARN</option><option>PASS</option></select></label>
<label>Truth <select id="t"><option value="">all</option><option value="over_budget">over_budget</option><option value="within_budget">within_budget</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Change request</th><th>Planted change</th><th>Truth</th><th>True worst ratio</th><th>Measured whole-run ratio</th><th>Decision</th><th>Flagged scopes</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: thin_slice_regression rows pass because a slice under min_items is not judged alone, and a small_overshoot can pass because a few percent over is inside the noise of 236 items. Source: <code>python3 step_04_with_cost_gate.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
var k=document.getElementById('k');
[[SUM.over_fail+' of '+SUM.over_budget,'over budget, FAIL'],[SUM.over_warn+' of '+SUM.over_budget,'over budget, WARN'],[SUM.within_fail+' of '+SUM.within_budget,'within budget, FAIL'],[SUM.to_read+' of '+SUM.change_requests,'to read']].forEach(function(x){
  var d=document.createElement('div'),b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((d&&r.decision!==d)||(t&&r.truth!==t))return;c++;var tr=document.createElement('tr');
[r.cr_id,r.change_kind,r.truth,r.true_worst_ratio,r.overall_ratio,r.decision,r.flagged].forEach(function(v,i){var td=document.createElement('td');td.textContent=v;if(i===5)td.className=v;tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('d').onchange=draw;document.getElementById('t').onchange=draw;draw();
</script></body></html>
"""
page = page.replace("__ROWS__", js(rows)).replace("__SUM__", js(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
