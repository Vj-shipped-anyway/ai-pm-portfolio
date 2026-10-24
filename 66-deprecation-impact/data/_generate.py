"""Generate the synthetic data for project 66: a catalog of model snapshots with retirement
notices, 60 features that call them, the registry rows that say which model each feature uses, and
the truth about what each feature really depends on.

The truth is built first, from planted dependency kinds (truth_dependencies.csv). The registry is
written from it afterwards, with gaps on purpose: a fallback that nobody recorded, an alias whose
recorded target is wrong, a feature with no model recorded, strings with odd case and spaces. The
rules in src/ never read the truth file. Fixed seed, so a rerun reproduces every file byte for byte.

Run (from data/):  python3 _generate.py
Writes: models.csv, aliases.csv, features.csv, usages.csv, truth_dependencies.csv, truth_aliases.csv,
        policy.json, example_models.csv, example_aliases.csv, example_features.csv, example_usages.csv
"""
import csv
import datetime
import json
import random

AS_OF = datetime.date(2026, 9, 1)
rng = random.Random(66)
D = datetime.date.fromisoformat

MODEL_COLS = ["model_id", "family", "vendor", "notice_date", "retire_date", "successor",
              "input_usd_per_1m", "output_usd_per_1m", "successor_input_token_factor", "base_model_id"]
MODELS = [
    ("va-large@2025-03", "va-large", "vendor-a", "2026-06-10", "2026-12-10", "va-large@2026-05", 12.00, 60.00, 1.00, ""),
    ("va-large@2026-05", "va-large", "vendor-a", "", "", "", 10.00, 50.00, 1.00, ""),
    ("va-fast@2024-11", "va-fast", "vendor-a", "2026-05-01", "2026-08-20", "va-fast@2025-09", 0.70, 3.50, 1.04, ""),
    ("va-fast@2025-03", "va-fast", "vendor-a", "2026-07-01", "2026-11-15", "va-fast@2025-09", 0.80, 4.00, 1.06, ""),
    ("va-fast@2025-09", "va-fast", "vendor-a", "", "", "", 1.00, 5.00, 1.00, ""),
    ("va-fast-lite@2025-06", "va-fast-lite", "vendor-a", "", "", "", 0.25, 1.25, 1.00, ""),
    ("vb-core@2025-01", "vb-core", "vendor-b", "2026-07-20", "2027-01-20", "vb-core@2026-03", 3.00, 15.00, 1.00, ""),
    ("vb-core@2026-03", "vb-core", "vendor-b", "", "", "", 2.50, 12.50, 1.00, ""),
    ("vb-mini@2024-10", "vb-mini", "vendor-b", "2026-02-01", "2026-06-01", "vb-mini@2026-01", 0.15, 0.60, 1.00, ""),
    ("vb-mini@2025-04", "vb-mini", "vendor-b", "2026-08-05", "2026-10-05", "vb-mini@2026-01", 0.15, 0.60, 1.00, ""),
    ("vb-mini@2026-01", "vb-mini", "vendor-b", "", "", "", 0.12, 0.50, 1.00, ""),
    ("vc-reason@2025-02", "vc-reason", "vendor-c", "2026-08-25", "2027-02-25", "vc-reason@2026-04", 6.00, 24.00, 1.08, ""),
    ("vc-reason@2026-04", "vc-reason", "vendor-c", "", "", "", 5.00, 20.00, 1.00, ""),
    ("vc-chat@2025-08", "vc-chat", "vendor-c", "", "", "", 1.10, 4.40, 1.00, ""),
    ("ft-dispute-v2", "ft-dispute", "vendor-a", "", "", "", 1.60, 8.00, 1.00, "va-fast@2025-03"),
    ("ft-kyc-v1", "ft-kyc", "vendor-a", "", "", "", 14.40, 72.00, 1.00, "va-large@2025-03"),
    ("ft-triage-v3", "ft-triage", "vendor-b", "", "", "", 0.24, 1.00, 1.00, "vb-mini@2026-01"),
]
OWN_RETIRE = {m[0]: m[4] for m in MODELS if m[4]}
BASE_OF = {m[0]: m[9] for m in MODELS if m[9]}
NONRET = ["va-large@2026-05", "va-fast@2025-09", "va-fast-lite@2025-06", "vb-core@2026-03", "vb-mini@2026-01",
          "vc-reason@2026-04", "vc-chat@2025-08"]

# alias, target as recorded in aliases.csv, date it was recorded, what the vendor's alias really points to
ALIASES = [
    ("va-fast-latest", "va-fast@2025-09", "2026-08-10", "va-fast@2025-09"),
    ("vb-core-stable", "vb-core@2025-01", "2026-08-12", "vb-core@2025-01"),
    ("vc-reason-prod", "vc-reason@2025-02", "2026-08-25", "vc-reason@2025-02"),
    ("va-large-default", "va-large@2026-05", "2026-08-20", "va-large@2025-03"),
    ("vb-mini-edge", "vb-mini@2025-04", "2026-03-02", "vb-mini@2026-01"),
    ("vc-chat-default", "vc-chat@2025-08", "2026-02-14", "vc-chat@2025-08"),
    ("ft-dispute-live", "ft-dispute-v2", "2026-08-15", "ft-dispute-v2"),
]

POLICY = {"lead_days": {"critical": 60, "standard": 30, "low": 14}, "no_eval_set_extra_days": 30,
          "judge_extra_days": 14, "finetune_extra_days": 45, "tight_margin_days": 30, "alias_max_age_days": 90}

STEMS = ["dispute-summary", "kyc-doc-reader", "payment-exception-triage", "complaint-classifier", "statement-explainer",
         "card-limit-advisor", "chargeback-drafter", "aml-alert-summarizer", "onboarding-faq", "loan-doc-extractor",
         "call-notes-summary", "fee-query-answerer", "fraud-case-narrative", "branch-ops-assistant",
         "reconciliation-explainer", "sanctions-hit-reviewer", "collections-script-helper", "trade-break-triage",
         "policy-lookup", "address-normalizer"]
LINES = ["retail", "cards", "payments"]


def retire_of(model):
    """Retirement date of a model, own or inherited from the base it was fine-tuned on; None when none applies."""
    while model:
        if model in OWN_RETIRE:
            return D(OWN_RETIRE[model])
        model = BASE_OF.get(model, "")
    return None


def root_of(model):
    while model:
        if model in OWN_RETIRE:
            return model
        model = BASE_OF.get(model, "")
    return ""


# ---------------------------------------------------------------- planted primary dependencies
PLANS = []  # (kind, true model, string written in the registry; "" when the registry has no row)
for m in ["va-large@2025-03", "va-large@2025-03", "va-fast@2025-03", "va-fast@2025-03", "vb-core@2025-01",
          "vb-mini@2025-04", "vc-reason@2025-02"]:
    PLANS.append(("exact_retiring", m, m))
PLANS += [("exact_messy", "va-fast@2025-03", " VA-Fast@2025-03"), ("exact_messy", "vb-mini@2025-04", "vb-mini@2025-04 ")]
for _ in range(17):
    m = rng.choice(NONRET)
    PLANS.append(("exact_ok", m, m))
PLANS += [("alias_retiring", "vb-core@2025-01", "vb-core-stable")] * 3
PLANS += [("alias_retiring", "vc-reason@2025-02", "vc-reason-prod")] * 3
PLANS += [("alias_ok", "va-fast@2025-09", "va-fast-latest")] * 4
PLANS += [("ft_retiring", "ft-dispute-v2", "ft-dispute-v2")] * 2
PLANS += [("ft_retiring", "ft-kyc-v1", "ft-kyc-v1")] * 2
PLANS += [("ft_retiring", "ft-dispute-v2", "ft-dispute-live")] * 2
PLANS += [("ft_ok", "ft-triage-v3", "ft-triage-v3")] * 2
PLANS += [("bare_retiring", "va-fast@2025-03", "va-fast")] * 2 + [("bare_retiring", "vb-core@2025-01", "vb-core")]
PLANS += [("bare_ok", "va-fast@2025-09", "va-fast")] * 2
PLANS += [("stale_alias_missed", "va-large@2025-03", "va-large-default")] * 3
PLANS += [("stale_alias_check", "vb-mini@2026-01", "vb-mini-edge")] * 2
PLANS += [("unresolved_retiring", "va-fast@2025-03", "va-fast@2025-3"), ("unresolved_ok", "vd-lite@1", "vd-lite@1"),
          ("unresolved_ok", "vc-chat@2025-08", "internal-router")]
PLANS += [("no_model_retiring", "va-fast@2025-03", ""), ("no_model_retiring", "vc-reason@2025-02", ""),
          ("no_model_ok", "va-fast-lite@2025-06", "")]
assert len(PLANS) == 60
rng.shuffle(PLANS)

names = [(s, line) for line in LINES for s in STEMS]
rng.shuffle(names)
names = names[:60]

features = []   # dicts
deps = []       # dicts: one per true dependency
for i, (kind, true_model, written) in enumerate(PLANS):
    fid = f"FT-{i + 1:03d}"
    stem, line = names[i]
    r = rng.random()
    crit = "critical" if r < 0.25 else "standard" if r < 0.75 else "low"
    has_eval = "yes" if rng.random() < 0.6 else "no"
    calls = rng.choice([8000, 25000, 60000, 150000, 400000, 1200000])
    tin, tout = rng.randrange(300, 3000, 50), rng.randrange(60, 900, 10)
    features.append(dict(feature_id=fid, feature_name=f"{stem}-{line}", owner_team=f"team-{line}", business_line=line,
                         criticality=crit, has_eval_set=has_eval, sunset_date="", kind=kind, calls=calls, tin=tin, tout=tout))
    deps.append(dict(feature_id=fid, role="primary", true_model=true_model, written=written, kind=kind,
                     calls=calls, tin=tin, tout=tout))

# fallbacks and judges attach to features after the primaries are fixed
by_feature = {f["feature_id"]: f for f in features}
clean_kinds = ("exact_ok", "alias_ok", "ft_ok", "bare_ok")
clean = [f["feature_id"] for f in features if f["kind"] in clean_kinds]
rng.shuffle(clean)
unrecorded = clean[:4]
recorded = [f["feature_id"] for f in features if not f["kind"].startswith("no_model") and f["feature_id"] not in unrecorded]


def attach(fid, role, true_model, written, kind):
    f = by_feature[fid]
    if role == "fallback":
        calls, tin, tout = max(100, f["calls"] * 3 // 100), f["tin"], f["tout"]
    else:
        calls, tin, tout = rng.choice([1800, 3000, 4500]), f["tin"] + f["tout"] + 300, 120
    deps.append(dict(feature_id=fid, role=role, true_model=true_model, written=written, kind=kind, calls=calls, tin=tin, tout=tout))


for fid, m in zip(unrecorded, ["va-fast@2025-03", "va-fast@2025-03", "vb-core@2025-01", "va-large@2025-03"]):
    attach(fid, "fallback", m, "", "fallback_unrecorded")
pool = list(recorded)
rng.shuffle(pool)
for fid, m in zip(pool[:6], ["va-large@2025-03", "va-fast@2025-03", "va-fast@2025-03", "vb-core@2025-01", "vb-mini@2025-04", "vc-reason@2025-02"]):
    attach(fid, "fallback", m, m, "fallback_retiring")
attach(pool[6], "fallback", "va-fast@2024-11", "va-fast@2024-11", "fallback_past")
for fid in pool[7:15]:
    m = rng.choice(NONRET)
    attach(fid, "fallback", m, m, "fallback_ok")
rng.shuffle(pool)
for fid, m in zip(pool[:4], ["vc-reason@2025-02", "vc-reason@2025-02", "va-large@2025-03", "vb-core@2025-01"]):
    attach(fid, "judge", m, m, "judge_retiring")
for fid in pool[4:8]:
    m = rng.choice(["vc-reason@2026-04", "va-large@2026-05", "vc-chat@2025-08", "vb-core@2026-03"])
    attach(fid, "judge", m, m, "judge_ok")

# four features sunset: two before their model retires, two after
sunset_pool = sorted(f["feature_id"] for f in features if f["kind"] in ("exact_retiring", "alias_retiring"))
rng.shuffle(sunset_pool)
for fid, delta in zip(sunset_pool[:4], [-20, -20, 40, 40]):
    primary = [d for d in deps if d["feature_id"] == fid and d["role"] == "primary"][0]
    by_feature[fid]["sunset_date"] = (retire_of(primary["true_model"]) + datetime.timedelta(days=delta)).isoformat()

ROLE_ORDER = {"primary": 0, "fallback": 1, "judge": 2}
deps.sort(key=lambda d: (d["feature_id"], ROLE_ORDER[d["role"]]))


def affected(d):
    r = retire_of(d["true_model"])
    if r is None:
        return "no"
    sunset = by_feature[d["feature_id"]]["sunset_date"]
    return "no" if sunset and D(sunset) <= r else "yes"


def money(x):
    return f"{x:.2f}"


def write(name, header, rows):
    with open(name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    write("models.csv", MODEL_COLS, [list(m[:6]) + [money(m[6]), money(m[7]), money(m[8]), m[9]] for m in MODELS])
    write("aliases.csv", ["alias", "model_id", "recorded_on"], [[a, t, on] for a, t, on, _ in ALIASES])
    write("truth_aliases.csv", ["alias", "recorded_target", "recorded_on", "true_target"], [list(a) for a in ALIASES])
    write("features.csv", ["feature_id", "feature_name", "owner_team", "business_line", "criticality", "has_eval_set", "sunset_date"],
          [[f[k] for k in ("feature_id", "feature_name", "owner_team", "business_line", "criticality", "has_eval_set", "sunset_date")] for f in features])
    usage_rows = []
    for d in deps:
        if d["written"] == "":
            continue
        usage_rows.append([f"U-{len(usage_rows) + 1:04d}", d["feature_id"], d["role"], d["written"],
                           f"svc/{by_feature[d['feature_id']]['feature_name']}/config.yaml:{d['role']}_model",
                           d["calls"], d["tin"], d["tout"]])
    write("usages.csv", ["usage_id", "feature_id", "role", "model_ref", "config_path", "monthly_calls", "avg_input_tokens", "avg_output_tokens"], usage_rows)
    write("truth_dependencies.csv",
          ["feature_id", "role", "true_model_id", "true_root_model_id", "true_retire_date", "written_ref", "kind", "affected", "monthly_calls"],
          [[d["feature_id"], d["role"], d["true_model"], root_of(d["true_model"]),
            retire_of(d["true_model"]).isoformat() if retire_of(d["true_model"]) else "", d["written"], d["kind"], affected(d), d["calls"]]
           for d in deps])
    with open("policy.json", "w", encoding="utf-8") as fh:
        json.dump(POLICY, fh, indent=1, sort_keys=True)
        fh.write("\n")
    # a small worked example for the command line: five features, as of the same date
    keep = ["va-fast@2025-03", "va-fast@2025-09", "vb-mini@2025-04", "vb-mini@2026-01", "vb-core@2025-01", "vb-core@2026-03",
            "vc-chat@2025-08", "vc-reason@2025-02", "vc-reason@2026-04", "ft-dispute-v2"]
    write("example_models.csv", MODEL_COLS, [list(m[:6]) + [money(m[6]), money(m[7]), money(m[8]), m[9]] for m in MODELS if m[0] in keep])
    write("example_aliases.csv", ["alias", "model_id", "recorded_on"], [["vb-core-stable", "vb-core@2025-01", "2026-08-12"]])
    write("example_features.csv", ["feature_id", "feature_name", "owner_team", "business_line", "criticality", "has_eval_set", "sunset_date"], [
        ["EX-1", "dispute-summary", "team-cards", "cards", "critical", "yes", ""],
        ["EX-2", "kyc-doc-reader", "team-retail", "retail", "standard", "no", ""],
        ["EX-3", "complaint-classifier", "team-retail", "retail", "low", "yes", ""],
        ["EX-4", "fee-query-answerer", "team-cards", "cards", "standard", "yes", ""],
        ["EX-5", "statement-explainer", "team-payments", "payments", "critical", "yes", ""]])
    write("example_usages.csv", ["usage_id", "feature_id", "role", "model_ref", "config_path", "monthly_calls", "avg_input_tokens", "avg_output_tokens"], [
        ["X-1", "EX-1", "primary", "va-fast@2025-03", "svc/dispute-summary/config.yaml:primary_model", 400000, 1200, 250],
        ["X-2", "EX-1", "fallback", "vb-mini@2025-04", "svc/dispute-summary/config.yaml:fallback_model", 12000, 1200, 250],
        ["X-3", "EX-2", "primary", "vb-core-stable", "svc/kyc-doc-reader/config.yaml:primary_model", 60000, 2400, 180],
        ["X-4", "EX-3", "primary", "va-fast", "svc/complaint-classifier/config.yaml:primary_model", 25000, 700, 60],
        ["X-5", "EX-4", "primary", "vc-chat@2025-08", "svc/fee-query-answerer/config.yaml:primary_model", 150000, 900, 220],
        ["X-6", "EX-5", "primary", "ft-dispute-v2", "svc/statement-explainer/config.yaml:primary_model", 90000, 1500, 400],
        ["X-7", "EX-5", "judge", "vc-reason@2025-02", "svc/statement-explainer/config.yaml:judge_model", 3000, 1900, 120]])
    print(f"wrote {len(MODELS)} models, {len(ALIASES)} aliases, {len(features)} features, {len(usage_rows)} usage rows, {len(deps)} true dependencies")


if __name__ == "__main__":
    main()
