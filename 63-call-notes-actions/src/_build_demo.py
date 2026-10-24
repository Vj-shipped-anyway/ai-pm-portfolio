"""Build demo.html from out/step_04_*.{csv,json} and data/notes.csv. Run step_04_with_grounding_check.py first.
Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")


def read(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


rows = read(os.path.join(HERE, "out", "step_04_decisions.csv"))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
notes = {}
for r in read(os.path.join(DATA, "notes.csv")):
    notes.setdefault(r["note_id"], []).append(r["text"])


def js(obj):
    return json.dumps(obj).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Call Notes Actions: __N__ candidate actions, one grounding check</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--reject:#b3261e;--review:#8a5a00;--accept:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--reject:#ff8a80;--review:#ffc266;--accept:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
.f{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
label{color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
ol#note{margin:12px 0;padding:8px 12px 8px 36px;border:1px solid var(--line);border-radius:8px}ol#note:empty{display:none}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:860px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.REJECT{color:var(--reject);font-weight:600}.REVIEW{color:var(--review);font-weight:600}.ACCEPT{color:var(--accept);font-weight:600}
.wrap{overflow-x:auto}td.nw{white-space:nowrap}
</style></head><body><main>
<h1>Call Notes Actions: __N__ candidate actions, one grounding check</h1>
<p class="s">Synthetic data. A stub extractor proposed an action from each call note and cited a sentence. The planted column is what the generator knew; the decision is what the check printed.</p>
<div class="k" id="k"></div>
<div class="f"><label>Decision <select id="d"><option value="">all</option><option>ACCEPT</option><option>REVIEW</option><option>REJECT</option></select></label>
<label>Planted cause <select id="t"><option value="">all</option></select></label>
<label>Note <select id="o"><option value="">all</option></select></label>
<span id="n" class="s"></span></div>
<ol id="note"></ol>
<div class="wrap"><table><thead><tr><th>Cand</th><th>Note</th><th>Action</th><th>Owner</th><th>Due</th><th>Subject</th><th>Cites</th><th>Decision</th><th>Why</th><th>Planted</th><th>Cited text</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: clause_swap (a date or document taken from the other clause), hedged_soft ("I will try to") and negated_phrasal ("hold off") pass every rule. Source: <code>python3 step_04_with_grounding_check.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__, NOTES=__NOTES__;
function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
var k=document.getElementById('k');
[[SUM.ungrounded_written+' of '+SUM.ungrounded,'ungrounded written'],[SUM.grounded_written+' of '+SUM.grounded,'grounded written'],[SUM.to_read+' of '+SUM.candidates,'held for a person'],[SUM.ungrounded_rejected+' of '+SUM.candidates,'rejected']].forEach(function(x){var d=el('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var causes={};ROWS.forEach(function(r){causes[r.planted]=1;});
Object.keys(causes).sort().forEach(function(c){var o=el('option',c);o.value=c;document.getElementById('t').appendChild(o);});
Object.keys(NOTES).sort().forEach(function(c){var o=el('option',c);o.value=c;document.getElementById('o').appendChild(o);});
function draw(){
 var d=document.getElementById('d').value,t=document.getElementById('t').value,o=document.getElementById('o').value,b=document.getElementById('b'),ol=document.getElementById('note');
 b.textContent='';ol.textContent='';
 if(o){NOTES[o].forEach(function(s){ol.appendChild(el('li',s));});}
 var c=0;
 ROWS.forEach(function(r){
  if((d&&r.decision!==d)||(t&&r.planted!==t)||(o&&r.note_id!==o))return;c++;
  var tr=document.createElement('tr');
  [r.cand_id,r.note_id,r.action_type,r.owner,r.due,r.subject+(r.amount?' '+r.amount:''),'S'+r.cite_sent_id,r.decision,r.reasons,r.planted,r.quote].forEach(function(v,i){
   var td=el('td',v);if(i===7)td.className=v;if(i<8&&i!==5)td.className=(td.className+' nw').trim();tr.appendChild(td);});
  b.appendChild(tr);});
 document.getElementById('n').textContent=c+' shown';}
['d','t','o'].forEach(function(id){document.getElementById(id).onchange=draw;});draw();
</script></body></html>
"""
page = (page.replace("__ROWS__", js(rows)).replace("__SUM__", js(summary)).replace("__NOTES__", js(notes))
        .replace("__N__", str(summary["candidates"])))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
