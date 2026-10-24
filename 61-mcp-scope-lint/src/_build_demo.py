"""Build demo.html from the files step_04_with_lint.py writes to out/. Run that step first.
Run (from src/):  python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def rows(name):
    with open(os.path.join(HERE, "out", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def embed(obj):
    return json.dumps(obj).replace("</", "<\\/")


with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MCP Scope Lint: 30 manifests, one proposal each</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--err:#b3261e;--warn:#8a5a00;--ok:#1e6b3a;--sel:#eef3fb}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--err:#ff8a80;--warn:#ffc266;--ok:#7fd49a;--sel:#1e2735}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:20px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
table{width:100%;border-collapse:collapse;font-size:14px;min-width:560px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
tr.pick{cursor:pointer}tr.on{background:var(--sel)}
.error{color:var(--err);font-weight:600}.warn{color:var(--warn);font-weight:600}.none{color:var(--ok)}
.wrap{overflow-x:auto}code{font-size:13px}
</style></head><body><main>
<h1>MCP Scope Lint: 30 manifests, one proposal each</h1>
<p class="s">Synthetic data. Each row is an MCP server manifest. The lint reads the scopes it grants and the scopes its tools ask for, then proposes a smaller grant. Truth columns come from the generator, not from the rules.</p>
<div class="k" id="k"></div>
<div class="wrap"><table><thead><tr><th>Server</th><th>Tools</th><th>Reach</th><th>After</th><th>Breadth %</th><th>Errors</th><th>Warnings</th><th>Unneeded (truth)</th><th>Cut</th><th>Needed cut</th></tr></thead><tbody id="t"></tbody></table></div>
<h2 id="h"></h2>
<label>Server <select id="sel"></select></label>
<h2>Findings</h2>
<div class="wrap"><table><thead><tr><th>Severity</th><th>Rule</th><th>Tool or scope</th><th>Message</th></tr></thead><tbody id="f"></tbody></table></div>
<h2>Proposal</h2>
<div class="wrap"><table><thead><tr><th>Level</th><th>Subject</th><th>Action</th><th>Detail</th></tr></thead><tbody id="c"></tbody></table></div>
<p class="s">Known limit: a tool with no hint that asks for more than it needs, a hint that overstates, and a tool nobody calls all pass; a wrong read-only hint makes the proposal cut a scope that is needed. Source: <code>python3 step_04_with_lint.py</code>.</p>
</main>
<script>
var SERVERS=__SERVERS__, FINDINGS=__FINDINGS__, CHANGES=__CHANGES__, SUM=__SUM__;
function cell(tr,v,cls){var td=document.createElement('td');td.textContent=v;if(cls)td.className=cls;tr.appendChild(td);}
function tile(a,b){var d=document.createElement('div'),x=document.createElement('b');x.textContent=a;d.appendChild(x);d.appendChild(document.createTextNode(b));document.getElementById('k').appendChild(d);}
tile(SUM.reach_before+' to '+SUM.reach_after,'reachable scopes, before and after');
tile(SUM.unneeded_cut+' of '+SUM.truth_unneeded,'unneeded scopes cut');
tile(SUM.needed_cut,'needed scopes cut (wrong hint)');
tile(SUM.errors+' / '+SUM.warnings,'errors / warnings');
var sel=document.getElementById('sel'),tb=document.getElementById('t');
function fill(id,list,fn){var b=document.getElementById(id);b.textContent='';if(!list.length){var tr=document.createElement('tr');cell(tr,'none','none');b.appendChild(tr);return;}list.forEach(function(r){var tr=document.createElement('tr');fn(tr,r);b.appendChild(tr);});}
function show(name){
  document.getElementById('h').textContent=name;sel.value=name;
  Array.prototype.forEach.call(tb.children,function(tr){tr.className=tr.getAttribute('data-n')===name?'pick on':'pick';});
  fill('f',FINDINGS.filter(function(r){return r.server===name;}),function(tr,r){cell(tr,r.severity,r.severity);cell(tr,r.kind);cell(tr,r.tool||r.scope);cell(tr,r.message);});
  fill('c',CHANGES.filter(function(r){return r.server===name&&r.action!=='keep';}),function(tr,r){cell(tr,r.level);cell(tr,r.subject);cell(tr,r.action);cell(tr,r.detail);});
}
SERVERS.forEach(function(r){
  var o=document.createElement('option');o.textContent=r.server;sel.appendChild(o);
  var tr=document.createElement('tr');tr.className='pick';tr.setAttribute('data-n',r.server);
  [r.server,r.tools,r.reach_before,r.reach_after,r.breadth_pct,r.errors,r.warnings,r.unneeded_truth,r.unneeded_cut,r.needed_cut].forEach(function(v){cell(tr,v);});
  tr.onclick=function(){show(r.server);};tb.appendChild(tr);
});
sel.onchange=function(){show(sel.value);};
show(SERVERS[0].server);
</script></body></html>
"""
page = (page.replace("__SERVERS__", embed(rows("step_04_servers.csv"))).replace("__FINDINGS__", embed(rows("step_04_findings.csv")))
        .replace("__CHANGES__", embed(rows("step_04_changes.csv"))).replace("__SUM__", embed(summary)))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
