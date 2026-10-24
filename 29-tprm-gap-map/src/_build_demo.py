"""Build demo.html from out/step_04_vendors.csv and data/guidance_map.csv. Run step_04_with_ai_fields.py first.
Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_vendors.csv"), encoding="utf-8") as fh:
    vendors = list(csv.DictReader(fh))
with open(os.path.join(HERE, "..", "data", "guidance_map.csv"), encoding="utf-8") as fh:
    gmap = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TPRM Gap Map: the text's examples against AI-specific characteristics</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--hi:#b3261e;--ok:#1e6b3a;--warn:#8a5a00}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--hi:#ff8a80;--ok:#7fd49a;--warn:#ffc266}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:28px 0 6px}
p.s{color:var(--mut);margin:0 0 12px}.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 12px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}label{margin-right:12px;color:var(--mut)}
.wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px;min-width:720px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.HIGH{color:var(--hi);font-weight:600}.LOWER{color:var(--ok);font-weight:600}.not{color:var(--warn);font-weight:600}
</style></head><body><main>
<h1>TPRM Gap Map: the text's examples against AI-specific characteristics</h1>
<p class="s">Synthetic vendors and a simulated 36-month incident log. The hazard rates are my assumptions, so read the numbers as a method, not as how real vendors behave.</p>
<div class="k" id="k"></div>
<h2>Vendors</h2>
<div><label>Tier with AI characteristics <select id="a"><option value="">all</option><option>HIGH</option><option>LOWER</option></select></label>
<label>Tier from the text's examples <select id="t"><option value="">all</option><option>HIGH</option><option>LOWER</option></select></label>
<label>Material incident <select id="m"><option value="">all</option><option>yes</option><option>no</option></select></label><span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Vendor</th><th>Service</th><th>Share %</th><th>Upstream</th><th>Text examples</th><th>With AI characteristics</th><th>Material incident</th><th>Causes</th></tr></thead><tbody id="b"></tbody></table></div>
<h2>Guidance map</h2>
<p class="s">What the proposed text says at each stage, whether it prompts the evidence an AI-enabled vendor needs, and what that evidence is. Source: the proposed interagency guidance of 2026-09-11 (docket OCC-2026-0793).</p>
<div class="wrap"><table><thead><tr><th>Stage</th><th>Section</th><th>Text prompts it</th><th>Evidence for an AI-enabled vendor</th></tr></thead><tbody id="g"></tbody></table></div>
</main>
<script>
var V=__V__, G=__G__, S=__S__;
var k=document.getElementById('k');
[[S.text_caught+' of '+S.material,'caught by the text examples'],[S.ai_caught+' of '+S.material,'caught with AI characteristics'],[S.text_false+' to '+S.ai_false,'false alarms, text to AI'],[S.text_flagged+' to '+S.ai_flagged,'vendors marked HIGH']].forEach(function(x){var d=document.createElement('div');d.innerHTML='<b>'+x[0]+'</b>'+x[1];k.appendChild(d);});
function cell(tr,v,c){var td=document.createElement('td');td.textContent=v;if(c)td.className=c;tr.appendChild(td);}
function draw(){var a=document.getElementById('a').value,t=document.getElementById('t').value,m=document.getElementById('m').value,b=document.getElementById('b');b.innerHTML='';var n=0;
V.forEach(function(r){if((a&&r.tier_with_ai!==a)||(t&&r.tier_text_examples!==t)||(m&&r.material_incident!==m))return;n++;var tr=document.createElement('tr');
cell(tr,r.vendor_id);cell(tr,r.service_type);cell(tr,r.activity_share_pct);cell(tr,r.upstream_provider||'-');cell(tr,r.tier_text_examples,r.tier_text_examples);cell(tr,r.tier_with_ai,r.tier_with_ai);cell(tr,r.material_incident);cell(tr,r.causes||'-');b.appendChild(tr);});
document.getElementById('n').textContent=n+' shown';}
['a','t','m'].forEach(function(i){document.getElementById(i).onchange=draw;});draw();
var g=document.getElementById('g');G.forEach(function(r){var tr=document.createElement('tr');cell(tr,r.stage);cell(tr,r.section_of_proposed_guidance);cell(tr,r.how_the_text_prompts_it,r.how_the_text_prompts_it==='not mentioned'?'not':'');cell(tr,r.evidence_for_an_ai_enabled_vendor);g.appendChild(tr);});
</script></body></html>
"""
page = page.replace("__V__", json.dumps(vendors)).replace("__G__", json.dumps(gmap)).replace("__S__", json.dumps(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
