"""Build demo.html from out/step_03_ladder.json, out/step_04_sentences.csv and out/step_04_summary.json.
Run steps 3 and 4 first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load_json(name):
    with open(os.path.join(HERE, "out", name), encoding="utf-8") as fh:
        return json.load(fh)


with open(os.path.join(HERE, "out", "step_04_sentences.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
summary, ladder = load_json("step_04_summary.json"), load_json("step_03_ladder.json")


def embed(obj):
    return json.dumps(obj).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Narrative Trace: __N__ sentences, one citation check</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--bad:#b3261e;--mid:#8a5a00;--good:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--bad:#ff8a80;--mid:#ffc266;--good:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:24px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.traced{color:var(--good);font-weight:600}.unchecked{color:var(--mid);font-weight:600}.bad{color:var(--bad);font-weight:600}
.wrap{overflow-x:auto}table.t{min-width:760px}td.n{white-space:nowrap}
</style></head><body><main>
<h1>Narrative Trace: __N__ sentences, one citation check</h1>
<p class="s">Synthetic data. Each row is one sentence of a made-up case narrative. The planted column is what I put in; the verdict is what the tool printed.</p>
<div class="k" id="k"></div>
<h2>What each added check buys</h2>
<div class="wrap"><table id="l"><thead><tr><th>Version</th><th>Defects caught</th><th>Fine sentences flagged</th></tr></thead><tbody></tbody></table></div>
<h2>Every sentence</h2>
<div><label>Verdict <select id="v"><option value="">all</option></select></label>
<label>Planted <select id="p"><option value="">all</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table class="t"><thead><tr><th>Case</th><th>No.</th><th>Planted</th><th>Verdict</th><th>Findings</th><th>Sentence</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: laundered (cites a real record, says something no field can confirm) and mixed_record (figures right, bound to the wrong record) pass by default. The ok_other_date rows are false alarms. Source: <code>python3 step_04_with_trace.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__, LAD=__LAD__;
function el(tag,text,cls){var e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e;}
var k=document.getElementById('k');
[[SUM.caught+' of '+SUM.defects,'defects flagged'],[SUM.false_alarms+' of '+SUM.fine,'fine sentences flagged'],[SUM.to_read+' of '+SUM.sentences,'to read'],[SUM.missed,'defects that pass']].forEach(function(x){var d=document.createElement('div');d.appendChild(el('b',String(x[0])));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var lb=document.querySelector('#l tbody');
LAD.forEach(function(r){var tr=document.createElement('tr');[r.version+'  '+r.name,r.caught+' of '+r.defects,r.false_alarms+' of '+r.fine].forEach(function(v){tr.appendChild(el('td',v));});lb.appendChild(tr);});
function fill(id,key){var s=document.getElementById(id),seen={};ROWS.forEach(function(r){seen[r[key]]=1;});Object.keys(seen).sort().forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v;s.appendChild(o);});}
fill('v','status');fill('p','kind');
function draw(){var v=document.getElementById('v').value,p=document.getElementById('p').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((v&&r.status!==v)||(p&&r.kind!==p))return;c++;var tr=document.createElement('tr');
[r.case_id,r.sent_no,r.kind,r.status,r.findings,r.text].forEach(function(x,i){var td=el('td',x,i===3?(r.status==='traced'?'traced':r.status==='unchecked'?'unchecked':'bad'):(i<4?'n':''));tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('v').onchange=draw;document.getElementById('p').onchange=draw;draw();
</script></body></html>
"""
page = (page.replace("__N__", str(summary["sentences"])).replace("__ROWS__", embed(rows))
        .replace("__SUM__", embed(summary)).replace("__LAD__", embed(ladder)))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
