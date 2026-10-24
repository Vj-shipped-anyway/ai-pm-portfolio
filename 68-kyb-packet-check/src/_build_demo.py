"""Build demo.html from out/step_04_decisions.csv and out/step_04_summary.json.

Run step_04_with_check.py first.  Run (from src/):  python3 _build_demo.py
"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>KYB Packet Check: 75 synthetic packets</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--review:#8a5a00;--pass:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--review:#ffc266;--pass:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;margin:2px 0}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:720px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.REVIEW{color:var(--review);font-weight:600}.PASS{color:var(--pass);font-weight:600}
.wrap{overflow-x:auto}td:nth-child(-n+5){white-space:nowrap}
</style></head><body><main>
<h1>KYB Packet Check: 75 synthetic packets</h1>
<p class="s">Synthetic data. Each row is a business-onboarding packet whose filing text a model has read. The planted column is what I built into the extraction; the decision is what the checks printed.</p>
<div class="k" id="k"></div>
<div><label>Decision <select id="d"><option value="">all</option><option>REVIEW</option><option>PASS</option></select></label>
<label>Planted <select id="t"><option value="">all</option><option>misread</option><option>clean</option></select></label>
<label>Wrong people in the file <select id="w"><option value="">all</option><option>yes</option><option>no</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Packet</th><th>Entity</th><th>Planted scenario</th><th>Planted</th><th>Decision</th><th>Wrong people</th><th>Findings</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known miss: the three nominee_note rows pass, because the note that moves the owner is neither a number nor a field. Source: <code>python3 step_04_with_check.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
var k=document.getElementById('k');
[[SUM.misreads_flagged+' of '+SUM.misreads,'misreads flagged'],[SUM.clean_flagged+' of '+SUM.clean,'clean packets flagged'],[SUM.wrong_people_flagged+' of '+SUM.wrong_people,'wrong-people packets flagged'],[SUM.sent_to_person+' of '+SUM.packets,'sent to a person']].forEach(function(x){var d=document.createElement('div');var b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,w=document.getElementById('w').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((d&&r.decision!==d)||(t&&r.planted!==t)||(w&&r.wrong_people!==w))return;c++;var tr=document.createElement('tr');
[r.packet_id,r.entity,r.scenario,r.planted,r.decision,r.wrong_people,r.finding_kinds].forEach(function(v,i){var td=document.createElement('td');td.textContent=v;if(i===4)td.className=v;tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
['d','t','w'].forEach(function(id){document.getElementById(id).onchange=draw;});draw();
</script></body></html>
"""


def as_script_data(obj) -> str:
    """JSON for an inline script. A '<' is escaped so a closing script tag inside the data cannot end the script early."""
    return json.dumps(obj).replace("<", "\\u003c")


def main() -> None:
    with open(os.path.join(HERE, "out", "step_04_decisions.csv"), newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)
    page = PAGE.replace("__ROWS__", as_script_data(rows)).replace("__SUM__", as_script_data(summary))
    with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print("Wrote demo.html")


if __name__ == "__main__":
    main()
