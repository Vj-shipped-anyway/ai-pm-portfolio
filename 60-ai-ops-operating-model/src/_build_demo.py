"""Build demo.html from out/step_04_programs.csv and out/step_04_summary.json. Run step_04_evidence_review.py first.
Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_programs.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Ops Review: 60 programs, 8 stages</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--over:#b3261e;--under:#8a5a00;--ok:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--over:#ff8a80;--under:#ffc266;--ok:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.OVERCLAIM{color:var(--over);font-weight:600}.UNDERCLAIM{color:var(--under);font-weight:600}.CONFIRMED{color:var(--ok);font-weight:600}
.wrap{overflow-x:auto}td:nth-child(-n+7){white-space:nowrap}table{min-width:760px}
</style></head><body><main>
<h1>AI Ops Review: 60 programs, 8 stages</h1>
<p class="s">Synthetic data. Each row is an AI program in bank operations. Claimed is the stage its owner reports, reviewed is the stage the evidence register reaches, truth is the stage from the evidence states I planted. The decision is what the review printed.</p>
<div class="k" id="k"></div>
<div><label>Decision <select id="d"><option value="">all</option><option>OVERCLAIM</option><option>CONFIRMED</option><option>UNDERCLAIM</option></select></label>
<label>Tier <select id="t"><option value="">all</option><option>1</option><option>2</option><option>3</option><option>4</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Program</th><th>Name</th><th>Tier</th><th>Claimed</th><th>Reviewed</th><th>Truth</th><th>Decision</th><th>Gaps within the claim</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: a row with a real-looking reference for an empty artifact (planted state hollow) passes every check, and so does lapsed evidence younger than 1.5 times its cycle. Rows where reviewed is above truth are those cases. Source: <code>python3 step_04_evidence_review.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
var k=document.getElementById('k');
[[SUM.stage_matches+' of '+SUM.programs,'stage equals truth'],[SUM.overclaims_flagged+' of '+SUM.overclaims,'overclaims flagged'],[SUM.overclaims_passed+' of '+SUM.overclaims,'overclaims passed'],[SUM.window_review+' of '+SUM.programs,'first 90 days evidenced']].forEach(function(x){
var d=document.createElement('div'),b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((d&&r.decision!==d)||(t&&r.tier!==t))return;c++;var tr=document.createElement('tr');
[r.program_id,r.program_name,r.tier,r.claimed,r.reviewed,r.truth,r.decision,r.gaps].forEach(function(v,i){var td=document.createElement('td');td.textContent=v;if(i===6)td.className=v;tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('d').onchange=draw;document.getElementById('t').onchange=draw;draw();
</script></body></html>
"""
page = page.replace("__ROWS__", json.dumps(rows).replace("</", "<\\/")).replace("__SUM__", json.dumps(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
