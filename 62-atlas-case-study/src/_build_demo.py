"""Build demo.html from out/step_04_decisions.csv, out/step_04_summary.json and out/step_04_example.yaml.
Run step_04_with_case_study_tool.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
with open(os.path.join(OUT, "step_04_decisions.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(OUT, "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
with open(os.path.join(OUT, "step_04_example.yaml"), encoding="utf-8") as fh:
    example = fh.read()

page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ATLAS case study from a trace: 60 runs, one tool</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--yes:#1e6b3a;--no:#8a5a00;--code:#f4f5f7}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--yes:#7fd49a;--no:#ffc266;--code:#1d2026}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:24px 0 8px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:560px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.yes{color:var(--yes);font-weight:600}.no{color:var(--no);font-weight:600}
.wrap{overflow-x:auto}pre{background:var(--code);border:1px solid var(--line);border-radius:8px;padding:12px;overflow-x:auto;font-size:13px;white-space:pre-wrap;word-break:break-word}
</style></head><body><main>
<h1>ATLAS case study from a trace: 60 runs, one tool</h1>
<p class="s">Synthetic data. Each row is an agent run that an alert flagged. The planted kind and whether it was a failure are what I generated; the drafted column is what the tool printed. The tool never reads the ticket note.</p>
<div class="k" id="k"></div>
<div><label>Failure <select id="f"><option value="">all</option><option>yes</option><option>no</option></select></label>
<label>Drafted <select id="d"><option value="">all</option><option>yes</option><option>no</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Run</th><th>Planted kind</th><th>Failure</th><th>Drafted</th><th>Techniques</th><th>Steps</th><th>Calls</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: failures with no draft are the short_storm and alternating_loop rows. Source: <code>python3 step_04_with_case_study_tool.py</code>.</p>
<h2>One draft, as the tool writes it</h2>
<p class="s">From the bundled example run. The actor, reporter and references lines are left for a person.</p>
<pre id="y"></pre>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__, EXAMPLE=__EXAMPLE__;
var k=document.getElementById('k');
[[SUM.failures_drafted+' of '+SUM.failures,'failures drafted'],[SUM.harmless_drafted+' of '+SUM.harmless,'harmless drafted'],[SUM.techniques_exact+' of '+SUM.drafted,'technique sets match'],[SUM.leaks_planted+' of '+SUM.drafted,'drafts with a planted string']].forEach(function(x){var d=document.createElement('div');var b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
document.getElementById('y').textContent=EXAMPLE;
function draw(){var f=document.getElementById('f').value,d=document.getElementById('d').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((f&&r.failure!==f)||(d&&r.drafted!==d))return;c++;var tr=document.createElement('tr');
[r.run_id,r.scenario,r.failure,r.drafted,r.techniques,r.steps,r.calls].forEach(function(v,i){var td=document.createElement('td');td.textContent=v;if(i===2||i===3)td.className=v;tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('f').onchange=draw;document.getElementById('d').onchange=draw;draw();
</script></body></html>
"""


def js(obj) -> str:
    return json.dumps(obj).replace("</", "<\\/")


page = page.replace("__ROWS__", js(rows)).replace("__SUM__", js(summary)).replace("__EXAMPLE__", js(example))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
