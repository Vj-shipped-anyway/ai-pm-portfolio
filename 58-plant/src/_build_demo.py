"""Build demo.html from out/step_04_rows.csv and out/step_04_summary.json. Run step_04_with_a_key.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_rows.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)


def embed(obj) -> str:
    """JSON that is safe inside a script element: no literal < can close it."""
    return json.dumps(obj).replace("<", "\\u003c")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>plant: an answer key for a ledger checker</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--good:#1e6b3a;--warn:#8a5a00;--bad:#b3261e}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--good:#7fd49a;--warn:#ffc266;--bad:#ff8a80}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:24px 0 8px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
td.n,th.n{text-align:right}
.found,.look-alike-left-alone{color:var(--good);font-weight:600}.missed,.look-alike-flagged,.clean-row-flagged{color:var(--bad);font-weight:600}
.wrap{overflow-x:auto}.wrap table{min-width:640px}
</style></head><body><main>
<h1>plant: an answer key for a ledger checker</h1>
<p class="s">Synthetic ledger. Every planted row is in a separate answer key with its behavior and the exact change. Two rule sets are scored against the same key. Rows are shown when planted, or when a rule set flagged a clean row.</p>
<div><label>Checker <select id="c"><option value="naive">naive</option><option value="tuned">tuned</option></select></label></div>
<div class="k" id="k"></div>
<h2>By planted behavior</h2>
<div class="wrap"><table><thead><tr><th>Behavior</th><th>Role</th><th class="n">Planted</th><th class="n">Naive flagged</th><th class="n">Tuned flagged</th></tr></thead><tbody id="t"></tbody></table></div>
<h2>Rows</h2>
<div><label>Outcome <select id="o"><option value="">all</option><option>found</option><option>missed</option><option>look-alike flagged</option><option>look-alike left alone</option><option>clean row flagged</option></select></label>
<label>Behavior <select id="b"><option value="">all</option></select></label><span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Row</th><th>Ref</th><th>Merchant</th><th class="n">Amount</th><th class="n">Day</th><th class="n">Posted</th><th>Memo</th><th>Planted behavior</th><th>Outcome</th></tr></thead><tbody id="r"></tbody></table></div>
<p class="s">Known limit: the key scores the variants I planted. The paraphrased injection uses three sentences, so a checker that memorizes them would score full marks. Source: <code>python3 step_04_with_a_key.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
function cell(tr,text,cls){var td=document.createElement('td');td.textContent=text;if(cls)td.className=cls;tr.appendChild(td);}
function slug(s){return s.replace(/ /g,'-');}
function tiles(){var c=document.getElementById('c').value,s=SUM.checkers[c],k=document.getElementById('k');k.textContent='';
[[s.found+' of '+s.positives,'planted failures found'],[s.look_alikes_flagged+' of '+s.look_alikes,'look-alikes flagged'],[s.clean_flagged+' of '+s.clean,'clean rows flagged'],[(s.found/s.flagged).toFixed(2),'precision']].forEach(function(x){
var d=document.createElement('div'),b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});}
function table(){var t=document.getElementById('t');SUM.behaviors.forEach(function(r){var tr=document.createElement('tr');cell(tr,r.behavior);cell(tr,r.role);cell(tr,r.planted,'n');cell(tr,r.naive,'n');cell(tr,r.tuned,'n');t.appendChild(tr);});}
function draw(){var c=document.getElementById('c').value,o=document.getElementById('o').value,b=document.getElementById('b').value,body=document.getElementById('r'),n=0;body.textContent='';
ROWS.forEach(function(r){var out=r[c];if((o&&out!==o)||(b&&r.behavior!==b))return;n++;var tr=document.createElement('tr');
cell(tr,r.row_id);cell(tr,r.ref);cell(tr,r.merchant);cell(tr,r.amount,'n');cell(tr,r.day,'n');cell(tr,r.posted_day,'n');cell(tr,r.memo);cell(tr,r.behavior||'(clean)');cell(tr,out,slug(out));body.appendChild(tr);});
document.getElementById('n').textContent=n+' shown';tiles();}
var sel=document.getElementById('b');SUM.behaviors.forEach(function(r){var op=document.createElement('option');op.value=r.behavior;op.textContent=r.behavior;sel.appendChild(op);});
['c','o','b'].forEach(function(id){document.getElementById(id).onchange=draw;});table();draw();
</script></body></html>
"""
page = page.replace("__ROWS__", embed(rows)).replace("__SUM__", embed(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
