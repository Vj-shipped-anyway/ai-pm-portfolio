"""Build demo.html from out/step_04_decisions.csv and out/step_04_summary.json. Run step_04_with_gate.py first.
Run (from src/): python3 _build_demo.py"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_decisions.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SMB FAQ Abstain: 30 questions, one gate</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--bad:#b3261e;--warn:#8a5a00;--good:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--bad:#ff8a80;--warn:#ffc266;--good:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;color:var(--mut)}.k b{font-size:20px;display:block;color:var(--fg)}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.wrap{overflow-x:auto}
.served_wrong,.false_abstain{color:var(--bad);font-weight:600}.caught,.declined{color:var(--good);font-weight:600}.served_ok{color:var(--good);font-weight:600}
</style></head><body><main>
<h1>SMB FAQ Abstain: 30 questions, one gate</h1>
<p class="s">Synthetic data. Each row is a question about a fictional bank's small-business products, the drafted answer a chatbot stand-in gave, and what the gate did with it. The drafts are stored text, not model output. The planted mode is how the draft was written; the outcome compares the decision with that truth.</p>
<div class="k" id="k"></div>
<div><label>Outcome <select id="o"><option value="">all</option><option>served_ok</option><option>served_wrong</option><option>caught</option><option>false_abstain</option><option>declined</option></select></label>
<label>Question class <select id="c"><option value="">all</option><option>answerable</option><option>not_in_kb</option><option>out_of_scope</option><option>state_specific</option><option>ambiguous</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>ID</th><th>Class</th><th>Question</th><th>Draft</th><th>Planted mode</th><th>Decision</th><th>Why</th><th>Outcome</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known limit: the served_wrong rows quote a number that is in the right passage and mean something else, so no check sees them. The set and the rules share an author, so the counts are a ceiling for these rules, not a rate on real traffic. Source: <code>python3 step_04_with_gate.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
var k=document.getElementById('k');
[[SUM.wrong_served+' of '+SUM.questions,'wrong answers served (draft only: '+SUM.wrong_served_draft_only+')'],[SUM.caught+' of '+SUM.draft_wrong,'wrong drafts held back'],[SUM.served_ok+' of '+SUM.draft_correct,'correct drafts served'],[SUM.held+' of '+SUM.questions,'handed to a banker']].forEach(function(x){
var d=document.createElement('div');var b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function draw(){var o=document.getElementById('o').value,c=document.getElementById('c').value,b=document.getElementById('b');
while(b.firstChild){b.removeChild(b.firstChild);}
var n=0;
ROWS.forEach(function(r){if((o&&r.outcome!==o)||(c&&r.q_class!==c))return;n++;var tr=document.createElement('tr');
[r.query_id,r.q_class,r.question,r.draft,r.mode,r.decision,r.reason+': '+r.detail,r.outcome].forEach(function(v,i){var td=document.createElement('td');td.textContent=v;if(i===7){td.className=v;}tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=n+' shown';}
document.getElementById('o').onchange=draw;document.getElementById('c').onchange=draw;draw();
</script></body></html>
"""

# "<" is escaped so no data string can close the script element
page = PAGE.replace("__ROWS__", json.dumps(rows).replace("<", "\\u003c")).replace("__SUM__", json.dumps(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
