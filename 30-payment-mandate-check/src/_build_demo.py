"""Build demo.html from out/step_04_decisions.csv and out/step_04_summary.json. Run step_04_with_mandate_check.py first.
Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_decisions.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
def safe_json(obj) -> str:
    """JSON for an inline script: a closing tag in the data cannot end the script early."""
    return json.dumps(obj).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Payment Mandate Check: 475 instructions, one gate</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--reject:#b3261e;--hold:#8a5a00;--release:#1e6b3a;--flag:#fff4d6}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--reject:#ff8a80;--hold:#ffc266;--release:#7fd49a;--flag:#3a3017}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
.f{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
label{color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:820px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
td.n{text-align:right;white-space:nowrap}td:nth-child(-n+3),td:nth-child(5),td:nth-child(6){white-space:nowrap}
.REJECT{color:var(--reject);font-weight:600}.HOLD{color:var(--hold);font-weight:600}.RELEASE{color:var(--release);font-weight:600}
tr.miss td{background:var(--flag)}
.wrap{overflow-x:auto}
</style></head><body><main>
<h1>Payment Mandate Check: 475 instructions, one gate</h1>
<p class="s">Synthetic data. Each row is a payment instruction an agent sent against a customer's mandate. The planted truth is the scenario I generated; the decision is what the check printed. Highlighted rows are where they differ.</p>
<div class="k" id="k"></div>
<div class="f">
<label>Decision <select id="d"><option value="">all</option><option>RELEASE</option><option>HOLD</option><option>REJECT</option></select></label>
<label>Planted truth <select id="t"><option value="">all</option><option>RELEASE</option><option>HOLD</option><option>REJECT</option></select></label>
<label>Scenario <select id="c"><option value="">all</option></select></label>
<label><input type="checkbox" id="m"> only rows where decision differs from the truth</label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Submission</th><th>Mandate</th><th>Payee</th><th class="n">Amount</th><th>Ccy</th><th>Received</th><th>Scenario</th><th>Truth</th><th>Decision</th><th>Reasons</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: split_below_confirm (the second and third piece of each split are released) and memo_contradicts_category (the free-text memo is not read). Source: <code>python3 step_04_with_mandate_check.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
var k=document.getElementById('k');
[[SUM.released+' of '+SUM.inside,'inside the mandate, released'],[SUM.held+' of '+SUM.for_person,'for a person, held'],[SUM.rejected+' of '+SUM.outside,'outside the mandate, rejected'],[SUM.legit_stopped+' of '+SUM.inside,'legitimate stopped'],[SUM.still_released+' of '+SUM.instructions,'released that should not be']].forEach(function(x){var d=el('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var kinds={};ROWS.forEach(function(r){kinds[r.kind]=1;});
var sel=document.getElementById('c');Object.keys(kinds).sort().forEach(function(x){var o=el('option',x);o.value=x;sel.appendChild(o);});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,c=sel.value,m=document.getElementById('m').checked,b=document.getElementById('b');
while(b.firstChild)b.removeChild(b.firstChild);var n=0;
ROWS.forEach(function(r){if((d&&r.decision!==d)||(t&&r.truth!==t)||(c&&r.kind!==c)||(m&&r.decision===r.truth))return;n++;
var tr=el('tr');if(r.decision!==r.truth)tr.className='miss';
[r.submission_id,r.mandate_id,r.payee_id,r.amount,r.currency,r.received_at,r.kind,r.truth,r.decision,r.reasons].forEach(function(v,i){var td=el('td',v);if(i===3)td.className='n';if(i===7||i===8)td.className=v;tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=n+' shown';}
['d','t','c','m'].forEach(function(id){document.getElementById(id).onchange=draw;});draw();
</script></body></html>
"""
page = page.replace("__ROWS__", safe_json(rows)).replace("__SUM__", safe_json(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
