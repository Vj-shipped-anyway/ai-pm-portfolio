"""Build demo.html from out/step_04_demo.json. Run step_04_token_matcher.py first. Run (from src/): python3 _build_demo.py"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_demo.json"), encoding="utf-8") as fh:
    data = json.load(fh)

page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Name Match Eval: three matchers, one threshold</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--c1:#b3261e;--c2:#8a5a00;--c3:#1e6b3a;--acc:#1a5fb4}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--c1:#ff8a80;--c2:#ffc266;--c3:#7fd49a;--acc:#8ab4f8}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:20px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
label{display:block;margin:8px 0;color:var(--mut)}select,input[type=range]{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
input[type=range]{width:100%;max-width:420px;padding:0}
table{width:100%;border-collapse:collapse;font-size:14px;min-width:420px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
td.n{text-align:right;white-space:nowrap}th.n{text-align:right}
.wrap{overflow-x:auto}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:700px){.cols{grid-template-columns:1fr}}
svg{width:100%;height:auto;max-width:560px;display:block}
svg text{fill:var(--mut);font-size:11px}
</style></head><body><main>
<h1>Name Match Eval: three matchers, one threshold</h1>
<p class="s">Synthetic data: 90 listed names, 400 customer names, 150 of them the same party as a listed entity spelled differently. Pick a matcher and move the threshold; the numbers are what the step scripts printed.</p>
<label>Matcher <select id="m"><option value="edit">edit (whole-name characters)</option><option value="tokens-flat">tokens-flat (words, any order)</option><option value="tokens" selected>tokens (words, any order, rare words weigh more)</option></select></label>
<label>Threshold <span id="tv"></span><input type="range" id="t" min="0.30" max="1.00" step="0.01" value="0.80"></label>
<div class="k" id="k"></div>
<h2>Recall against false alerts, all thresholds from 0.30 to 1.00</h2>
<svg id="chart" viewBox="0 0 400 260" role="img" aria-label="Recall against false-alert rate for three matchers"></svg>
<p class="s" id="lg"></p>
<div class="cols">
<div><h2>Planted matches caught</h2><div class="wrap"><table><thead><tr><th>Planted change</th><th class="n">Caught</th></tr></thead><tbody id="mt"></tbody></table></div></div>
<div><h2>Clear names that alert</h2><div class="wrap"><table><thead><tr><th>Planted kind</th><th class="n">Alerts</th></tr></thead><tbody id="ct"></tbody></table></div></div>
</div>
<p class="s">Known misses: alias_unlisted (the list does not carry the name) and namesake (the same name, a different person) at every threshold. The targets, 10.0% false alerts and 85.0% recall, are my assumptions. Source: <code>python3 step_04_token_matcher.py</code>.</p>
</main>
<script>
var D=__DATA__;
var COLORS={"edit":"var(--c1)","tokens-flat":"var(--c2)","tokens":"var(--c3)"};
var NS="http://www.w3.org/2000/svg";
function el(tag,attrs,text){var e=document.createElementNS(NS,tag);Object.keys(attrs).forEach(function(k){e.setAttribute(k,attrs[k]);});if(text!==undefined){e.textContent=text;}return e;}
function row(tb,a,b){var tr=document.createElement('tr');var t1=document.createElement('td');t1.textContent=a;var t2=document.createElement('td');t2.className='n';t2.textContent=b;tr.appendChild(t1);tr.appendChild(t2);tb.appendChild(tr);}
function pct(a,b){return b?(100*a/b).toFixed(1)+'%':'n/a';}
function at(m,t){var rows=D.matchers[m];for(var i=0;i<rows.length;i++){if(Math.abs(rows[i].threshold-t)<0.0005){return rows[i];}}return rows[0];}
function chart(){
  var s=document.getElementById('chart');while(s.firstChild){s.removeChild(s.firstChild);}
  var X=function(v){return 40+v*340;},Y=function(v){return 230-v*210;};
  s.appendChild(el('rect',{x:40,y:20,width:340,height:210,fill:'none',stroke:'var(--line)'}));
  [0,0.25,0.5,0.75,1].forEach(function(v){s.appendChild(el('text',{x:4,y:Y(v)+4},Math.round(v*100)+'%'));s.appendChild(el('text',{x:X(v)-8,y:246},Math.round(v*100)+'%'));});
  s.appendChild(el('line',{x1:X(D.targets.false_alert),y1:20,x2:X(D.targets.false_alert),y2:230,stroke:'var(--mut)','stroke-dasharray':'4 3'}));
  s.appendChild(el('line',{x1:40,y1:Y(D.targets.recall),x2:380,y2:Y(D.targets.recall),stroke:'var(--mut)','stroke-dasharray':'4 3'}));
  s.appendChild(el('text',{x:230,y:14},'false-alert rate'));
  Object.keys(D.matchers).forEach(function(m){
    var pts=D.matchers[m].map(function(r){return X(r.false_alerts/r.clear).toFixed(1)+','+Y(r.caught/r.matches).toFixed(1);}).join(' ');
    s.appendChild(el('polyline',{points:pts,fill:'none',stroke:COLORS[m],'stroke-width':2}));
  });
  var sel=document.getElementById('m').value,r=at(sel,parseFloat(document.getElementById('t').value));
  s.appendChild(el('circle',{cx:X(r.false_alerts/r.clear),cy:Y(r.caught/r.matches),r:5,fill:'var(--acc)'}));
}
function draw(){
  var m=document.getElementById('m').value,t=parseFloat(document.getElementById('t').value),r=at(m,t);
  document.getElementById('tv').textContent=t.toFixed(2);
  var k=document.getElementById('k');while(k.firstChild){k.removeChild(k.firstChild);}
  [[r.caught+' of '+r.matches+' ('+pct(r.caught,r.matches)+')','matches caught'],[r.false_alerts+' of '+r.clear+' ('+pct(r.false_alerts,r.clear)+')','clear names alerting'],[String(r.alerts),'alerts to review']].forEach(function(x){
    var d=document.createElement('div'),b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
  var mt=document.getElementById('mt'),ct=document.getElementById('ct');
  while(mt.firstChild){mt.removeChild(mt.firstChild);}while(ct.firstChild){ct.removeChild(ct.firstChild);}
  D.kinds.match.forEach(function(kind){row(mt,kind,r.kinds[kind]+' of '+D.counts[kind]);});
  D.kinds.clear.forEach(function(kind){row(ct,kind,r.kinds[kind]+' of '+D.counts[kind]);});
  chart();
}
var lg=document.getElementById('lg');
Object.keys(COLORS).forEach(function(m){var sp=document.createElement('span');sp.style.color=COLORS[m];sp.textContent='\\u25A0 '+m+'   ';lg.appendChild(sp);});
lg.appendChild(document.createTextNode('Dashed lines: the 10.0% false-alert and 85.0% recall targets. Dot: the selected setting.'));
document.getElementById('m').onchange=draw;document.getElementById('t').oninput=draw;draw();
</script></body></html>
"""
page = page.replace("__DATA__", json.dumps(data, sort_keys=True).replace("</", "<\\/"))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
