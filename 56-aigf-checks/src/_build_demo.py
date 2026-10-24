"""Build demo.html from out/step_04_rows.csv, out/step_04_risks.csv and out/step_04_summary.json.
Run step_04_with_checks.py first. Run (from src/): python3 _build_demo.py"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read_csv(name: str) -> list:
    with open(os.path.join(HERE, "out", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def embed(obj) -> str:
    """JSON for a script tag: '<' is escaped so file text cannot close the tag."""
    return json.dumps(obj).replace("<", "\\u003c")


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>aigf-checks: 73 crosswalk rows, one check</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--bad:#b3261e;--warn:#8a5a00;--good:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--bad:#ff8a80;--warn:#ffc266;--good:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:24px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:720px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.found{color:var(--good);font-weight:600}.missed{color:var(--bad);font-weight:600}.quiet{color:var(--mut)}.false{color:var(--warn);font-weight:600}
.wrap{overflow-x:auto}code{font-size:13px}
</style></head><body><main>
<h1>aigf-checks: 73 crosswalk rows, one check</h1>
<p class="s">Synthetic data. Each row claims that one check covers one framework risk and that one line of its output shows it. The planted kind is the defect I built into the row; the found column is what <code>aigf_checks.py</code> reported.</p>
<div class="k" id="k"></div>
<div><label>Planted kind <select id="t"></select></label>
<label>Result <select id="r"><option value="">all</option><option value="found">flagged</option><option value="quiet">not flagged</option><option value="missed">defective, not flagged</option><option value="false">harmless, flagged</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Row</th><th>Risk</th><th>Check</th><th>Covers</th><th>Claim</th><th>Planted kind</th><th>Found</th><th>Detail</th></tr></thead><tbody id="b"></tbody></table></div>
<h2>Status per risk</h2>
<p class="s">The status the tool gives from the rows that pass, next to the status the planted truth implies.</p>
<div class="wrap"><table><thead><tr><th>Risk</th><th>Title</th><th>Tool</th><th>Planted truth</th></tr></thead><tbody id="rb"></tbody></table></div>
<p class="s">Known misses: notes that overclaim in other words, and checks that declare an aspect they do not exercise. Source: <code>python3 step_04_with_checks.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, RISKS=__RISKS__, SUM=__SUM__;
var DEFECTIVE_KIND=function(k){return ['ok','ok_reformatted','ok_negated_word','ok_partial'].indexOf(k)<0;};
function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
var k=document.getElementById('k');
[[SUM.found+' of '+SUM.defective,'defective rows found'],[SUM.false_alarms+' of '+SUM.clean,'harmless rows flagged'],[SUM.risks_right+' of '+SUM.risks,'risk statuses right'],[SUM.to_read+' of '+SUM.rows,'rows to read']].forEach(function(x){var d=el('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var kinds=[];ROWS.forEach(function(r){if(kinds.indexOf(r.planted_kind)<0)kinds.push(r.planted_kind);});kinds.sort();
var t=document.getElementById('t');t.appendChild(el('option','all'));t.firstChild.value='';
kinds.forEach(function(x){var o=el('option',x);o.value=x;t.appendChild(o);});
function state(r){var def=DEFECTIVE_KIND(r.planted_kind),flag=r.found!=='';if(flag&&def)return 'found';if(flag)return 'false';if(def)return 'missed';return 'quiet';}
function draw(){var tk=t.value,rs=document.getElementById('r').value,b=document.getElementById('b');while(b.firstChild)b.removeChild(b.firstChild);var c=0;
ROWS.forEach(function(r){var s=state(r);if((tk&&r.planted_kind!==tk)||(rs&&s!==rs))return;c++;var tr=el('tr');
[r.row_id,r.risk_id,r.check_id,r.covers,r.claim,r.planted_kind,r.found||'none',r.detail].forEach(function(v,i){tr.appendChild(el('td',v,i===6?s:''));});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
var rb=document.getElementById('rb');
RISKS.forEach(function(r){var tr=el('tr');[r.risk_id,r.title,r.status,r.planted_status].forEach(function(v,i){tr.appendChild(el('td',v,i===2&&r.status!==r.planted_status?'missed':''));});rb.appendChild(tr);});
t.onchange=draw;document.getElementById('r').onchange=draw;draw();
</script></body></html>
"""

with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
page = PAGE.replace("__ROWS__", embed(read_csv("step_04_rows.csv"))).replace("__RISKS__", embed(read_csv("step_04_risks.csv"))) \
           .replace("__SUM__", embed(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
