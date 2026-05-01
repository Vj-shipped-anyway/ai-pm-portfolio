"""
Step 1 — Before continuous monitoring: the quarterly Word-doc attestation.

This is what most US banks still do under SR 11-7 today. A model is deployed
in Q1, the model owner signs a 30-page attestation in Word, the document
goes into a shared drive, and nobody opens it again until Q4 audit prep.

If the model decays in week three of Q1, the bank carries the decay for the
remaining ~24 weeks before anyone looks. That's not negligence — it's the
direct consequence of the tooling, which is point-in-time by design.

This script does NOT do drift math. That's the whole point. It produces the
same artifact the bank produces today — a static attestation summary — to
make visible what's invisible in this regime.

Run:
    python step_01_quarterly_attestation.py

Output: prints the attestation summary, writes a CSV of fleet attestation
state to src/out/step_01_attestations.csv.
"""

import csv
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


def days_since(iso_date: str, today: date) -> int:
    return (today - datetime.strptime(iso_date, "%Y-%m-%d").date()).days


def render_attestation_doc(model: dict, today: date) -> str:
    """The dummy 30-page attestation, compressed to a Step-1 summary block.

    In the real world this is a Word doc with sections for: model purpose,
    development methodology, training data lineage, validation results, fair
    lending, ongoing monitoring plan (one paragraph), and committee sign-off.
    The 'ongoing monitoring plan' is almost always a single line that says
    'monthly PSI review by model owner' — and almost never enforced.
    """
    age = days_since(model["last_attested"], today)
    return (
        "----------------------------------------------------------------\n"
        f"  QUARTERLY MODEL ATTESTATION — {model['name']} ({model['model_id']})\n"
        "----------------------------------------------------------------\n"
        f"  Model tier:           {model['tier']}\n"
        f"  Family:               {model['family']}\n"
        f"  Owner (Line 1):       {model['owner']}\n"
        f"  Vendor / snapshot:    {model['vendor']} / {model['snapshot_id']}\n"
        f"  Deployed:             {model['deployed_date']}\n"
        f"  Last attested:        {model['last_attested']} ({age} days ago)\n"
        f"  Ongoing monitoring:   'Monthly PSI review by model owner.'\n"
        f"  Validator sign-off:   on file (Word doc, p. 28)\n"
        f"  Next attestation:     scheduled — quarterly\n"
        "----------------------------------------------------------------"
    )


def main():
    today = date(2026, 4, 28)  # walkthrough cut date

    models_path = DATA_DIR / "models.csv"
    out_path = OUT_DIR / "step_01_attestations.csv"

    print("\n" + "=" * 80)
    print("Step 1 — Before continuous monitoring: quarterly Word-doc attestation")
    print("=" * 80 + "\n")
    print("This is the world MRM lives in today. Eight production models, eight")
    print("attestations, all signed off in January, none re-examined until April.\n")

    rows_out = []
    stale_count = 0
    with open(models_path) as f:
        for model in csv.DictReader(f):
            doc = render_attestation_doc(model, today)
            print(doc)
            print()
            age = days_since(model["last_attested"], today)
            stale = age > 30
            if stale:
                stale_count += 1
            rows_out.append({
                "model_id": model["model_id"],
                "name": model["name"],
                "tier": model["tier"],
                "last_attested": model["last_attested"],
                "days_since_attestation": age,
                "monitoring_signal_in_window": "none — quarterly review only",
                "stale_over_30d": stale,
            })

    with open(out_path, "w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows_out[0].keys()))
        writer.writeheader()
        for r in rows_out:
            writer.writerow(r)

    print("=" * 80)
    print("Summary — what this regime gives you")
    print("=" * 80)
    print(f"  Models in fleet:                          {len(rows_out)}")
    print(f"  Models attested in the last 30 days:      {len(rows_out) - stale_count}")
    print(f"  Models attested >30 days ago:             {stale_count}")
    print(f"  Models with continuous monitoring signal: 0  <-- the bleed")
    print(f"  Median days since last attestation:       "
          f"{sorted([r['days_since_attestation'] for r in rows_out])[len(rows_out)//2]}")
    print()
    print("Reading: every model in this fleet has been operating without a")
    print("monitored signal for three months or more. If credit_pd_v3 started")
    print("decaying in early February (Day 30 in the inference logs), nobody")
    print("would know until the Q2 review at earliest. That's the structural")
    print("blindness the rest of this walkthrough is here to fix.")
    print()
    print(f"Wrote: {out_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
