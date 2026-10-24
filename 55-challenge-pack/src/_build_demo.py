"""Build demo.html from the files step_04_with_the_pack.py writes to out/. Run that step first.

Run (from src/):  python3 _build_demo.py
"""
from __future__ import annotations

import csv
import json
import os

from challenge_pack import ITEMS, TIERS

HERE = os.path.dirname(os.path.abspath(__file__))


def read_csv(name: str) -> list:
    with open(os.path.join(HERE, "out", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Challenge pack: a test plan by tier</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--bad:#b3261e;--ok:#1e6b3a;--warn:#8a5a00;--card:#f6f7f9}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--bad:#ff8a80;--ok:#7fd49a;--warn:#ffc266;--card:#1b1e23}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:24px 0 8px}p.s{color:var(--mut);margin:0 0 12px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 12px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;background:var(--card)}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select,button{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px 8px;font:inherit}
button{cursor:pointer}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.wrap{overflow-x:auto}table{min-width:640px}
.bad{color:var(--bad);font-weight:600}.good{color:var(--ok);font-weight:600}.warn{color:var(--warn);font-weight:600}
#detail{border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin-top:12px;background:var(--card)}
#detail p{margin:4px 0}
</style></head><body><main>
<h1>Challenge pack: a test plan by tier</h1>
<p class="s">Synthetic data. Each row is an AI use case. The tier used is the higher of the declared tier and the rubric recomputed from the form. The true tier is the one I planted; the gaps are what the pack printed.</p>
<div class="k" id="k"></div>
<h2>Tier to test plan (an assumption of this prototype)</h2>
<div class="wrap"><table><thead><tr><th>Tier</th><th>Depth</th><th>Core items</th><th>Evidence window</th></tr></thead><tbody id="t"></tbody></table></div>
<h2>Use cases</h2>
<div><label>Gaps <select id="g"><option value="">all</option><option value="with">with gaps</option><option value="none">complete</option></select></label>
<label>Tier used <select id="u"><option value="">all</option><option>1</option><option>2</option><option>3</option><option>4</option></select></label>
<label>Against the truth <select id="w"><option value="">all</option><option value="below">tier used below true</option><option value="above">tier used above true</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Use case</th><th>Title</th><th>Type</th><th>Declared</th><th>Used</th><th>True</th><th>Plan items</th><th>Gaps</th></tr></thead><tbody id="b"></tbody></table></div>
<div id="detail"><p class="s">Select a use case to see its gaps.</p></div>
<p class="s">Known limits: hollow evidence passes every check, and a use case whose form understates its risk keeps a light plan. Source: <code>python3 step_04_with_the_pack.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, GAPS=__GAPS__, SUM=__SUM__, TIERS=__TIERS__, NAMES=__NAMES__;
function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
var k=document.getElementById('k');
[[SUM.covered+' of '+SUM.required,'owed items asked for'],[SUM.found_total+' of '+SUM.defects,'planted defects found'],[(SUM.fine_flagged+SUM.hard.reaffirmed[0]+SUM.hard.boundary[0]+SUM.hard.first_line[0])+' false alarms','on '+(SUM.hard.reaffirmed[1]+SUM.hard.boundary[1]+SUM.hard.first_line[1])+' hard negatives'],[SUM.hollow_pass+' of '+SUM.hollow,'hollow items that pass']].forEach(function(x){var d=el('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var tb=document.getElementById('t');
TIERS.forEach(function(t){var tr=el('tr');[t.tier,t.depth,t.items,t.window+' months'].forEach(function(v){tr.appendChild(el('td',v));});tb.appendChild(tr);});
function show(id){var d=document.getElementById('detail');d.textContent='';var g=GAPS[id]||[];
d.appendChild(el('p',id+': '+(g.length?g.length+' gap'+(g.length>1?'s':''):'no gaps'),g.length?'bad':'good'));
g.forEach(function(x){d.appendChild(el('p',x.item+' '+(NAMES[x.item]||'')+': '+x.kinds.replace(/_/g,' ')+' ('+x.detail+')'));});}
function draw(){var g=document.getElementById('g').value,u=document.getElementById('u').value,w=document.getElementById('w').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){var used=+r.tier_used,tru=+r.true_tier,gaps=+r.gaps;
if((g==='with'&&!gaps)||(g==='none'&&gaps)||(u&&String(used)!==u)||(w==='below'&&!(used<tru))||(w==='above'&&!(used>tru)))return;c++;
var tr=el('tr'),td=el('td'),btn=el('button',r.use_case_id);btn.onclick=function(){show(r.use_case_id);};td.appendChild(btn);tr.appendChild(td);
[r.title,r.model_type,r.declared_tier,r.tier_used,r.true_tier,r.plan_items].forEach(function(v){tr.appendChild(el('td',v));});
tr.appendChild(el('td',r.gaps,gaps?'bad':'good'));b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
['g','u','w'].forEach(function(i){document.getElementById(i).onchange=draw;});draw();
</script></body></html>
"""


def js(obj) -> str:
    return json.dumps(obj).replace("</", "<\\/")


def main() -> None:
    rows = read_csv("step_04_cases.csv")
    gaps = {}
    for g in read_csv("step_04_gaps.csv"):
        gaps.setdefault(g["use_case_id"], []).append({"item": g["item_id"], "kinds": g["kinds"], "detail": g["detail"]})
    with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)
    tiers = [{"tier": t, "depth": TIERS[t]["depth"], "window": TIERS[t]["window_months"],
              "items": len([i for i in ITEMS if i["overlay"] == "" and i["min_tier"] <= t])} for t in sorted(TIERS)]
    names = {i["id"]: i["title"] for i in ITEMS}
    page = (PAGE.replace("__ROWS__", js(rows)).replace("__GAPS__", js(gaps)).replace("__SUM__", js(summary))
            .replace("__TIERS__", js(tiers)).replace("__NAMES__", js(names)))
    with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    print("Wrote demo.html")


if __name__ == "__main__":
    main()
