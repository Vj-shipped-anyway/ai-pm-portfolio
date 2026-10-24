"""Build demo.html from out/step_03_variants.csv, out/step_04_decisions.csv and out/step_04_summary.json.
Run step_03 and step_04 first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def rows_of(name):
    with open(os.path.join(HERE, "out", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


variants = rows_of("step_03_variants.csv")
decisions = rows_of("step_04_decisions.csv")
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Entitlement Canary: 50 pull requests, one leak test</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--block:#b3261e;--review:#8a5a00;--allow:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--block:#ff8a80;--review:#ffc266;--allow:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:24px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.BLOCK{color:var(--block);font-weight:600}.REVIEW{color:var(--review);font-weight:600}.ALLOW{color:var(--allow);font-weight:600}
.wrap{overflow-x:auto}td{white-space:nowrap}table{min-width:560px}
</style></head><body><main>
<h1>Entitlement Canary: 50 pull requests, one leak test</h1>
<p class="s">Synthetic data. Each row is a pull request that changes a retrieval system. The truth is the change I planted; the decision is what the canary check printed.</p>
<div class="k" id="k"></div>
<h2>What each part of the gate buys</h2>
<div class="wrap"><table><thead><tr><th>Variant</th><th>Leaking caught</th><th>Clean flagged</th></tr></thead><tbody id="v"></tbody></table></div>
<h2>Every pull request</h2>
<div><label>Decision <select id="d"><option value="">all</option><option>BLOCK</option><option>REVIEW</option><option>ALLOW</option></select></label>
<label>Truth <select id="t"><option value="">all</option><option value="leak">leak</option><option value="no leak">no leak</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>PR</th><th>Planted change</th><th>Truth</th><th>Decision</th><th>Leaking canaries</th><th>Retired</th><th>Inert</th><th>Leaked pairs</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known miss: a leak that touches one (user, document) pair can pass. The same author wrote the data and the rules, so these numbers are a ceiling for these rules. Source: <code>python3 step_04_with_canary.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__, VAR=__VAR__;
function cell(tr,v,cls){var td=document.createElement('td');td.textContent=v;if(cls)td.className=cls;tr.appendChild(td);}
var k=document.getElementById('k');
[[SUM.leaking_blocked+' of '+SUM.leaking,'leaking blocked'],[SUM.clean_blocked+' of '+SUM.clean,'clean blocked'],[SUM.clean_reviewed+' of '+SUM.clean,'clean sent to review'],[SUM.to_read+' of '+SUM.pull_requests,'to read']].forEach(function(x){
var d=document.createElement('div'),b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var v=document.getElementById('v');
VAR.forEach(function(r){var tr=document.createElement('tr');cell(tr,r.variant);cell(tr,r.caught+' of '+r.leaking);cell(tr,r.flagged+' of '+r.clean);v.appendChild(tr);});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((d&&r.decision!==d)||(t&&r.truth!==t))return;c++;var tr=document.createElement('tr');
cell(tr,r.pr_id);cell(tr,r.change_kind);cell(tr,r.truth);cell(tr,r.decision,r.decision);cell(tr,r.leaking_canaries);cell(tr,r.retired);cell(tr,r.inert);cell(tr,r.leaked_pairs);b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('d').onchange=draw;document.getElementById('t').onchange=draw;draw();
</script></body></html>
"""


def embed(obj):
    return json.dumps(obj).replace("</", "<\\/")


page = page.replace("__ROWS__", embed(decisions)).replace("__SUM__", embed(summary)).replace("__VAR__", embed(variants))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
