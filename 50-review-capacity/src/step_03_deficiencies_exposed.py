"""Step 3 - Where each half of the fix fails when used alone, and what is left over.

The tool changes Erlang C in two ways:
  variability only   scale the tail of the wait by the measured spread of handling times and arrival gaps
  batch only         drain the cases that land at open as a backlog instead of averaging them in
Each is scored on its own against the same replay. KNOWN LIMIT, left in on purpose: the spread of the gaps
between arrivals does not see arrivals that come in busy and quiet spells, so a bursty queue is still
staffed one reviewer short, in step 4 as well. This step prints the measurement that shows why.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
import statistics

from common import load_world, score
from review_capacity import required_seats

world = load_world()
variants = {"erlang_c": (False, False), "variability_only": (True, False), "batch_only": (False, True), "both": (True, True)}
seats = {name: {q["queue_id"]: required_seats(q, *flags) for q in world} for name, flags in variants.items()}
scores = {name: score(world, seats[name]) for name in variants}

print("STEP 3 - each half alone")
for name in ("erlang_c", "variability_only", "batch_only"):
    s = scores[name]
    print(f"  {name:<17} matches the true number: {s['exact']:>2} of {s['queues']}; too few: {len(s['under'])}; too many: {len(s['over'])}; "
          f"meets both limits on the replay: {s['meets']}")


def closer(name):
    """Queues where `name` lands nearer the true number than Erlang C, and queues where it lands farther."""
    better = [q for q in world if abs(seats[name][q["queue_id"]] - q["true_seats"]) < abs(seats["erlang_c"][q["queue_id"]] - q["true_seats"])]
    worse = [q for q in world if abs(seats[name][q["queue_id"]] - q["true_seats"]) > abs(seats["erlang_c"][q["queue_id"]] - q["true_seats"])]
    return better, worse


for name in ("variability_only", "batch_only"):
    better, worse = closer(name)
    print(f"  {name} moves the answer on {len([q for q in world if seats[name][q['queue_id']] != seats['erlang_c'][q['queue_id']]])} queues: "
          f"nearer the truth on {len(better)} ({', '.join(q['queue_id'] for q in better) or 'none'}), "
          f"farther on {len(worse)} ({', '.join(q['queue_id'] for q in worse) or 'none'})")

print("  queue, planted kind, true / Erlang C / variability only / batch only / both")
for q in world:
    k = q["queue_id"]
    print(f"    {k:<32} {q['kind']:<18} {q['true_seats']:>2} / {seats['erlang_c'][k]:>2} / {seats['variability_only'][k]:>2} / "
          f"{seats['batch_only'][k]:>2} / {seats['both'][k]:>2}")

# Known limit: how irregular are the arrivals, as the tool measures them and as hourly counts show them.
print("  KNOWN LIMIT - bursty arrivals")


def hourly_dispersion(q):
    """Variance over mean of the number of live arrivals per hour, over the replayed days."""
    counts = {}
    for c in q["replayed"]:
        if c["channel"] == "live":
            counts[(c["day"], int(c["arrival_min"] // 60))] = counts.get((c["day"], int(c["arrival_min"] // 60)), 0) + 1
    hours = [counts.get((d, h), 0) for d in range(11, 21) for h in range(int(q["hours_open"]))]
    return statistics.pvariance(hours) / statistics.mean(hours)


for k in ("onboarding_review", "card_dispute_wave"):
    q = next(x for x in world if x["queue_id"] == k)
    print(f"    {k}: spread of arrival gaps {q['arrival_cv']:.2f}; hourly arrival counts, variance over mean {hourly_dispersion(q):.2f}")
q = next(x for x in world if x["queue_id"] == "card_dispute_wave")
r = scores["both"]["results"][q["queue_id"]]
print(f"    card_dispute_wave with both parts: {seats['both'][q['queue_id']]} reviewers against {q['true_seats']} needed, "
      f"{100.0 * r['late_share']:.1f}% of cases late against {100.0 * (1 - q['target_share']):.0f}% allowed")
