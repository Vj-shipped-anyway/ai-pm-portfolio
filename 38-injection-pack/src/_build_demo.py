"""Build demo.html from out/step_04_decisions.csv and out/step_04_summary.json. Run step_04_with_pack.py first.
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
<title>Injection Pack: 51 rule changes, one regression suite</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--block:#b3261e;--allow:#1e6b3a;--warn:#8a5a00}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--block:#ff8a80;--allow:#7fd49a;--warn:#ffc266}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.BLOCK{color:var(--block);font-weight:600}.ALLOW{color:var(--allow);font-weight:600}.harmful{color:var(--warn);font-weight:600}
.wrap{overflow-x:auto}td:nth-child(-n+3){white-space:nowrap}
</style></head><body><main>
<h1>Injection Pack: 51 rule changes, one regression suite</h1>
<p class="s">Synthetic data. Each row is a pull request that changes the rules of a five-layer prompt gateway. Truth is what the change does to a held-out population of 1,000 attacks and 500 benign cases; the decision is what the 160-case pack printed when run on the old and the new rules.</p>
<div class="k" id="k"></div>
<div><label>Decision <select id="d"><option value="">all</option><option>BLOCK</option><option>ALLOW</option></select></label>
<label>Held-out truth <select id="t"><option value="">all</option><option value="harmful">harmful</option><option value="harmless">harmless</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>PR</th><th>Change</th><th>Kind</th><th>Layer</th><th>Change in attacks blocked (held-out)</th><th>Change in benign blocked (held-out)</th><th>Truth</th><th>Decision</th><th>Pack regressions</th><th>Blind-spot note</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses are the harmful rows that read ALLOW. The pack has no case for the encoded-payload technique, so removing the rule that catches it passes; the tool prints a blind-spot note for that row. Source: <code>python3 step_04_with_pack.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
var k=document.getElementById('k');
[[SUM.harmful_stopped+' of '+SUM.harmful,'harmful changes stopped'],[SUM.harmless_stopped+' of '+SUM.harmless,'harmless changes stopped'],[SUM.exact+' of '+SUM.pull_requests,'decisions match the truth'],[SUM.missed+' of '+SUM.harmful,'harmful changes that pass']].forEach(function(x){var d=document.createElement('div'),b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((d&&r.decision!==d)||(t&&r.truth!==t))return;c++;var tr=document.createElement('tr');
[r.pr_id,r.note,r.kind,r.layer,String(-Number(r.lost)),String(Number(r.gained)),r.truth,r.decision,r.pack_regressions,r.blind_spot_note].forEach(function(v,i){var td=document.createElement('td');td.textContent=v;if(i===7)td.className=v;if(i===6&&v==='harmful')td.className='harmful';tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('d').onchange=draw;document.getElementById('t').onchange=draw;draw();
</script></body></html>
"""
page = page.replace("__ROWS__", js(rows)).replace("__SUM__", js(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
