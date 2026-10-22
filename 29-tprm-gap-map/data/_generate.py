"""Generate the synthetic data for project 29: 60 third-party vendors and a 36-month incident log.

The truth label (a vendor is high risk if it caused at least one material incident) comes from a
simulated incident process, not from the tiering rules in src/. The hazard rates below are my
assumptions, fixed in advance. They are the weakest part of this project: change them and the
printed numbers move. Everything is seeded, so the files are byte-for-byte reproducible.

Run (from data/):  python3 _generate.py
Writes: vendors.csv, incident_log.csv, vendor_truth.csv
"""
import csv
import random

rng = random.Random(29)

TYPES = [("core_processing", 3), ("cloud_hosting", 6), ("compliance_tool", 6), ("fintech_partner", 5),
         ("data_provider", 8), ("ai_enabled_service", 22), ("call_center", 5), ("facilities", 5)]
SHARE = {"core_processing": (40, 90), "cloud_hosting": (20, 70), "compliance_tool": (5, 30), "fintech_partner": (10, 40),
         "data_provider": (5, 35), "ai_enabled_service": (3, 45), "call_center": (3, 15), "facilities": (1, 5)}
OWN_HAZARD = {"core_processing": 0.008, "cloud_hosting": 0.006, "compliance_tool": 0.004, "fintech_partner": 0.006,
              "data_provider": 0.004, "ai_enabled_service": 0.006, "call_center": 0.004, "facilities": 0.002}
UPSTREAM_AI = (["P1", "P2", "P3", "P4"], [0.50, 0.25, 0.15, 0.10])
UPSTREAM_CLOUD = (["C1", "C2", "C3"], [0.50, 0.30, 0.20])
UPSTREAM_OUTAGES = {"P1": 3, "P2": 2, "P3": 2, "P4": 1, "C1": 2, "C2": 1, "C3": 1}   # events in 36 months
MONTHS = 36
MATERIAL_HOURS = 4.0          # an incident is material at 4 or more customer-impact hours
SCALE = 2.0                   # impact hours = duration x share of activity x SCALE


def yn(p):
    return "yes" if rng.random() < p else "no"


def main():
    vendors = []
    n = 0
    for vtype, count in TYPES:
        for _ in range(count):
            n += 1
            lo, hi = SHARE[vtype]
            v = {"vendor_id": f"V{n:03d}", "service_type": vtype, "activity_share_pct": rng.randint(lo, hi),
                 "upstream_provider": "", "model_change_notice_days": "", "trains_on_bank_data": "",
                 "bank_data_retained_days": ""}
            if vtype == "ai_enabled_service":
                v["upstream_provider"] = rng.choices(*UPSTREAM_AI)[0]
                v["model_change_notice_days"] = rng.choices([0, 14, 30, 90], [0.4, 0.2, 0.25, 0.15])[0]
                v["trains_on_bank_data"] = yn(0.25)
                v["bank_data_retained_days"] = rng.choices([0, 30, 365, 9999], [0.2, 0.3, 0.3, 0.2])[0]
            elif vtype == "cloud_hosting":
                v["upstream_provider"] = rng.choices(*UPSTREAM_CLOUD)[0]
            v.update(soc_report=yn(0.80), insurance=yn(0.85), financial_ok=yn(0.90), key_personnel=yn(0.90))
            vendors.append(v)
    rng.shuffle(vendors)
    for i, v in enumerate(vendors, 1):
        v["vendor_id"] = f"V{i:03d}"

    events = {}
    for up, k in UPSTREAM_OUTAGES.items():
        events[up] = [(rng.randint(1, MONTHS), rng.uniform(3, 18)) for _ in range(k)]

    log = []
    for v in vendors:
        share = v["activity_share_pct"] / 100.0
        t = v["service_type"]
        for m in range(1, MONTHS + 1):
            if rng.random() < OWN_HAZARD[t]:
                log.append((v["vendor_id"], m, "own_outage", rng.uniform(2, 12) * share * SCALE))
            if t == "ai_enabled_service":
                if rng.random() < (0.05 if v["model_change_notice_days"] == 0 else 0.012):
                    log.append((v["vendor_id"], m, "silent_model_change", rng.uniform(4, 12) * share / 0.40))
                exposed = v["trains_on_bank_data"] == "yes" or v["bank_data_retained_days"] >= 365
                if rng.random() < (0.025 if exposed else 0.004):
                    log.append((v["vendor_id"], m, "data_exposure", 6.0))
        up = v["upstream_provider"]
        if up:
            for m, dur in events[up]:
                log.append((v["vendor_id"], m, "upstream_outage", dur * share * SCALE))
    log.sort(key=lambda r: (r[1], r[0], r[2]))

    with open("vendors.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(vendors[0]))
        w.writeheader()
        w.writerows(vendors)
    with open("incident_log.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["vendor_id", "month", "cause", "customer_impact_hours", "material"])
        for vid, m, cause, hours in log:
            w.writerow([vid, m, cause, f"{hours:.1f}", "yes" if hours >= MATERIAL_HOURS else "no"])
    truth = {}
    for vid, m, cause, hours in log:
        if hours >= MATERIAL_HOURS:
            truth.setdefault(vid, set()).add(cause)
    with open("vendor_truth.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["vendor_id", "high_risk", "material_causes"])
        for v in vendors:
            c = truth.get(v["vendor_id"], set())
            w.writerow([v["vendor_id"], "yes" if c else "no", ";".join(sorted(c))])
    print(f"wrote {len(vendors)} vendors and {len(log)} incidents; {len(truth)} vendors with a material incident")


if __name__ == "__main__":
    main()
