"""Build demo.html from out/step_04_results.csv and out/step_04_summary.json. Run step_04_chain_and_anchor.py first.
Run (from src/):  python3 _build_demo.py"""
import csv
import json
import os

from common import OPS, OUT_DIR, HERE

with open(os.path.join(OUT_DIR, "step_04_results.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(OUT_DIR, "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
ops = {name: (OPS[name].__doc__ or "").strip() for name in sorted({r["op"] for r in rows})}


def embed(obj) -> str:
    """JSON for a script block: a closing tag inside a string must not end the block."""
    return json.dumps(obj, sort_keys=True).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>audit-chain: __PLANTED__ planted edits, four checks</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--good:#1e6b3a;--bad:#b3261e}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--good:#7fd49a;--bad:#ff8a80}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:24px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
td.good{color:var(--good);font-weight:600}td.bad{color:var(--bad);font-weight:600}
.wrap{overflow-x:auto}dl{margin:0}dt{font-weight:600;margin-top:8px}dd{margin:0;color:var(--mut)}
</style></head><body><main>
<h1>audit-chain: __PLANTED__ planted edits, four checks</h1>
<p class="s">Synthetic data. Each row is one edit made to a copy of a __EVENTS__-event log. The truth is what was done to the file; each column is what a check printed. Green means the check gave the right answer for that row (it flagged a tampered log, or passed a harmless change). Red means it did not.</p>
<div class="k" id="k"></div>
<div><label>Planted edit <select id="o"><option value="">all</option></select></label>
<label>Region <select id="r"><option value="">all</option><option value="anchored">anchored (event __ANCHOR__ or earlier)</option><option value="open">open tail (after the anchor)</option><option value="-">not applicable</option></select></label>
<label>Truth <select id="t"><option value="">all</option><option value="tampered">tampered</option><option value="benign">benign</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Edit</th><th>Planted</th><th>Region</th><th>Truth</th><th>No check</th><th>Record check</th><th>Bare chain</th><th>Chain and anchor</th><th>First problem</th></tr></thead><tbody id="b"></tbody></table></div>
<h2>What each planted edit does</h2>
<dl id="g"></dl>
<p class="s">Known misses: everything written after the anchor is covered only by the chain, so a rewrite of the open tail, a cut that keeps all anchored events, a forged append and an edit to the last event with its own hash recomputed all pass. Source: <code>python3 step_04_chain_and_anchor.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__, OPS=__OPS__;
function el(tag,text,cls){var e=document.createElement(tag);e.textContent=text;if(cls){e.className=cls;}return e;}
var k=document.getElementById('k');
[[SUM.flagged.anchored+' of '+SUM.tampered,'tampered, chain and anchor'],[SUM.flagged.chain+' of '+SUM.tampered,'tampered, bare chain'],[SUM.flagged.records+' of '+SUM.tampered,'tampered, record check'],[SUM.false_alarms.anchored+' of '+SUM.benign,'harmless flagged, chain and anchor'],[SUM.open_tail[0]+' of '+SUM.open_tail[1],'open-tail edits flagged']].forEach(function(x){var d=document.createElement('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var sel=document.getElementById('o');Object.keys(OPS).forEach(function(o){var op=el('option',o);op.value=o;sel.appendChild(op);});
var g=document.getElementById('g');Object.keys(OPS).forEach(function(o){g.appendChild(el('dt',o));g.appendChild(el('dd',OPS[o]));});
function draw(){var o=sel.value,r=document.getElementById('r').value,t=document.getElementById('t').value,b=document.getElementById('b');
while(b.firstChild){b.removeChild(b.firstChild);}var c=0;
ROWS.forEach(function(x){if((o&&x.op!==o)||(r&&x.region!==r)||(t&&x.truth!==t)){return;}c++;var tr=document.createElement('tr');
[x.tamper_id,x.op,x.region,x.truth].forEach(function(v){tr.appendChild(el('td',v));});
['none','records','chain','anchored'].forEach(function(name){var right=(x.truth==='tampered')===(x[name]==='flagged');tr.appendChild(el('td',x[name],right?'good':'bad'));});
tr.appendChild(el('td',x.first_problem||'-'));b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
['o','r','t'].forEach(function(id){document.getElementById(id).onchange=draw;});draw();
</script></body></html>
"""
page = (page.replace("__PLANTED__", str(summary["planted"])).replace("__EVENTS__", str(summary["events"]))
        .replace("__ANCHOR__", str(summary["anchor_seq"])).replace("__ROWS__", embed(rows))
        .replace("__SUM__", embed(summary)).replace("__OPS__", embed(ops)))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
