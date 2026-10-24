"""Build demo.html from the step 4 output. Run step_04_with_gate.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    with open(os.path.join(HERE, "out", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


matches = [{k: m[k] for k in ("match_id", "rule", "status", "a_ids", "b_ids", "amount", "currency", "evidence", "approver", "gate_why")} for m in read("step_04_matches.csv")]
open_items = read("step_04_unmatched.csv")
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)

page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>recon-agent: every match shows its evidence</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--ok:#1e6b3a;--wait:#8a5a00;--bad:#b3261e;--sel:#eef3fb}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--ok:#7fd49a;--wait:#ffc266;--bad:#ff8a80;--sel:#1d2733}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
button,select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:5px 10px;font:inherit}
button.on{background:var(--sel);font-weight:600}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 8px}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
tr.row{cursor:pointer}tr.row:hover{background:var(--sel)}tr.ev td{color:var(--mut);background:var(--sel)}
.posted_auto,.posted_approved{color:var(--ok);font-weight:600}.pending,.awaiting_approval{color:var(--wait);font-weight:600}
.rejected,.blocked,.rejected_by_reviewer{color:var(--bad);font-weight:600}
.wrap{overflow-x:auto}
</style></head><body><main>
<h1>recon-agent: every match shows its evidence</h1>
<p class="s">Synthetic data. Two ledgers for one month, matched by five rules. Click a match to see the facts it rests on. The approver in this run is a script, not a person.</p>
<div class="k" id="k"></div>
<div class="bar"><button id="tm" class="on">Matches</button><button id="to">Open lines</button>
<label>Filter <select id="f"></select></label><span id="n" class="s"></span></div>
<div class="wrap"><table><thead id="h"></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: true matches the five rules never propose (a split deposit with no batch id, a date gap beyond the window, a reference with two wrong characters, an abbreviation the table does not know), and six distinct invoices one edit from a real one that the scripted approver passed. Source: <code>python3 step_04_with_gate.py</code>.</p>
</main>
<script>
var M=__MATCHES__, O=__OPEN__, S=__SUMMARY__, view='m';
function el(t,txt,cls){var e=document.createElement(t);if(txt!==undefined)e.textContent=txt;if(cls)e.className=cls;return e;}
var k=document.getElementById('k');
[[S.posted_auto+' of '+S.proposals,'matches posted on their own'],[S.posted_approved+' of '+S.need_person,'posted on approval'],[S.wrong_auto+' / '+S.wrong_approved,'wrong: own / approved'],[S.to_read+' of '+S.lines,'lines a person looks at']].forEach(function(x){var d=el('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function opts(vals){var f=document.getElementById('f');f.textContent='';[''].concat(vals).forEach(function(v){var o=el('option',v||'all');o.value=v;f.appendChild(o);});}
function uniq(a){return a.filter(function(v,i){return a.indexOf(v)===i;}).sort();}
function head(cols){var h=document.getElementById('h');h.textContent='';var tr=el('tr');cols.forEach(function(c){tr.appendChild(el('th',c));});h.appendChild(tr);}
function draw(){
  var f=document.getElementById('f').value,b=document.getElementById('b'),c=0;b.textContent='';
  if(view==='m'){
    M.forEach(function(r){if(f&&r.status!==f)return;c++;
      var tr=el('tr',undefined,'row'),ev=el('tr',undefined,'ev');ev.hidden=true;
      [r.match_id,r.rule,r.a_ids,r.b_ids.split('+').join(', '),r.amount+' '+r.currency,r.status,r.approver].forEach(function(v,i){tr.appendChild(el('td',v,i===5?r.status:''));});
      var td=el('td',r.evidence+(r.gate_why?'  |  needs a person: '+r.gate_why:''));td.colSpan=7;ev.appendChild(td);
      tr.onclick=function(){ev.hidden=!ev.hidden;};b.appendChild(tr);b.appendChild(ev);});
  }else{
    O.forEach(function(r){if(f&&r.reason!==f)return;c++;var tr=el('tr');
      [r.ledger,r.id,r.date,r.amount+' '+r.currency,r.counterparty,r.reason,r.detail].forEach(function(v,i){tr.appendChild(el('td',v,i===5?r.reason:''));});b.appendChild(tr);});
  }
  document.getElementById('n').textContent=c+' shown';
}
function show(v){view=v;document.getElementById('tm').className=v==='m'?'on':'';document.getElementById('to').className=v==='o'?'on':'';
  if(v==='m'){head(['Match','Rule','Bank line','Book lines','Amount','Status','Approver']);opts(uniq(M.map(function(r){return r.status;})));}
  else{head(['Ledger','Line','Date','Amount','Counterparty','Reason','Detail']);opts(uniq(O.map(function(r){return r.reason;})));}
  draw();}
document.getElementById('tm').onclick=function(){show('m');};document.getElementById('to').onclick=function(){show('o');};
document.getElementById('f').onchange=draw;show('m');
</script></body></html>
"""
def safe(obj):
    return json.dumps(obj).replace("</", "<\\/")


page = page.replace("__MATCHES__", safe(matches)).replace("__OPEN__", safe(open_items)).replace("__SUMMARY__", safe(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
