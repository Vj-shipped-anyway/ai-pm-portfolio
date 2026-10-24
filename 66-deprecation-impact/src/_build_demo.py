"""Build demo.html from the files step_04_with_map.py writes to out/. Run that step first.
Run (from src/):  python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    with open(os.path.join(HERE, "out", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


deps, calendar = read("step_04_dependencies.csv"), read("step_04_calendar.csv")
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)


def embed(obj):
    return json.dumps(obj).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Deprecation Impact: which features a model retirement hits</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--red:#b3261e;--amber:#8a5a00;--green:#1e6b3a;--blue:#1a5fb4;--grey:#5b6470}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--red:#ff8a80;--amber:#ffc266;--green:#7fd49a;--blue:#8ab4f8;--grey:#9aa3ad}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:24px 0 6px}p.s{color:var(--mut);margin:0 0 12px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 8px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px;min-width:720px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.PAST,.LATE{color:var(--red);font-weight:600}.TIGHT{color:var(--amber);font-weight:600}.ROOM{color:var(--green);font-weight:600}
.SUNSETS{color:var(--grey);font-weight:600}.CHECK{color:var(--blue);font-weight:600}
.wrap{overflow-x:auto}td.n{white-space:nowrap}
</style></head><body><main>
<h1>Deprecation Impact: which features a model retirement hits</h1>
<p class="s">Synthetic data: 60 features, 17 model snapshots, 7 retirement notices. Each row is one place a feature names a model. The last column is the planted truth; everything else is what the tool printed.</p>
<div class="k" id="k"></div>
<h2>Retirement calendar</h2>
<div class="wrap"><table><thead><tr><th>Retires</th><th>Model</th><th>Days left</th><th>Features</th><th>Calls per month</th><th>Worst tier</th><th>Cost now</th><th>Cost on successor</th></tr></thead><tbody id="c"></tbody></table></div>
<h2>Every hit and every entry in the check queue</h2>
<div><label>Tier <select id="t"><option value="">all</option><option>PAST</option><option>LATE</option><option>TIGHT</option><option>ROOM</option><option>SUNSETS</option><option>CHECK</option></select></label>
<label>Truly affected <select id="a"><option value="">all</option><option>yes</option><option>no</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Feature</th><th>Role</th><th>Model string</th><th>Tier</th><th>Retires</th><th>Slack (days)</th><th>Calls per month</th><th>Note</th><th>Truly affected</th></tr></thead><tbody id="b"></tbody></table></div>
<h2>Known misses</h2>
<p class="s">These dependencies pass as clear, or are not in the registry at all. The tool does not show them; the planted truth does.</p>
<ul id="m"></ul>
<p class="s">Source: <code>python3 step_04_with_map.py</code>. Lead times are assumptions (see the README), so the tiers move when you change them.</p>
</main>
<script>
var DEPS=__DEPS__, CAL=__CAL__, SUM=__SUM__;
function cell(tr,v,cls){var td=document.createElement('td');td.textContent=v;if(cls)td.className=cls;tr.appendChild(td);}
var k=document.getElementById('k');
[[SUM.found+' of '+SUM.affected,'affected dependencies found and dated'],[String(SUM.queued),'affected, in the check queue'],[String(SUM.missed),'affected, missed'],[SUM.features_opened+' vs '+SUM.family_features,'features opened, tool vs family search']].forEach(function(x){var d=document.createElement('div');var b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var c=document.getElementById('c');
CAL.forEach(function(r){var tr=document.createElement('tr');cell(tr,r.retire_date,'n');cell(tr,r.model_id);cell(tr,r.days_left,'n');cell(tr,r.features);cell(tr,Number(r.monthly_calls).toLocaleString('en-US'),'n');cell(tr,r.features==='0'?'none':r.tier,r.features==='0'?'':r.tier);cell(tr,r.features==='0'?'':'$'+r.cost_now,'n');cell(tr,r.features==='0'?'':'$'+r.cost_after,'n');c.appendChild(tr);});
function draw(){var t=document.getElementById('t').value,a=document.getElementById('a').value,b=document.getElementById('b');b.textContent='';var n=0;
DEPS.forEach(function(r){if((t&&r.tier!==t)||(a&&r.truly_affected!==a))return;n++;var tr=document.createElement('tr');
cell(tr,r.feature_name);cell(tr,r.role);cell(tr,r.model_ref===''?'(none recorded)':'"'+r.model_ref+'"','n');cell(tr,r.tier,r.tier);cell(tr,r.retire_date,'n');cell(tr,r.slack_days,'n');cell(tr,Number(r.monthly_calls).toLocaleString('en-US'),'n');cell(tr,r.note);cell(tr,r.truly_affected);b.appendChild(tr);});
document.getElementById('n').textContent=n+' shown';}
document.getElementById('t').onchange=draw;document.getElementById('a').onchange=draw;draw();
var m=document.getElementById('m');
SUM.missed_items.forEach(function(r){var li=document.createElement('li');li.textContent=r.feature_id+' '+r.role+' on '+r.true_model+' ('+r.kind+')';m.appendChild(li);});
</script></body></html>
"""
page = page.replace("__DEPS__", embed(deps)).replace("__CAL__", embed(calendar)).replace("__SUM__", embed(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
