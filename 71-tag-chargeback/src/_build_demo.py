"""Build demo.html from the files step_04_with_tool.py writes to out/. Run step 4 first.
Run (from src/):  python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read_rows(name):
    with open(os.path.join(HERE, "out", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
data = {"summary": summary, "defects": read_rows("step_04_defects.csv"), "reasons": read_rows("step_04_reasons.csv"),
        "centers": read_rows("step_04_chargeback.csv")}
payload = json.dumps(data).replace("</", "<\\/")

page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tag Chargeback: one month of cloud spend</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--ok:#1e6b3a;--bad:#b3261e;--left:#8a5a00;--bar:#3b6fb6;--bar2:#b9c4d6}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--ok:#7fd49a;--bad:#ff8a80;--left:#ffc266;--bar:#7aa7e8;--bar2:#3a4658}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:28px 0 6px}p.s{color:var(--mut);margin:0 0 12px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
label{color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;margin-left:6px}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px;min-width:560px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
td.n,th.n{text-align:right;white-space:nowrap}
.ok{color:var(--ok)}.bad{color:var(--bad);font-weight:600}.left{color:var(--left);font-weight:600}
.wrap{overflow-x:auto}.bar{height:8px;border-radius:4px;background:var(--bar);min-width:1px}.bar.b{background:var(--bar2);margin-top:3px}
</style></head><body><main>
<h1>Tag Chargeback: one month of cloud spend</h1>
<p class="s">Synthetic data, one fictional bank, one billing month. The planted owner of each line is known, so each row says where the money landed against that owner. The same author wrote the data and the rules, so read the numbers as a ceiling.</p>
<div class="k" id="k"></div>
<h2>Where the money went, by planted defect</h2>
<p class="s"><label>Show <select id="f"><option value="">every defect</option><option value="wrong">where money landed on the wrong team</option><option value="left">where money was left for a person</option><option value="clean">where every line was handled correctly</option></select></label> <span id="n"></span></p>
<div class="wrap"><table><thead><tr><th>Planted defect</th><th>What the rules do</th><th class="n">Lines</th><th class="n">Spend</th><th class="n">Correct</th><th class="n">Wrong</th><th class="n">Left</th></tr></thead><tbody id="d"></tbody></table></div>
<h2>Unallocated, by reason</h2>
<div class="wrap"><table><thead><tr><th>Reason</th><th class="n">Lines</th><th class="n">Spend</th></tr></thead><tbody id="r"></tbody></table></div>
<h2>Chargeback by cost center</h2>
<p class="s">Dark bar: what the tool charges. Light bar: the spend the planted owner actually has, shared pool excluded. A gap is a misallocation or a refusal.</p>
<div class="wrap"><table><thead><tr><th>Cost center</th><th>Status</th><th class="n">Charged</th><th class="n">Planted own spend</th><th style="width:30%">Compare</th></tr></thead><tbody id="c"></tbody></table></div>
<p class="s">Known misses: a valid tag on the wrong team and an untagged resource of one team in another team's dedicated account are both charged with no warning. Source: <code>python3 step_04_with_tool.py</code>.</p>
</main>
<script>
var D=__DATA__;
var WHAT={alias_key:"Policy lists the alias: allocated, marked repaired",alias_unlisted:"Key not in the policy: reads as untagged, account default if dedicated",child_untagged:"Inherits from tagged lines of the same resource",clean:"Allocated by tag",closed_cc:"Refused: cost center is closed",conflict:"Refused: two tags disagree",credit:"Negative line allocated by tag",empty_value:"Empty value reads as untagged",foreign_tagged:"Tag beats the account default",missing:"Account default if dedicated, else refused",partial_tag:"Tagged lines by tag, the rest inherit",shared_service:"Split in proportion to allocated spend",unknown_value:"Refused: value not in the registry",value_format:"Case and spaces ignored: allocated, marked repaired",value_nohyphen:"Refused: not in the registry",wrong_default:"Account default charges the wrong team",wrong_valid:"Valid tag, charged as tagged: wrong team",zero_cost:"Nothing to allocate, not reported"};
function money(v){var x=parseFloat(v);return (x<0?"-":"")+"$"+Math.abs(x).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});}
function cell(tr,text,cls){var td=document.createElement("td");td.textContent=text;if(cls)td.className=cls;tr.appendChild(td);return td;}
var S=D.summary,k=document.getElementById("k");
[[S.correct_pct,"on the planted owner"],[S.wrong_pct,"on the wrong team"],[S.left_pct,"left for a person"],[S.compliance_strict+" to "+S.compliance_repaired,"tag compliance by dollars, strict to repaired"]].forEach(function(x){var d=document.createElement("div"),b=document.createElement("b");b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function drawDefects(){var f=document.getElementById("f").value,body=document.getElementById("d"),shown=0;body.textContent="";
D.defects.forEach(function(r){var w=parseFloat(r.wrong)!==0,l=parseFloat(r.left)!==0;
if(f==="wrong"&&!w)return;if(f==="left"&&!l)return;if(f==="clean"&&(w||l))return;shown++;
var tr=document.createElement("tr");cell(tr,r.defect);cell(tr,WHAT[r.defect]||"");cell(tr,r.lines,"n");cell(tr,money(r.usd),"n");cell(tr,money(r.correct),"n ok");cell(tr,money(r.wrong),w?"n bad":"n");cell(tr,money(r.left),l?"n left":"n");body.appendChild(tr);});
document.getElementById("n").textContent=shown+" of "+D.defects.length+" shown";}
document.getElementById("f").onchange=drawDefects;drawDefects();
var rb=document.getElementById("r");D.reasons.forEach(function(r){var tr=document.createElement("tr");cell(tr,r.reason);cell(tr,r.lines,"n");cell(tr,money(r.usd),"n");rb.appendChild(tr);});
var mx=1;D.centers.forEach(function(r){mx=Math.max(mx,parseFloat(r.total),parseFloat(r.planted_own_spend));});
var cb=document.getElementById("c");D.centers.forEach(function(r){var tr=document.createElement("tr");cell(tr,r.cost_center+" "+r.name);cell(tr,r.active==="True"?"active":"closed");cell(tr,money(r.total),"n");cell(tr,money(r.planted_own_spend),"n");
var td=cell(tr,"");var a=document.createElement("div");a.className="bar";a.style.width=Math.max(0,100*parseFloat(r.total)/mx)+"%";var b=document.createElement("div");b.className="bar b";b.style.width=Math.max(0,100*parseFloat(r.planted_own_spend)/mx)+"%";td.appendChild(a);td.appendChild(b);cb.appendChild(tr);});
</script></body></html>
"""
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page.replace("__DATA__", payload))
print("Wrote demo.html")
