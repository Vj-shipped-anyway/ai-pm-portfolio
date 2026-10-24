"""Build demo.html from src/out/. Run step_04_with_check.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    with open(os.path.join(HERE, "out", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


builds = read("step_04_builds.csv")
static = read("step_04_static.csv")
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>iso20022-map-check: ten converter builds, one check</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--bad:#b3261e;--warn:#8a5a00;--ok:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--bad:#ff8a80;--warn:#ffc266;--ok:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:24px 0 6px}p.s{color:var(--mut);margin:0 0 12px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px;min-width:640px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.found{color:var(--ok);font-weight:600}.missed{color:var(--bad);font-weight:600}.clean{color:var(--mut)}
.wrap{overflow-x:auto}code{font-size:13px}
</style></head><body><main>
<h1>iso20022-map-check: ten converter builds, one check</h1>
<p class="s">Synthetic data. Each row is a converter build that turns legacy payment messages into ISO 20022 style elements. Eight carry one planted defect. The result is what the check printed; the planted defect is what the build was told to do.</p>
<div class="k" id="k"></div>
<h2>Converter builds</h2>
<div><label>Result <select id="f"><option value="">all</option><option value="found">found</option><option value="missed">missed</option><option value="clean">no defect planted</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Build</th><th>Planted defect</th><th>Element</th><th>Typical messages find it</th><th>Probes add it</th><th>Result</th><th>What the check printed</th></tr></thead><tbody id="b"></tbody></table></div>
<h2>Mapping findings, no messages needed</h2>
<div class="wrap"><table><thead><tr><th>Kind</th><th>Element or field</th><th>Detail</th></tr></thead><tbody id="s"></tbody></table></div>
<p class="s">Known miss: build B10 drops the beneficiary account only when TYP is 16 and CHGS is S. No message carries that pair of codes, so nothing fires. Source: <code>python3 step_04_with_check.py</code>.</p>
</main>
<script>
var BUILDS=__BUILDS__, STATIC=__STATIC__, SUM=__SUM__;
function add(parent,tag,text,cls){var e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;parent.appendChild(e);return e;}
var k=document.getElementById('k');
[[SUM.mapping_defects_found+' of '+SUM.mapping_defects,'mapping defects found'],
 [SUM.builds_found+' of '+SUM.builds_planted,'defective builds found'],
 [SUM.builds_found_typical+' of '+SUM.builds_planted,'found by typical messages alone'],
 [SUM.harmless_rows_flagged+' of '+SUM.harmless_rows,'harmless rows flagged']].forEach(function(x){var d=add(k,'div','');add(d,'b',x[0]);d.appendChild(document.createTextNode(x[1]));});
function result(r){if(r.defect==='none')return 'clean';return r.typical_finds==='yes'||r.probes_add==='yes'?'found':'missed';}
function draw(){var f=document.getElementById('f').value,b=document.getElementById('b'),c=0;b.textContent='';
BUILDS.forEach(function(r){var res=result(r);if(f&&res!==f)return;c++;var tr=document.createElement('tr');
[[r.build],[r.defect==='none'?'none ('+(r.benign||'no variation')+')':r.defect],[r.element||'-'],[r.defect==='none'?'-':r.typical_finds],[r.defect==='none'?'-':r.probes_add],[res,res],[r.findings]].forEach(function(v){add(tr,'td',v[0],v[1]);});
b.appendChild(tr);});document.getElementById('n').textContent=c+' shown';}
document.getElementById('f').onchange=draw;draw();
var s=document.getElementById('s');STATIC.forEach(function(r){var tr=document.createElement('tr');add(tr,'td',r.kind);add(tr,'td',r.subject);add(tr,'td',r.detail);s.appendChild(tr);});
</script></body></html>
"""
page = (page.replace("__BUILDS__", json.dumps(builds)).replace("__STATIC__", json.dumps(static)).replace("__SUM__", json.dumps(summary)))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
