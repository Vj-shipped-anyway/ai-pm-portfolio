"""Build demo.html from the files in out/. Run step_04_with_guard.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load_json(name):
    with open(os.path.join(HERE, "out", name), encoding="utf-8") as fh:
        return json.load(fh)


def as_js(obj):
    """JSON for an inline script: a closing script tag or a line separator inside a string cannot end the block."""
    return json.dumps(obj).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


with open(os.path.join(HERE, "out", "step_04_decisions.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
summary, rules = load_json("step_04_summary.json"), load_json("step_04_rules.json")
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>plan-guard: 86 plans, ten rules</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--block:#b3261e;--review:#8a5a00;--allow:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--block:#ff8a80;--review:#ffc266;--allow:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:24px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.BLOCK{color:var(--block);font-weight:600}.REVIEW{color:var(--review);font-weight:600}.ALLOW{color:var(--allow);font-weight:600}
.wrap{overflow-x:auto}table{min-width:680px}td:nth-child(-n+5){white-space:nowrap}td:last-child{overflow-wrap:anywhere;min-width:220px}
</style></head><body><main>
<h1>plan-guard: 86 plans, ten rules</h1>
<p class="s">Synthetic data. Each row is a Terraform plan in JSON form. The truth is the change I planted; the decision is what the rules printed. The same author wrote both, so read the numbers as a ceiling.</p>
<div class="k" id="k"></div>
<h2>Plans</h2>
<div><label>Decision <select id="d"><option value="">all</option><option>BLOCK</option><option>REVIEW</option><option>ALLOW</option></select></label>
<label>Planted truth <select id="t"><option value="">all</option><option value="block">block</option><option value="review">review</option><option value="ok">ok</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Plan</th><th>Planted change</th><th>Truth</th><th>Decision</th><th>Checked</th><th>Findings</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: the split_world_cidr, policy_weak_condition and queue_policy_world rows are risky and allowed. Known false alarms: the lb_internal_http rows go to review. Source: <code>python3 step_04_with_guard.py</code>.</p>
<h2>The ten rules</h2>
<div class="wrap"><table><thead><tr><th>Rule</th><th>Name</th><th>Severity</th><th>Resource types</th></tr></thead><tbody id="r"></tbody></table></div>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__, RULES=__RULES__;
function cell(tr,text,cls){var td=document.createElement('td');td.textContent=text;if(cls)td.className=cls;tr.appendChild(td);}
var k=document.getElementById('k');
[[SUM.risky_blocked+' of '+SUM.risky,'risky blocked'],[SUM.review_flagged+' of '+SUM.review,'need-a-look flagged'],[SUM.harmless_blocked+' of '+SUM.harmless,'harmless blocked'],[SUM.to_read+' of '+SUM.plans,'to read']].forEach(function(x){
var d=document.createElement('div'),b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((d&&r.decision!==d)||(t&&r.truth!==t))return;c++;var tr=document.createElement('tr');
cell(tr,r.plan_id);cell(tr,r.kind);cell(tr,r.truth);cell(tr,r.decision,r.decision);cell(tr,r.checked);cell(tr,r.findings);b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('d').onchange=draw;document.getElementById('t').onchange=draw;draw();
var rb=document.getElementById('r');RULES.forEach(function(x){var tr=document.createElement('tr');cell(tr,x.id);cell(tr,x.name);cell(tr,x.severity);cell(tr,x.types.join(', '));rb.appendChild(tr);});
</script></body></html>
"""
page = page.replace("__ROWS__", as_js(rows)).replace("__SUM__", as_js(summary)).replace("__RULES__", as_js(rules))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
