"""Build demo.html from out/step_04_results.json and out/step_03_hidden.json. Run steps 3 and 4 first.
Run (from src/):  python3 _build_demo.py"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    with open(os.path.join(HERE, "out", name), encoding="utf-8") as fh:
        return json.load(fh)


results, hidden = load("step_04_results.json"), load("step_03_hidden.json")
slim = {"development": results["development"], "holdout": results["holdout"], "mixes": hidden["mixes"], "extractors": {}}
for name, r in results["extractors"].items():
    slim["extractors"][name] = {"layouts": {n: {k: s[k] for k in ("docs", "values", "correct", "docs_all_right", "errors", "fields")}
                                            for n, s in r["layouts"].items()}}
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spread Extraction Eval: 120 statements, six layouts</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--bar:#2f6fb0;--bad:#b3261e;--ok:#1e6b3a;--chip:#f2f4f7}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--bar:#6aa6e8;--bad:#ff8a80;--ok:#7fd49a;--chip:#1e2228}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:24px 0 6px}p.s{color:var(--mut);margin:0 0 12px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
label{margin-right:14px;color:var(--mut);display:inline-block;margin-bottom:6px}
select,input{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;font:inherit}
input{width:64px}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:middle}
.wrap{overflow-x:auto}table{min-width:560px}
.bar{display:inline-block;height:10px;background:var(--bar);border-radius:3px;vertical-align:middle;margin-right:6px}
.PASS{color:var(--ok);font-weight:600}.FAIL{color:var(--bad);font-weight:600}
button.row{background:none;border:0;color:var(--fg);font:inherit;text-decoration:underline;cursor:pointer;padding:0}
.chip{display:inline-block;background:var(--chip);border-radius:10px;padding:1px 8px;margin:2px 4px 2px 0;font-size:13px}
ul{margin:6px 0;padding-left:20px}
</style></head><body><main>
<h1>Spread Extraction Eval: 120 statements, six layouts</h1>
<p class="s">Synthetic statements. Each row is one layout; every value is scored against the truth the generator planted. The two extractors are rule-based stand-ins, not a model, and one author wrote the data and the rules, so read the numbers as a ceiling.</p>
<div><label>Extractor <select id="e"></select></label>
<label>Layouts <select id="sc"><option value="dev">development layouts</option><option value="all">all layouts</option></select></label>
<label>Floor % <input id="fl" type="number" min="0" max="100" step="0.5" value="95"></label>
<label>Max gap, points <input id="gp" type="number" min="0" max="100" step="0.5" value="3"></label></div>
<div class="k" id="k"></div>
<ul id="why"></ul>
<div class="wrap"><table><thead><tr><th>Layout</th><th>Split</th><th>Docs</th><th>Field accuracy</th><th>Documents all right</th></tr></thead><tbody id="b"></tbody></table></div>
<h2 id="dh"></h2><div id="dc"></div>
<div class="wrap"><table><thead><tr><th>Field</th><th>Values</th><th>Accuracy</th></tr></thead><tbody id="f"></tbody></table></div>
<h2>The same extractor under different mixes of incoming layouts</h2>
<p class="s">Pooled accuracy of alias_aware when the share of the held-out layout changes. The shares are assumptions.</p>
<div class="wrap"><table><thead><tr><th>Mix</th><th>Pooled accuracy</th></tr></thead><tbody id="m"></tbody></table></div>
<p class="s">Known limit: the tie-out check (do the figures obey the accounting identities) passes a statement read in the wrong scale with its columns swapped. Only a labeled sample sees it. Source: <code>python3 step_04_layout_scorer.py</code>.</p>
</main>
<script>
var D=__DATA__;
var $=function(i){return document.getElementById(i)};
var sel=null;
function pct(c,n){return n?Math.round(1000*c/n)/10:0}
function el(tag,text,cls){var x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x}
function cell(tr,v,cls){tr.appendChild(el('td',v,cls))}
function names(){return $('sc').value==='dev'?D.development:D.development.concat(D.holdout).sort()}
function gate(L,list,floor,gap){
  var acc={},gated=list.filter(function(n){return L[n].docs>=10});
  gated.forEach(function(n){acc[n]=pct(L[n].correct,L[n].values)});
  var best=gated.slice().sort(function(a,b){return acc[b]-acc[a]||(a<b?-1:1)})[0],why=[];
  gated.slice().sort(function(a,b){return acc[a]-acc[b]||(a<b?-1:1)}).forEach(function(n){
    var p=[];if(acc[n]<floor)p.push('below the floor of '+floor.toFixed(1)+'%');
    if(Math.round((acc[best]-acc[n])*10)/10>gap)p.push((acc[best]-acc[n]).toFixed(1)+' points below '+best);
    if(p.length)why.push(n+': '+acc[n].toFixed(1)+'% is '+p.join(' and '))});
  return {verdict:why.length?'FAIL':'PASS',why:why,acc:acc,best:best}}
function draw(){
  var L=D.extractors[$('e').value].layouts,list=names(),floor=parseFloat($('fl').value)||0,gap=parseFloat($('gp').value)||0;
  var g=gate(L,list,floor,gap),c=0,v=0;list.forEach(function(n){c+=L[n].correct;v+=L[n].values});
  var worst=list.slice().sort(function(a,b){return g.acc[a]-g.acc[b]})[0];
  var k=$('k');k.textContent='';
  [[pct(c,v).toFixed(1)+'%','pooled accuracy'],[g.acc[worst].toFixed(1)+'%','worst layout ('+worst+')'],[g.verdict,'gate']].forEach(function(x,i){
    var d=el('div');d.appendChild(el('b',x[0],i===2?g.verdict:''));d.appendChild(document.createTextNode(x[1]));k.appendChild(d)});
  var w=$('why');w.textContent='';g.why.forEach(function(t){w.appendChild(el('li',t))});
  var b=$('b');b.textContent='';
  list.slice().sort(function(a,b2){return g.acc[b2]-g.acc[a]||(a<b2?-1:1)}).forEach(function(n){
    var tr=el('tr'),a=g.acc[n],td=el('td'),bt=el('button',n,'row');bt.onclick=function(){sel=n;detail()};td.appendChild(bt);tr.appendChild(td);
    cell(tr,D.holdout.indexOf(n)>=0?'held out':'development');cell(tr,L[n].docs);
    var t=el('td'),bar=el('span','','bar');bar.style.width=Math.round(a*1.2)+'px';t.appendChild(bar);t.appendChild(document.createTextNode(a.toFixed(1)+'%'));tr.appendChild(t);
    cell(tr,L[n].docs_all_right+' of '+L[n].docs);b.appendChild(tr)});
  if(!sel||list.indexOf(sel)<0)sel=worst;detail()}
function detail(){
  var s=D.extractors[$('e').value].layouts[sel];$('dh').textContent='Fields in '+sel;
  var dc=$('dc');dc.textContent='';var any=false;
  Object.keys(s.errors).forEach(function(c){if(s.errors[c]){any=true;dc.appendChild(el('span',c+' '+s.errors[c],'chip'))}});
  if(!any)dc.appendChild(el('span','no wrong values','chip'));
  var f=$('f');f.textContent='';
  Object.keys(s.fields).sort(function(a,b){return pct(s.fields[a][1],s.fields[a][0])-pct(s.fields[b][1],s.fields[b][0])||(a<b?-1:1)}).forEach(function(n){
    var tr=el('tr');cell(tr,n);cell(tr,s.fields[n][0]);cell(tr,pct(s.fields[n][1],s.fields[n][0]).toFixed(1)+'%');f.appendChild(tr)})}
Object.keys(D.extractors).sort().forEach(function(n){var o=el('option',n);o.value=n;$('e').appendChild(o)});
$('e').value='alias_aware';
var m=$('m');Object.keys(D.mixes).sort(function(a,b){return D.mixes[b]-D.mixes[a]}).forEach(function(n){var tr=el('tr');cell(tr,n);cell(tr,D.mixes[n].toFixed(1)+'%');m.appendChild(tr)});
['e','sc'].forEach(function(i){$(i).onchange=function(){sel=null;draw()}});
['fl','gp'].forEach(function(i){$(i).oninput=draw});
draw();
</script></body></html>
"""
page = page.replace("__DATA__", json.dumps(slim, sort_keys=True).replace("</", "<\\/"))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
