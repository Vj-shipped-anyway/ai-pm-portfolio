"""Build demo.html from the files in out/. Run step_04_with_memo_tieout.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
with open(os.path.join(OUT, "step_04_results.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(OUT, "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
with open(os.path.join(OUT, "demo_run.txt"), encoding="utf-8") as fh:
    demo_run = fh.read()


def embed(obj):
    return json.dumps(obj).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Memo Tieout: 28 credit memos against their spreads</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--bad:#b3261e;--warn:#8a5a00;--good:#1e6b3a;--code:#f3f4f6}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--bad:#ff8a80;--warn:#ffc266;--good:#7fd49a;--code:#1d2026}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:22px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
pre{background:var(--code);border:1px solid var(--line);border-radius:8px;padding:10px 12px;overflow-x:auto;font-size:13px;line-height:1.45;margin:0}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
.wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
td:nth-child(-n+6){white-space:nowrap}
.flag{color:var(--bad);font-weight:600}.pass{color:var(--good);font-weight:600}.warn{color:var(--warn);font-weight:600}
</style></head><body><main>
<h1>Memo Tieout: 28 credit memos against their spreads</h1>
<p class="s">Synthetic data. Each row is one figure in a memo. The planted kind is how I built the figure; the status is what the tool printed.</p>
<div class="k" id="k"></div>
<h2>One memo, run on the command line</h2>
<pre id="run"></pre>
<h2>All 308 figures</h2>
<div><label>Planted kind <select id="kind"></select></label>
<label>Tool status <select id="status"></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Memo</th><th>Line</th><th>Figure</th><th>Planted kind</th><th>Truth</th><th>Status</th><th>Why</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: prose_tag_mismatch (the number agrees with its mark, the sentence names another line) and unparsed_form (a figure in words or with a USD prefix is never read). Source: <code>python3 step_04_with_memo_tieout.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__, RUN=__RUN__;
function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
document.getElementById('run').textContent=RUN;
var k=document.getElementById('k');
[[SUM.caught+' of '+SUM.wrong,'wrong figures caught'],[SUM.false_alarms+' of '+SUM.fine,'fine figures flagged'],[SUM.to_open+' of '+SUM.figures,'figures to open'],[SUM.missed+'','wrong figures still passing']].forEach(function(x){var d=el('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function fill(id,key){var s=document.getElementById(id),seen={};s.appendChild(el('option','all'));s.firstChild.value='';
ROWS.forEach(function(r){if(!seen[r[key]]){seen[r[key]]=1;var o=el('option',r[key]);o.value=r[key];s.appendChild(o);}});}
fill('kind','kind');fill('status','status');
function draw(){var kd=document.getElementById('kind').value,st=document.getElementById('status').value,b=document.getElementById('b');
while(b.firstChild)b.removeChild(b.firstChild);var c=0;
ROWS.forEach(function(r){if((kd&&r.kind!==kd)||(st&&r.status!==st))return;c++;var tr=el('tr');
[r.memo_id,r.line+':'+r.col,r.text,r.kind,r.expected,r.status,r.why].forEach(function(v,i){var td=el('td',v);
if(i===4)td.className=v==='flag'?'warn':'';if(i===5&&v!=='tied'&&v!=='term')td.className='flag';tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('kind').onchange=draw;document.getElementById('status').onchange=draw;draw();
</script></body></html>
"""
page = page.replace("__ROWS__", embed(rows)).replace("__SUM__", embed(summary)).replace("__RUN__", embed(demo_run))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
