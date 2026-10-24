"""A tiny registry written to a temp folder, so each test states only what it changes."""
import contextlib
import io
import os

import deprecation_impact as di

AS_OF = "2026-09-01"
MODELS = """model_id,family,vendor,notice_date,retire_date,successor,input_usd_per_1m,output_usd_per_1m,successor_input_token_factor,base_model_id
m-old@1,m,v,2026-01-01,2026-12-01,m-new@2,3.00,15.00,1.10,
m-new@2,m,v,,,,2.00,10.00,1.00,
m-lite@1,m-lite,v,,,,0.50,2.00,1.00,
ft-a,ft-a,v,,,,4.00,20.00,1.00,m-old@1
dead@1,dead,v,2026-01-01,2026-03-01,,1.00,1.00,1.00,
"""
ALIASES = """alias,model_id,recorded_on
m-prod,m-old@1,2026-08-20
m-stale,m-old@1,2026-02-01
lite-prod,m-lite@1,2026-01-01
"""
FEATURES = """feature_id,feature_name,owner_team,business_line,criticality,has_eval_set,sunset_date
F1,alpha,t,retail,critical,yes,
F2,beta,t,cards,standard,no,
F3,gamma,t,cards,low,yes,
"""
USAGE_HEAD = "usage_id,feature_id,role,model_ref,config_path,monthly_calls,avg_input_tokens,avg_output_tokens\n"


def usage_line(n, feature, role, ref, calls=1000, tin=1000, tout=100):
    return f"U{n},{feature},{role},{ref},cfg,{calls},{tin},{tout}\n"


def write(folder, name, text):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return path


def build(folder, usages, models=MODELS, aliases=ALIASES, features=FEATURES):
    """Write the four files; returns the argv for `report` with all of them."""
    return ["report", "--features", write(folder, "features.csv", features), "--usages", write(folder, "usages.csv", USAGE_HEAD + usages),
            "--models", write(folder, "models.csv", models), "--aliases", write(folder, "aliases.csv", aliases), "--as-of", AS_OF]


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = di.main(argv)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()
