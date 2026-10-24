"""Build demo.html from out/step_04_scorecard.csv and out/step_04_summary.json. Run step_04_with_scorecard.py first.

Run (from src/):  python3 _build_demo.py
"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Failover Scorecard: 48 services, one rule</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--ok:#1e6b3a;--bad:#b3261e;--mid:#8a5a00}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--ok:#7fd49a;--bad:#ff8a80;--mid:#ffc266}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
.f{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
label{color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;margin-left:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.wrap{overflow-x:auto}td.r{min-width:260px}td.n{white-space:nowrap}
.READY,.NOT_REQUIRED{color:var(--ok);font-weight:600}.DEPENDENCY,.SLOW,.STALE,.CHANGED{color:var(--mid);font-weight:600}
.FAILED,.UNTESTED,.NO_PATH{color:var(--bad);font-weight:600}
</style></head><body><main>
<h1>Failover Scorecard: 48 services, one rule</h1>
<p class="s">Synthetic data. Each row is a service in a made-up bank. The status is what the readiness rule printed; the planted truth is the story the generator gave the service, fixed before the rule ran.</p>
<div class="k" id="k"></div>
<div class="f">
<label>Status<select id="st"><option value="">all</option></select></label>
<label>Tier<select id="ti"><option value="">all</option><option>1</option><option>2</option><option>3</option></select></label>
<label>Domain<select id="dm"><option value="">all</option></select></label>
<label>Planted truth<select id="tr"><option value="">all</option><option>ready</option><option>not_ready</option><option>accepted</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>ID</th><th>Service</th><th>Domain</th><th>Tier</th><th>Status</th><th>Why</th><th>Planted truth</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known miss: the rows with status READY and planted truth not_ready are services that need a dependency the map does not list. The rule follows only declared edges. Windows of 180, 365 and 540 days by tier are my assumption. Source: <code>python3 step_04_with_scorecard.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
var k=document.getElementById('k');
[[SUM.not_ready_flagged+' of '+SUM.not_ready,'not ready, flagged'],[SUM.ready_flagged+' of '+SUM.ready,'ready, flagged'],[SUM.tier1_ready+' of '+SUM.tier1,'tier 1 with a tested way back'],[SUM.missed+' of '+SUM.not_ready,'not ready, scored READY']].forEach(function(x){var d=el('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function fill(id,values){var s=document.getElementById(id);values.forEach(function(v){s.appendChild(el('option',v));});}
fill('st',Object.keys(SUM.by_status).sort());
fill('dm',Array.from(new Set(ROWS.map(function(r){return r.domain;}))).sort());
function draw(){
  var f={status:document.getElementById('st').value,tier:document.getElementById('ti').value,domain:document.getElementById('dm').value,truth:document.getElementById('tr').value};
  var b=document.getElementById('b');while(b.firstChild)b.removeChild(b.firstChild);var c=0;
  ROWS.forEach(function(r){
    for(var key in f){if(f[key]&&r[key]!==f[key])return;}
    c++;var tr=el('tr');
    [[r.service_id,'n'],[r.name,'n'],[r.domain,'n'],[r.tier,'n'],[r.status,'n '+r.status],[r.reason,'r'],[r.truth,'n']].forEach(function(v){tr.appendChild(el('td',v[0],v[1]));});
    b.appendChild(tr);});
  document.getElementById('n').textContent=c+' shown';}
['st','ti','dm','tr'].forEach(function(id){document.getElementById(id).onchange=draw;});
draw();
</script></body></html>
"""


def main() -> None:
    with open(os.path.join(HERE, "out", "step_04_scorecard.csv"), newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)

    def embed(obj) -> str:
        return json.dumps(obj, sort_keys=True).replace("<", "\\u003c")

    with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
        fh.write(PAGE.replace("__ROWS__", embed(rows)).replace("__SUM__", embed(summary)))
    print("Wrote demo.html")


if __name__ == "__main__":
    main()
