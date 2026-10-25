"""Build demo.html from src/out/. Run step_04_with_fairlens.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_cases.csv"), encoding="utf-8", newline="") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
with open(os.path.join(HERE, "out", "step_04_example.json"), encoding="utf-8") as fh:
    example = json.load(fh)


def embed(obj) -> str:
    return json.dumps(obj).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FairLens CLI: six tests, 36 portfolios</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--fail:#b3261e;--review:#8a5a00;--pass:#1e6b3a;--none:#5b6470}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--fail:#ff8a80;--review:#ffc266;--pass:#7fd49a;--none:#9aa3ad}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:28px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:140px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.FAIL{color:var(--fail);font-weight:600}.REVIEW{color:var(--review);font-weight:600}.PASS{color:var(--pass);font-weight:600}.NONE{color:var(--none)}
.wrap{overflow-x:auto}table.w{min-width:640px}
</style></head><body><main>
<h1>FairLens CLI: six tests, 36 portfolios</h1>
<p class="s">Synthetic data. Each row is a scorecard portfolio with a planted mechanism. The pack ran on each one; the verdicts are what it printed.</p>
<div class="k" id="k"></div>
<h2>One portfolio, six tests</h2>
<p class="s" id="exs"></p>
<div class="wrap"><table class="w"><thead><tr><th>Test</th><th>Verdict</th><th>Numbers</th></tr></thead><tbody id="ex"></tbody></table></div>
<h2>All portfolios</h2>
<div><label>Mechanism <select id="m"><option value="">all</option></select></label>
<label>Overall <select id="o"><option value="">all</option><option>FAIL</option><option>REVIEW</option><option>PASS</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table class="w"><thead><tr><th>Portfolio</th><th>Planted mechanism</th><th>Planted proxy</th><th>Point AIR</th><th>T1</th><th>T2</th><th>T3</th><th>T4</th><th>T5</th><th>T6</th><th>Overall</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: T4 does not mark FAIL on the two_proxies rows (it is pointed at one column), on the quiet_proxy rows (a proxy worth a few points) or on one weak proxy_gap row. No portfolio reads PASS overall. Source: <code>python3 step_04_with_fairlens.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__, EX=__EX__;
function cell(tr,text,cls){var td=document.createElement('td');td.textContent=text;if(cls)td.className=cls;tr.appendChild(td);}
var k=document.getElementById('k');
[[SUM.found_by_t4+' of '+SUM.planted,'planted proxies marked FAIL by the ablation'],[SUM.false_t4+' of '+SUM.others,'other portfolios marked FAIL by the ablation'],[SUM.t5_pass_t4_fail+' of '+SUM.t4_fail,'ablation FAILs where the reason pairs passed'],[SUM.noise_point_air_flagged+' of '+SUM.noise,'identical-group portfolios under 0.80 on the point estimate']].forEach(function(x){var d=document.createElement('div');var b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
document.getElementById('exs').textContent='Portfolio '+EX.case_id+', the one behind the command-line demo. Overall: '+EX.overall+'.';
var ex=document.getElementById('ex');
EX.tests.forEach(function(t){var tr=document.createElement('tr');cell(tr,t.id+' '+t.name);cell(tr,t.verdict,t.verdict.replace(' ','').toUpperCase()==='NOTRUN'?'NONE':t.verdict);cell(tr,t.numbers);ex.appendChild(tr);});
var ms=[];ROWS.forEach(function(r){if(ms.indexOf(r.mechanism)<0)ms.push(r.mechanism);});
var msel=document.getElementById('m');ms.forEach(function(m){var o=document.createElement('option');o.textContent=m;o.value=m;msel.appendChild(o);});
function draw(){var m=msel.value,o=document.getElementById('o').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((m&&r.mechanism!==m)||(o&&r.overall!==o))return;c++;var tr=document.createElement('tr');
cell(tr,r.case_id);cell(tr,r.mechanism);cell(tr,r.proxy_planted==='1'?'yes':'no');cell(tr,r.point_air);
['T1','T2','T3','T4','T5','T6'].forEach(function(t){cell(tr,r[t],r[t]);});cell(tr,r.overall,r.overall);b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
msel.onchange=draw;document.getElementById('o').onchange=draw;draw();
</script></body></html>
"""
page = page.replace("__ROWS__", embed(rows)).replace("__SUM__", embed(summary)).replace("__EX__", embed(example))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
