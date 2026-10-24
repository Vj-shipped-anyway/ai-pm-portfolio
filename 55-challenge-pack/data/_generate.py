"""Generate the synthetic data for project 55: 150 AI use cases with a declared tier, the evidence
package each sponsor has on file, and the planted truth about both.

Everything is seeded, so a rerun reproduces every file byte for byte. Standard library only.

The truth comes from a process that is separate from the rules in src/challenge_pack.py:
  - each use case has hidden true attributes, and a true tier from the written rubric on them;
  - the form misstates some attributes (vendor omitted, data class one level low) and the sponsor
    shades the declared tier, so the declared tier can be wrong in either direction;
  - the sponsor files evidence for the items they think they owe, and every filed item is given a
    planted status: ok, reaffirmed, boundary, stale, wrong_version, not_independent or hollow.
    A missing item is simply not filed.
Hard negatives are planted on purpose: reaffirmed items (old date, recent reaffirmation), items dated
exactly at the edge of the window, first-line items prepared by the developer's own unit, and evidence
filed for items the use case does not owe. One kind cannot be seen from the files: hollow evidence,
which is on time, current, independent and says nothing.

Run (from data/):  python3 _generate.py
Writes: use_cases.csv, evidence.csv, truth_tier.csv, truth_evidence.csv, plan_items.csv, plan_tiers.csv,
        example_use_cases.csv, example_evidence.csv
"""
from __future__ import annotations

import calendar
import csv
import datetime as dt
import random
from pathlib import Path

SEED = 20261024
OUT = Path(__file__).parent
rng = random.Random(SEED)
N_USE_CASES = 150
AS_OF = dt.date(2026, 10, 1)

# ---------------------------------------------------------------------------
# The rubric, as written in project 11 (points on six inputs; tier = min(4, 1 + points // 4))
# ---------------------------------------------------------------------------
PTS_CUSTOMER = {"yes": 2, "no": 0}
PTS_AUTONOMY = {"advisory": 0, "assisted": 1, "automated": 3}
CLASS_ORDER = ["public", "internal", "confidential", "restricted"]
PTS_CLASS = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
PTS_VENDOR = {"none": 0, "self_hosted": 1, "vendor_api": 2}
PTS_REG = {"none": 0, "privacy": 1, "aml": 2, "udaap": 2, "fair_lending": 3}
PTS_EXPOSURE = {"lt_1m": 0, "1m_10m": 1, "10m_50m": 2, "gt_50m": 3}
OUT_OF_SCOPE = ("rules", "generative", "agentic")


def points(cf, aut, cls, ven, reg, exp):
    return PTS_CUSTOMER[cf] + PTS_AUTONOMY[aut] + PTS_CLASS[cls] + PTS_VENDOR[ven] + PTS_REG[reg] + PTS_EXPOSURE[exp]


def tier_of(p):
    return min(4, 1 + p // 4)


# ---------------------------------------------------------------------------
# The test plan (the spec both sides read): id, min tier, independent, overlay
# ---------------------------------------------------------------------------
PLAN = [
    ("CH01", 1, 0, ""), ("CH02", 1, 0, ""), ("CH03", 1, 0, ""),
    ("CH04", 2, 0, ""), ("CH05", 2, 0, ""), ("CH06", 2, 0, ""),
    ("CH07", 3, 1, ""), ("CH08", 3, 1, ""), ("CH09", 3, 0, ""), ("CH10", 3, 1, ""),
    ("CH11", 4, 1, ""), ("CH12", 4, 1, ""), ("CH13", 4, 1, ""),
    ("V01", 1, 0, "vendor"), ("V02", 2, 1, "vendor"), ("G01", 1, 1, "scope"),
]
WINDOW = {1: 36, 2: 24, 3: 12, 4: 12}
DEPTH = {1: "Inventory and monitor", 2: "Desk review", 3: "Independent validation",
         4: "Independent validation, benchmark and senior sign-off"}
INDEPENDENT = {i: bool(ind) for i, _t, ind, _o in PLAN}


def owed(model_type, vendor, tier):
    out = []
    for item_id, min_tier, _ind, overlay in PLAN:
        if min_tier > tier:
            continue
        if overlay == "vendor" and vendor == "none":
            continue
        if overlay == "scope" and model_type not in OUT_OF_SCOPE:
            continue
        out.append(item_id)
    return out


# ---------------------------------------------------------------------------
# Documented parameters (mine, not observations)
# ---------------------------------------------------------------------------
P_VENDOR_OMIT = 0.25        # a vendor-dependent use case whose form says no vendor
P_CLASS_UNDER = 0.20        # data class written one level below the truth
P_SHADE_DOWN = 0.20         # declared one tier below the rubric on the form as written
P_SHADE_UP = 0.03           # declared one tier above it
P_FILE_KNOWN = 0.93         # an item the sponsor knows they owe is filed
P_FILE_UNKNOWN = 0.20       # an item owed under the true tier only is filed by chance
P_FILE_EXTRA = 0.15         # an item the use case does not owe is filed anyway
STATUSES = ["ok", "reaffirmed", "boundary", "stale", "wrong_version", "not_independent", "hollow"]
STATUS_W = [0.62, 0.12, 0.03, 0.08, 0.06, 0.06, 0.03]
MODEL_TYPES = ["statistical", "ml", "rules", "generative", "agentic"]
MODEL_W = [0.20, 0.35, 0.10, 0.25, 0.10]

STEMS = {
    "statistical": ["Deposit attrition forecast", "Loan loss reserve estimator", "Branch cash demand forecast",
                    "Card spend seasonality model", "Collections roll-rate model"],
    "ml": ["Payment fraud scoring", "Merchant risk scoring", "Transaction anomaly detector",
           "Early-warning delinquency score", "Customer churn propensity"],
    "rules": ["Sanctions list screening rules", "Overdraft fee waiver rules", "Wire limit rule engine",
              "Dormant account flagging rules"],
    "generative": ["Complaint summarisation assistant", "Dispute letter drafting assistant",
                   "Policy question assistant", "Call note summariser", "Procedure search assistant"],
    "agentic": ["Payment exception resolution agent", "Reconciliation break agent",
                "KYC refresh outreach agent", "Statement query agent"],
}
DEV_UNITS = ["Retail Lending", "Cards", "Payments Operations", "Treasury", "Collections", "Digital Channels",
             "Fraud Strategy"]
SECOND_LINE = ["Model Risk Management", "Operational Risk", "Compliance Testing"]


def add_months(d, n):
    y, m0 = divmod(d.year * 12 + (d.month - 1) + n, 12)
    m = m0 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def older_version(v):
    major, minor = (int(x) for x in v.split("."))
    return "%d.%d" % (major, minor - 1) if minor > 0 else "%d.9" % (major - 1)


def evidence_row(uc, item_id, status, window, as_of, rng_):
    """One evidence row for a filed item. status decides which defect, if any, the row carries."""
    version = uc["deployed_version"]
    unit = rng_.choice(SECOND_LINE) if INDEPENDENT[item_id] or rng_.random() < 0.2 else uc["developer_unit"]
    cutoff = add_months(as_of, -window)
    date = as_of - dt.timedelta(days=rng_.randint(20, window * 28 - 20))
    reaffirmed = ""
    if status == "reaffirmed":
        date = cutoff - dt.timedelta(days=rng_.randint(60, 600))
        reaffirmed = as_of - dt.timedelta(days=rng_.randint(10, window * 28 - 20))
    elif status == "boundary":
        date = cutoff
    elif status == "stale":
        date = cutoff - dt.timedelta(days=rng_.randint(1, 540))
    elif status == "wrong_version":
        version = older_version(version)
    elif status == "not_independent":
        unit = uc["developer_unit"]
    return {"use_case_id": uc["use_case_id"], "item_id": item_id, "ref": "DOC-%d" % rng_.randint(1000, 9999),
            "prepared_by_unit": unit, "covers_version": version, "evidence_date": date.isoformat(),
            "reaffirmed_date": reaffirmed.isoformat() if reaffirmed else ""}


def write_csv(name, header, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


USE_CASE_COLUMNS = ["use_case_id", "title", "model_type", "vendor_model", "customer_facing", "decision_autonomy",
                    "data_class", "regulatory_scope", "financial_exposure_band", "developer_unit",
                    "deployed_version", "declared_tier"]
EVIDENCE_COLUMNS = ["use_case_id", "item_id", "ref", "prepared_by_unit", "covers_version", "evidence_date",
                    "reaffirmed_date"]


def build():
    use_cases, evidence, truth_tier, truth_ev = [], [], [], []
    item_order = [p[0] for p in PLAN]
    for i in range(1, N_USE_CASES + 1):
        uid = "UC-%03d" % i
        mt = rng.choices(MODEL_TYPES, MODEL_W)[0]
        vw = [0.15, 0.20, 0.65] if mt in ("generative", "agentic") else [0.50, 0.15, 0.35]
        true_vendor = rng.choices(["none", "self_hosted", "vendor_api"], vw)[0]
        cf = "yes" if rng.random() < 0.40 else "no"
        aut = rng.choices(["advisory", "assisted", "automated"], [0.40, 0.40, 0.20])[0]
        cls = rng.choices(CLASS_ORDER, [0.10, 0.30, 0.35, 0.25])[0]
        reg = rng.choices(list(PTS_REG), [0.30, 0.25, 0.15, 0.15, 0.15])[0]
        exp = rng.choices(list(PTS_EXPOSURE), [0.30, 0.35, 0.25, 0.10])[0]
        true_tier = tier_of(points(cf, aut, cls, true_vendor, reg, exp))
        form_vendor = "none" if true_vendor != "none" and rng.random() < P_VENDOR_OMIT else true_vendor
        form_cls = CLASS_ORDER[CLASS_ORDER.index(cls) - 1] if cls != "public" and rng.random() < P_CLASS_UNDER else cls
        form_tier = tier_of(points(cf, aut, form_cls, form_vendor, reg, exp))
        r = rng.random()
        declared = form_tier - 1 if r < P_SHADE_DOWN and form_tier > 1 else \
            form_tier + 1 if r > 1 - P_SHADE_UP and form_tier < 4 else form_tier
        dev = rng.choice(DEV_UNITS)
        uc = {"use_case_id": uid, "title": "%s (%s)" % (rng.choice(STEMS[mt]), dev), "model_type": mt,
              "vendor_model": form_vendor, "customer_facing": cf, "decision_autonomy": aut, "data_class": form_cls,
              "regulatory_scope": reg, "financial_exposure_band": exp, "developer_unit": dev,
              "deployed_version": "%d.%d" % (rng.randint(1, 3), rng.randint(0, 4)), "declared_tier": declared}
        use_cases.append(uc)
        truth_tier.append([uid, true_tier, true_vendor, cls])
        true_plan = owed(mt, true_vendor, true_tier)
        known = set(owed(mt, form_vendor, declared))
        rows = {}
        for item_id in item_order:
            if item_id in true_plan:
                if rng.random() >= (P_FILE_KNOWN if item_id in known else P_FILE_UNKNOWN):
                    truth_ev.append([uid, item_id, 1, "missing"])
                    continue
                status = rng.choices(STATUSES, STATUS_W)[0]
                if status == "not_independent" and not INDEPENDENT[item_id]:
                    status = "ok"
                rows[item_id] = evidence_row(uc, item_id, status, WINDOW[true_tier], AS_OF, rng)
                truth_ev.append([uid, item_id, 1, status])
            elif item_id.startswith("CH") and rng.random() < P_FILE_EXTRA:
                rows[item_id] = evidence_row(uc, item_id, "ok", WINDOW[true_tier], AS_OF, rng)
                truth_ev.append([uid, item_id, 0, "extra"])
        evidence.extend(rows[k] for k in item_order if k in rows)
    return use_cases, evidence, truth_tier, truth_ev


def example():
    """Six use cases written by hand (with fixed dates) for `challenge_pack.py --demo`."""
    specs = [
        ("EX-01", "Branch cash demand forecast", "statistical", "none", "no", "advisory", "internal", "none",
         "lt_1m", "Treasury", "2.1", 1, {}),
        ("EX-02", "Merchant risk scoring", "ml", "vendor_api", "no", "assisted", "confidential", "aml",
         "1m_10m", "Cards", "1.3", 2,
         {"CH08": {"evidence_date": "2025-02-11"}, "CH09": {"evidence_date": "2024-09-05", "reaffirmed_date": "2026-03-12"}}),
        ("EX-03", "Complaint summarisation assistant", "generative", "vendor_api", "no", "advisory", "confidential",
         "privacy", "lt_1m", "Digital Channels", "1.0", 2, {}),
        ("EX-04", "Sanctions list screening rules", "rules", "none", "no", "automated", "restricted", "aml",
         "10m_50m", "Payments Operations", "3.2", 3, {}),
        ("EX-05", "Payment exception resolution agent", "agentic", "vendor_api", "yes", "automated", "restricted",
         "udaap", "gt_50m", "Payments Operations", "1.1", 4, {}),
        ("EX-06", "Overdraft fee waiver rules", "rules", "none", "yes", "advisory", "internal", "none", "lt_1m",
         "Retail Lending", "2.0", 1, {}),
    ]
    ucs, ev = [], []
    for uid, title, mt, ven, cf, aut, cls, reg, exp, dev, ver, declared, overrides in specs:
        ucs.append({"use_case_id": uid, "title": title, "model_type": mt, "vendor_model": ven, "customer_facing": cf,
                    "decision_autonomy": aut, "data_class": cls, "regulatory_scope": reg,
                    "financial_exposure_band": exp, "developer_unit": dev, "deployed_version": ver,
                    "declared_tier": declared})
        tier = max(declared, tier_of(points(cf, aut, cls, ven, reg, exp)))
        for k, item_id in enumerate(owed(mt, ven, tier)):
            row = {"use_case_id": uid, "item_id": item_id, "ref": "DOC-%s-%s" % (uid[-2:], item_id),
                   "prepared_by_unit": SECOND_LINE[k % 3] if INDEPENDENT[item_id] else dev,
                   "covers_version": ver, "evidence_date": (AS_OF - dt.timedelta(days=15 * (k + 1))).isoformat(),
                   "reaffirmed_date": ""}
            row.update(overrides.get(item_id, {}))
            ev.append(row)
    return ucs, ev


def main():
    ucs, ev, tt, te = build()
    write_csv("use_cases.csv", USE_CASE_COLUMNS, [[u[c] for c in USE_CASE_COLUMNS] for u in ucs])
    write_csv("evidence.csv", EVIDENCE_COLUMNS, [[e[c] for c in EVIDENCE_COLUMNS] for e in ev])
    write_csv("truth_tier.csv", ["use_case_id", "true_tier", "true_vendor_model", "true_data_class"], tt)
    write_csv("truth_evidence.csv", ["use_case_id", "item_id", "owed", "planted_status"], te)
    items = {p[0]: p for p in PLAN}
    write_csv("plan_items.csv", ["item_id", "min_tier", "independent", "overlay"], [list(items[k]) for k in items])
    write_csv("plan_tiers.csv", ["tier", "depth", "window_months"], [[t, DEPTH[t], WINDOW[t]] for t in sorted(WINDOW)])
    eu, ee = example()
    write_csv("example_use_cases.csv", USE_CASE_COLUMNS, [[u[c] for c in USE_CASE_COLUMNS] for u in eu])
    write_csv("example_evidence.csv", EVIDENCE_COLUMNS, [[e[c] for c in EVIDENCE_COLUMNS] for e in ee])
    counts = {}
    for _u, _i, o, s in te:
        counts[(o, s)] = counts.get((o, s), 0) + 1
    print("use cases %d, evidence rows %d, truth rows %d" % (len(ucs), len(ev), len(te)))
    print("planted: " + ", ".join("%s%s %d" % ("" if o else "not owed ", s, n) for (o, s), n in sorted(counts.items())))


if __name__ == "__main__":
    main()
