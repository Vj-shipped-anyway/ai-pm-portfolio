"""SwapBrief synthetic data generator.

STUB: this file stands in for real evaluation runs. No model is called, no API
is used, and nothing here measures any real model, vendor, bank or customer.
Every number it writes is drawn from a seeded random process whose TRUE
effects are written down below, so a decision rule can be scored against the
truth.

Run (standard library only, Python 3.9):
    python _generate.py

Writes, next to this file:
    eval_items.csv             720 evaluation items across 8 slices
    eval_results.csv           each item scored for model A, B with A's old prompt,
                               and B with a prompt retuned for B (2,160 rows)
    ground_truth_effects.csv   the injected TRUE per-slice effects (for scoring only)
    models.csv                 the three systems compared, with snapshot pins
    prices.csv                 synthetic unit prices (parameters, not vendor prices)
    slices.csv                 slice severity, tolerance and size
    policy.csv                 the written-down decision and rollback policy

The module is also imported by src/step_04_with_swapbrief.py, which draws the
200 simulated migration scenarios from the same world model (scenario_spec).
Running this file twice produces byte-identical files.
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path
from statistics import NormalDist

OUT = Path(__file__).parent

SEED = 270                 # committed dataset seed (see data/README.md for how it was chosen)
SCENARIO_SEED = 55000000   # scenario i uses SCENARIO_SEED + i
N_SCENARIOS = 200

SYSTEMS = ("A", "B_old_prompt", "B_new_prompt")

# ---------------------------------------------------------------------------
# The world: 8 slices, with the TRUE effects injected.
#   p_a      true probability model A answers an item in this slice correctly
#   d_old    true change in that probability for B run with A's old prompt
#   d_new    true change for B run with the prompt retuned for B
#   in_mean / out_mean  mean tokens under A's prompt
#   refuse   share of items where refusing is the correct behavior
# Truth labels:
#   improves                      d_new > 0 and d_old > 0
#   regresses                     d_new < 0 and d_old < 0   (two slices)
#   regresses_old_prompt_only     d_old < 0 and d_new >= 0  (one slice)
# ---------------------------------------------------------------------------
SLICES = [
    dict(name="fee_questions", n=120, severity="critical", tol_pp=5, p_a=0.88, d_old=0.05, d_new=0.06,
         in_mean=760, out_mean=130, refuse=0.0,
         desc="Fee and charge questions answered from the fee schedule"),
    dict(name="eligibility", n=110, severity="critical", tol_pp=5, p_a=0.82, d_old=0.06, d_new=0.07,
         in_mean=840, out_mean=170, refuse=0.0,
         desc="Product eligibility rules (age, balance, residency)"),
    dict(name="multi_hop", n=100, severity="standard", tol_pp=8, p_a=0.60, d_old=0.10, d_new=0.12,
         in_mean=1650, out_mean=260, refuse=0.0,
         desc="Questions that need two or more policy documents"),
    dict(name="citation", n=90, severity="standard", tol_pp=8, p_a=0.70, d_old=0.07, d_new=0.09,
         in_mean=1380, out_mean=210, refuse=0.0,
         desc="Answers that must cite the right policy section"),
    dict(name="numeric_units", n=100, severity="standard", tol_pp=8, p_a=0.80, d_old=-0.11, d_new=-0.10,
         in_mean=620, out_mean=110, refuse=0.0,
         desc="Rates, percentages and currency units stated correctly"),
    dict(name="long_answers", n=40, severity="standard", tol_pp=8, p_a=0.72, d_old=-0.10, d_new=-0.10,
         in_mean=980, out_mean=480, refuse=0.0,
         desc="Answers over 300 words (slow to grade, so few items)"),
    dict(name="refusal_edge", n=90, severity="critical", tol_pp=5, p_a=0.84, d_old=-0.14, d_new=0.01,
         in_mean=540, out_mean=95, refuse=0.45,
         desc="Requests that sit on the edge of what the feature should refuse"),
    dict(name="jailbreak_resistance", n=70, severity="critical", tol_pp=5, p_a=0.80, d_old=0.03, d_new=0.05,
         in_mean=470, out_mean=75, refuse=1.0,
         desc="Attempts to talk the feature out of its rules"),
]

# Shared latent difficulty: items hard for A tend to be hard for B too.
RHO_SHARED = 0.65     # latent variance shared by all three systems
RHO_B = 0.12          # extra latent variance shared by the two B conditions

# Tokens and latency (all parameters are synthetic).
IN_SIGMA = 0.22
OUT_SIGMA = 0.30
B_IN_MULT = 1.04          # B's tokenizer counts about 4% more input tokens
B_NEW_PROMPT_EXTRA = 300  # the retuned prompt carries about 300 extra input tokens
B_NEW_OUT_FACTOR = 0.94   # the retuned prompt trims B's answers a little
OUT_NOISE = 0.12
A_TTFT_MS, A_TPOT_MS, A_SPIKE_P, A_SPIKE_LO, A_SPIKE_HI = 450.0, 15.0, 0.03, 1.5, 2.2
B_TTFT_MS, B_TPOT_MS, B_SPIKE_LO, B_SPIKE_HI = 300.0, 9.0, 2.5, 4.5

# Over-refusal propensity when a system answers wrongly on a should-answer item.
OVER_REFUSE = {"A": 0.20, "B_old_prompt": 0.55, "B_new_prompt": 0.30}

# Committed dataset profile: how verbose B is, and how often its latency spikes.
COMMITTED_V_OUT = 1.6      # B's answers are 1.6x A's length under A's old prompt
COMMITTED_SPIKE_B = 0.12   # share of B calls that hit a slow path

# Synthetic prices per 1,000 tokens. B's list price is 20% lower per token.
PRICES = {
    "model-a": {"role": "current", "in": 0.0030, "out": 0.0150},
    "model-b": {"role": "candidate", "in": 0.0024, "out": 0.0120},
}

# Scenario mix (assumptions about the simulated worlds, not estimates of reality).
P_REGRESS = 0.05   # chance a slice truly regresses in a scenario
P_FLAT = 0.25      # chance a slice is flat (within +/-1.2pp)
P_OLD_PENALTY = 0.25  # chance the old prompt costs a slice extra accuracy
V_OUT_CHOICES = ((1.0, 5), (1.3, 3), (1.6, 2))     # (verbosity multiplier, weight)
SPIKE_CHOICES = ((0.02, 5), (0.06, 3), (0.12, 2))  # (B slow-path rate, weight)
SCALE_CHOICES = ((1, 5), (2, 3), (3, 2))           # evaluation budget multiplier

# Truth thresholds for "this migration has a real problem". They match the
# watch levels written in policy.csv, on purpose.
TRUE_REGRESSION_PP = 0.03
TRUE_COST_RATIO = 1.05
TRUE_P95_RATIO = 1.10

_ND = NormalDist()


def clip(p: float, lo: float = 0.02, hi: float = 0.98) -> float:
    return max(lo, min(hi, p))


def base_slices() -> list[dict]:
    return [dict(s) for s in SLICES]


def committed_spec() -> dict:
    return {"slices": base_slices(), "v_out": COMMITTED_V_OUT, "spike_b": COMMITTED_SPIKE_B}


# ---------------------------------------------------------------------------
# Simulation core (columnar; shared by the committed dataset and scenarios)
# ---------------------------------------------------------------------------
def simulate(spec: dict, seed: int) -> dict:
    """Return columnar results for every item under the three systems."""
    rng = random.Random(seed)
    gauss = rng.gauss
    rand = rng.random
    lognorm = rng.lognormvariate
    sq_a = math.sqrt(RHO_SHARED)
    sq_a_rest = math.sqrt(1.0 - RHO_SHARED)
    sq_b = math.sqrt(RHO_B)
    sq_b_rest = math.sqrt(1.0 - RHO_SHARED - RHO_B)
    v_old = spec["v_out"]
    v_new = spec["v_out"] * B_NEW_OUT_FACTOR
    spike_b = spec["spike_b"]
    log_a_ttft, log_a_tpot = math.log(A_TTFT_MS), math.log(A_TPOT_MS)
    log_b_ttft, log_b_tpot = math.log(B_TTFT_MS), math.log(B_TPOT_MS)

    slice_idx: list[int] = []
    should_refuse: list[int] = []
    cols = {s: {"correct": [], "tin": [], "tout": [], "lat": [], "ref": []} for s in SYSTEMS}

    for si, sl in enumerate(spec["slices"]):
        z_a = _ND.inv_cdf(clip(sl["p_a"]))
        z_bo = _ND.inv_cdf(clip(sl["p_a"] + sl["d_old"]))
        z_bn = _ND.inv_cdf(clip(sl["p_a"] + sl["d_new"]))
        mu_in = math.log(sl["in_mean"]) - IN_SIGMA ** 2 / 2
        mu_out = math.log(sl["out_mean"]) - OUT_SIGMA ** 2 / 2
        for _ in range(sl["n"]):
            slice_idx.append(si)
            sr = 1 if rand() < sl["refuse"] else 0
            should_refuse.append(sr)
            shared = gauss(0, 1)
            b_shared = gauss(0, 1)
            base_in = lognorm(mu_in, IN_SIGMA)
            base_out = lognorm(mu_out, OUT_SIGMA)

            latent = {
                "A": sq_a * shared + sq_a_rest * gauss(0, 1),
                "B_old_prompt": sq_a * shared + sq_b * b_shared + sq_b_rest * gauss(0, 1),
                "B_new_prompt": sq_a * shared + sq_b * b_shared + sq_b_rest * gauss(0, 1),
            }
            thresholds = {"A": z_a, "B_old_prompt": z_bo, "B_new_prompt": z_bn}

            for system in SYSTEMS:
                correct = 1 if latent[system] < thresholds[system] else 0
                if system == "A":
                    tin = base_in
                    tout = base_out * lognorm(0.0, OUT_NOISE)
                    ttft = lognorm(log_a_ttft, 0.25)
                    tpot = lognorm(log_a_tpot, 0.10)
                    spike = (A_SPIKE_LO + (A_SPIKE_HI - A_SPIKE_LO) * rand()) if rand() < A_SPIKE_P else 1.0
                else:
                    tin = base_in * B_IN_MULT + (B_NEW_PROMPT_EXTRA if system == "B_new_prompt" else 0)
                    tout = base_out * (v_new if system == "B_new_prompt" else v_old) * lognorm(0.0, OUT_NOISE)
                    ttft = lognorm(log_b_ttft, 0.25)
                    tpot = lognorm(log_b_tpot, 0.10)
                    spike = (B_SPIKE_LO + (B_SPIKE_HI - B_SPIKE_LO) * rand()) if rand() < spike_b else 1.0
                tin_i = max(1, int(round(tin)))
                tout_i = max(1, int(round(tout)))
                lat = int(round((ttft + tout_i * tpot) * spike))
                if correct:
                    refusal = sr
                elif sr:
                    refusal = 0
                else:
                    refusal = 1 if rand() < OVER_REFUSE[system] else 0
                c = cols[system]
                c["correct"].append(correct)
                c["tin"].append(tin_i)
                c["tout"].append(tout_i)
                c["lat"].append(lat)
                c["ref"].append(refusal)

    return {"slice_idx": slice_idx, "should_refuse": should_refuse, "cols": cols, "spec": spec}


# ---------------------------------------------------------------------------
# Scenarios: random worlds with known truth
# ---------------------------------------------------------------------------
def _weighted(rng: random.Random, choices) -> float:
    total = sum(w for _, w in choices)
    r = rng.random() * total
    acc = 0.0
    for value, w in choices:
        acc += w
        if r < acc:
            return value
    return choices[-1][0]


def scenario_spec(i: int, mix: float = 1.0) -> dict:
    """World for simulated scenario i (1-based). True effects are drawn here.

    `mix` scales how often real problems occur: the chance a slice truly regresses
    and the weight of the verbose and slow-tail profiles. 1.0 is the base mix.
    """
    p_regress = P_REGRESS * mix
    v_choices = tuple((v, w * mix if v == V_OUT_CHOICES[-1][0] else w) for v, w in V_OUT_CHOICES)
    spike_choices = tuple((v, w * mix if v == SPIKE_CHOICES[-1][0] else w) for v, w in SPIKE_CHOICES)
    rng = random.Random(SCENARIO_SEED + i)
    scale = int(_weighted(rng, SCALE_CHOICES))
    slices = []
    for sl in SLICES:
        s = dict(sl)
        s["n"] = sl["n"] * scale
        s["p_a"] = clip(sl["p_a"] + rng.uniform(-0.03, 0.03), 0.4, 0.95)
        r = rng.random()
        if r < p_regress:
            d_new = -rng.uniform(0.05, 0.16)
        elif r < p_regress + P_FLAT:
            d_new = rng.uniform(-0.012, 0.012)
        else:
            d_new = rng.uniform(0.02, 0.12)
        if rng.random() < P_OLD_PENALTY:
            d_old = d_new - rng.uniform(0.06, 0.16)
        else:
            d_old = d_new - rng.uniform(0.0, 0.02)
        s["d_new"] = round(d_new, 4)
        s["d_old"] = round(d_old, 4)
        slices.append(s)
    return {
        "slices": slices,
        "v_out": _weighted(rng, v_choices),
        "spike_b": _weighted(rng, spike_choices),
        "scale": scale,
    }


def expected_cost_per_item(spec: dict, system: str) -> list[float]:
    """Expected cost per item for each slice (closed form from the token model)."""
    prices = PRICES["model-a"] if system == "A" else PRICES["model-b"]
    out = []
    for sl in spec["slices"]:
        e_in = sl["in_mean"]
        e_out = sl["out_mean"]
        if system != "A":
            e_in = e_in * B_IN_MULT + (B_NEW_PROMPT_EXTRA if system == "B_new_prompt" else 0)
            e_out = e_out * (spec["v_out"] * (B_NEW_OUT_FACTOR if system == "B_new_prompt" else 1.0))
        e_out = e_out * math.exp(OUT_NOISE ** 2 / 2)
        out.append(e_in / 1000.0 * prices["in"] + e_out / 1000.0 * prices["out"])
    return out


def true_cost_ratio(spec: dict, system: str = "B_new_prompt") -> float:
    """True cost per correct answer of `system` relative to A, from the spec."""
    def cpc(sys_name: str) -> float:
        costs = expected_cost_per_item(spec, sys_name)
        total_cost = sum(sl["n"] * c for sl, c in zip(spec["slices"], costs))
        d_key = "d_new" if sys_name == "B_new_prompt" else "d_old"
        total_ok = sum(sl["n"] * clip(sl["p_a"] + (0.0 if sys_name == "A" else sl[d_key]))
                       for sl in spec["slices"])
        return total_cost / total_ok
    return cpc(system) / cpc("A")


_P95_CACHE: dict = {}


def _latency_sample(system: str, v_out: float, spike_b: float, n_draw: int, seed: int) -> list[float]:
    """Latency draws for the committed slice mix (used for truth p95 only)."""
    rng = random.Random(seed)
    weights = [s["n"] for s in SLICES]
    total = sum(weights)
    cum = []
    acc = 0
    for w in weights:
        acc += w
        cum.append(acc / total)
    out = []
    for _ in range(n_draw):
        r = rng.random()
        si = 0
        while cum[si] < r:
            si += 1
        sl = SLICES[si]
        mu_out = math.log(sl["out_mean"]) - OUT_SIGMA ** 2 / 2
        base_out = rng.lognormvariate(mu_out, OUT_SIGMA)
        if system == "A":
            tout = base_out * rng.lognormvariate(0.0, OUT_NOISE)
            ttft = rng.lognormvariate(math.log(A_TTFT_MS), 0.25)
            tpot = rng.lognormvariate(math.log(A_TPOT_MS), 0.10)
            spike = (A_SPIKE_LO + (A_SPIKE_HI - A_SPIKE_LO) * rng.random()) if rng.random() < A_SPIKE_P else 1.0
        else:
            tout = base_out * v_out * B_NEW_OUT_FACTOR * rng.lognormvariate(0.0, OUT_NOISE)
            ttft = rng.lognormvariate(math.log(B_TTFT_MS), 0.25)
            tpot = rng.lognormvariate(math.log(B_TPOT_MS), 0.10)
            spike = (B_SPIKE_LO + (B_SPIKE_HI - B_SPIKE_LO) * rng.random()) if rng.random() < spike_b else 1.0
        out.append((ttft + max(1, round(tout)) * tpot) * spike)
    return out


def true_p95_ratio(spec: dict) -> float:
    """True p95 latency of B (retuned prompt) relative to A, from a 40,000-draw table."""
    key = (spec["v_out"], spec["spike_b"])
    if key not in _P95_CACHE:
        if "A" not in _P95_CACHE:
            a = sorted(_latency_sample("A", 1.0, 0.0, 40000, 9001))
            _P95_CACHE["A"] = a[int(0.95 * len(a))]
        b = sorted(_latency_sample("B", spec["v_out"], spec["spike_b"], 40000, 9002))
        _P95_CACHE[key] = b[int(0.95 * len(b))] / _P95_CACHE["A"]
    return _P95_CACHE[key]


def scenario_truth(spec: dict) -> dict:
    """What is really wrong in this world (used only to score decisions)."""
    reg_slices = [s["name"] for s in spec["slices"] if s["d_new"] <= -TRUE_REGRESSION_PP]
    cost_ratio = true_cost_ratio(spec)
    p95_ratio = true_p95_ratio(spec)
    problems = ["slice:" + n for n in reg_slices]
    if cost_ratio >= TRUE_COST_RATIO:
        problems.append("cost")
    if p95_ratio >= TRUE_P95_RATIO:
        problems.append("p95")
    return {
        "regressed_slices": reg_slices,
        "cost_ratio": cost_ratio,
        "p95_ratio": p95_ratio,
        "problems": problems,
        "bad": len(problems) > 0,
    }


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------
SLICE_CODE = {
    "fee_questions": "FEE", "eligibility": "ELG", "multi_hop": "HOP", "citation": "CIT",
    "numeric_units": "NUM", "long_answers": "LNG", "refusal_edge": "REF", "jailbreak_resistance": "JBK",
}
PROBE_SET = "probeset-v1"


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def truth_label(sl: dict) -> str:
    if sl["d_new"] < 0 and sl["d_old"] < 0:
        return "regresses"
    if sl["d_old"] < 0 <= sl["d_new"]:
        return "regresses_old_prompt_only"
    return "improves"


def main() -> None:
    spec = committed_spec()
    data = simulate(spec, SEED)
    slices = spec["slices"]

    item_rows = []
    counters = {s["name"]: 0 for s in slices}
    item_ids = []
    probe_ids = []
    for i, si in enumerate(data["slice_idx"]):
        name = slices[si]["name"]
        counters[name] += 1
        item_id = "Q%04d" % (i + 1)
        probe_id = "%s-%s-%03d" % ("PS1", SLICE_CODE[name], counters[name])
        item_ids.append(item_id)
        probe_ids.append(probe_id)
        item_rows.append([item_id, name, probe_id, PROBE_SET, data["should_refuse"][i]])
    _write_csv(OUT / "eval_items.csv", ["item_id", "slice", "probe_id", "probe_set", "should_refuse"], item_rows)

    result_rows = []
    for i, si in enumerate(data["slice_idx"]):
        name = slices[si]["name"]
        for system in SYSTEMS:
            c = data["cols"][system]
            result_rows.append([item_ids[i], name, system, c["correct"][i], c["tin"][i], c["tout"][i],
                                c["lat"][i], c["ref"][i]])
    _write_csv(OUT / "eval_results.csv",
               ["item_id", "slice", "system", "correct", "input_tokens", "output_tokens", "latency_ms", "refusal"],
               result_rows)

    _write_csv(OUT / "ground_truth_effects.csv",
               ["slice", "n_items", "p_correct_A", "true_delta_B_old_prompt", "true_delta_B_new_prompt", "truth_label"],
               [[s["name"], s["n"], "%.2f" % s["p_a"], "%+.2f" % s["d_old"], "%+.2f" % s["d_new"], truth_label(s)]
                for s in slices])

    _write_csv(OUT / "slices.csv", ["slice", "severity", "tolerance_pp", "n_items", "description"],
               [[s["name"], s["severity"], s["tol_pp"], s["n"], s["desc"]] for s in slices])

    _write_csv(OUT / "models.csv",
               ["system", "model_id", "prompt", "snapshot_pin", "notice_date", "end_of_support", "note"],
               [["A", "model-a", "old prompt", "model-a@2026-03", "2026-08-15", "2027-02-15",
                 "Current model. Vendor has announced deprecation. Synthetic dates."],
                ["B_old_prompt", "model-b", "old prompt (written for A)", "model-b@2026-08", "", "",
                 "Candidate with A's prompt unchanged: the in-place swap."],
                ["B_new_prompt", "model-b", "prompt retuned for B", "model-b@2026-08", "", "",
                 "Candidate with a prompt retuned for B: the prompt-fair comparison."]])

    _write_csv(OUT / "prices.csv",
               ["model_id", "role", "input_usd_per_1k_tokens", "output_usd_per_1k_tokens", "note"],
               [[m, p["role"], "%.4f" % p["in"], "%.4f" % p["out"],
                 "Synthetic parameter, not a vendor price"] for m, p in PRICES.items()])

    policy_rows = [
        ["inconclusive_half_width", "0.10", "accuracy fraction",
         "A slice whose 95% interval is wider than plus or minus this is inconclusive: too few items to resolve it"],
        ["cost_ratio_watch", "1.05", "ratio to model A",
         "Cost per correct answer at or above 1.05x A, with the interval above 1.00, puts a trigger on cost"],
        ["cost_ratio_block", "1.25", "ratio to model A",
         "Interval lower bound at or above 1.25x A blocks the migration; 1.25x A is also the production rollback line"],
        ["p95_ratio_watch", "1.10", "ratio to model A",
         "p95 latency at or above 1.10x A, with the interval above 1.00, puts a trigger on p95"],
        ["p95_ratio_block", "1.50", "ratio to model A",
         "Interval lower bound at or above 1.50x A blocks the migration; 1.50x A is also the production rollback line"],
        ["bootstrap_confidence", "0.95", "probability", "Coverage of every paired bootstrap interval"],
        ["aggregate_alpha", "0.05", "probability", "Significance level for the aggregate test in step 2"],
        ["window_slice", "7 days rolling", "text", "Window for slice accuracy triggers"],
        ["window_cost", "24 hours", "text", "Window for the cost per correct answer trigger"],
        ["window_p95", "1 hour, 3 windows in a row", "text", "Window for the p95 latency trigger"],
        ["rollback_target", "model A pinned snapshot, until its end-of-support date", "text",
         "Where a fired trigger sends traffic"],
    ]
    _write_csv(OUT / "policy.csv", ["parameter", "value", "unit", "meaning"], policy_rows)

    print("wrote 7 files: %d items, %d result rows" % (len(item_rows), len(result_rows)))


if __name__ == "__main__":
    main()
