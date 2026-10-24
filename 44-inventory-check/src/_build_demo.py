"""Build demo.html from the files step_04_with_checks.py writes to out/. Run that script first.
Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read_csv(name):
    with open(os.path.join(HERE, "out", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


rows = read_csv("step_04_systems.csv")
shadows = read_csv("step_04_shadows.csv")
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Inventory Check: 100 records, three tests</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--fail:#b3261e;--review:#8a5a00;--ok:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--fail:#ff8a80;--review:#ffc266;--ok:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:28px 0 4px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:720px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.FAIL{color:var(--fail);font-weight:600}.REVIEW{color:var(--review);font-weight:600}.OK{color:var(--ok);font-weight:600}
.wrap{overflow-x:auto}
</style></head><body><main>
<h1>Inventory Check: 100 records, three tests</h1>
<p class="s">Synthetic data. Each row is an inventory record for a generative or agentic system. The planted case is what I built the record as; the verdict is what the tests printed.</p>
<div class="k" id="k"></div>
<div><label>Verdict <select id="d"><option value="">all</option><option>FAIL</option><option>REVIEW</option><option>OK</option></select></label>
<label>Planted truth <select id="t"><option value="">all</option><option value="defective">defective</option><option value="clean">clean</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Tier</th><th>Kind</th><th>Planted case</th><th>Truth</th><th>Verdict</th><th>Findings</th></tr></thead><tbody id="b"></tbody></table></div>
<h2>Systems that call a model outside the inventory</h2>
<p class="s">The usage export names four of the seven. The untagged traffic is reported but cannot be attributed. Two systems send their calls under a listed system's id and are not found.</p>
<div class="wrap"><table><thead><tr><th>Shadow system</th><th>How it hides</th><th>Tagged as</th><th>Calls</th><th>Result</th></tr></thead><tbody id="s"></tbody></table></div>
<p class="s">Known misses: the placeholder_novel rows (a placeholder the word list does not hold) and the rubber_stamp rows (a review date refreshed in bulk) pass. The seasonal_quiet rows are flagged as idle though they are fine. Source: <code>python3 step_04_with_checks.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SHADOWS=__SHADOWS__, SUM=__SUM__;
function cell(tr,v,cls){var td=document.createElement('td');td.textContent=v;if(cls)td.className=cls;tr.appendChild(td);}
var k=document.getElementById('k');
[[SUM.defective_flagged+' of '+SUM.defective,'defective flagged'],[SUM.clean_flagged+' of '+SUM.clean,'clean flagged'],[SUM.to_open+' of '+SUM.records,'records to open'],[SUM.shadows_named+' of '+SUM.shadows,'shadow systems named']].forEach(function(x){var d=document.createElement('div');var b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((d&&r.verdict!==d)||(t&&r.truth!==t))return;c++;var tr=document.createElement('tr');
[r.system_id,r.name,r.status,r.risk_tier,r.kind,r.case_kind,r.truth,r.verdict,r.findings].forEach(function(v,i){cell(tr,v,i===7?v:'');});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
var sb=document.getElementById('s');
SHADOWS.forEach(function(r){var tr=document.createElement('tr');[r.shadow_name,r.shadow_kind,r.tagged_as,r.calls,r.result].forEach(function(v){cell(tr,v,'');});sb.appendChild(tr);});
document.getElementById('d').onchange=draw;document.getElementById('t').onchange=draw;draw();
</script></body></html>
"""


def embed(obj):
    """JSON for an inline script: a closing tag inside a value must not end the script."""
    return json.dumps(obj).replace("</", "<\\/")


page = page.replace("__ROWS__", embed(rows)).replace("__SHADOWS__", embed(shadows)).replace("__SUM__", embed(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
