"""Build demo.html from out/step_04_queues.csv. Run step_04_with_review_capacity.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_queues.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Review capacity: 13 queues, four ways to size them</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--short:#b3261e;--spare:#8a5a00;--exact:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--short:#ff8a80;--spare:#ffc266;--exact:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
td.n,th.n{text-align:right}
.short{color:var(--short);font-weight:600}.spare{color:var(--spare);font-weight:600}.exact{color:var(--exact);font-weight:600}
.wrap{overflow-x:auto}td:nth-child(-n+2){white-space:nowrap}
</style></head><body><main>
<h1>Review capacity: 13 queues, four ways to size them</h1>
<p class="s">Synthetic data. Each row is a review queue replayed over ten working days. Needed is the smallest number of reviewers at the desk that met the queue's wait target and utilization cap on that replay. The other columns are what each method said.</p>
<div class="k" id="k"></div>
<div><label>Outcome <select id="v"><option value="">all</option><option>exact</option><option>short</option><option>spare</option></select></label>
<label>Planted kind <select id="t"><option value="">all</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Queue</th><th>Kind</th><th class="n">Needed</th><th class="n">Average load</th><th class="n">Erlang C</th><th class="n">Tool</th><th class="n">Tool, from days 1-10</th><th class="n">Late % at Erlang C</th><th class="n">Late % at tool</th><th class="n">Allowed %</th><th>Tool vs needed</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: the bursty queue is one reviewer short, and the queue whose volume rose after the history was taken is short when the tool is fitted on that history. Source: <code>python3 step_04_with_review_capacity.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
var k=document.getElementById('k');
[[SUM.exact+' of '+SUM.queues,'tool matches the needed reviewers'],[SUM.meets+' of '+SUM.queues,'queues meet both limits (Erlang C: '+SUM.erlang_meets+')'],[SUM.late_pct+'%','cases late (Erlang C: '+SUM.erlang_late_pct+'%)'],[SUM.seats+' / '+SUM.true_seats,'reviewers chosen / needed']].forEach(function(x){var d=document.createElement('div');var b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var kinds={};ROWS.forEach(function(r){kinds[r.kind]=1;});
var ts=document.getElementById('t');Object.keys(kinds).sort().forEach(function(n){var o=document.createElement('option');o.value=n;o.textContent=n;ts.appendChild(o);});
function draw(){var v=document.getElementById('v').value,t=ts.value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((v&&r.verdict!==v)||(t&&r.kind!==t))return;c++;var tr=document.createElement('tr');
[r.queue_id,r.kind,r.true_seats,r.average_load_seats,r.erlang_c_seats,r.tool_seats,r.forecast_seats,r.erlang_late_pct,r.tool_late_pct,r.target_late_pct,r.verdict].forEach(function(x,i){var td=document.createElement('td');td.textContent=x;if(i>=2&&i<=9)td.className='n';if(i===10)td.className=x;tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('v').onchange=draw;ts.onchange=draw;draw();
</script></body></html>
"""
page = page.replace("__ROWS__", json.dumps(rows)).replace("__SUM__", json.dumps(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
