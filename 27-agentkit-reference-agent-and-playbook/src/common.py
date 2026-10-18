"""Shared helpers for the four step scripts: paths, rounding, a tiny table printer and JSON/CSV writers.
Standard library only."""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
BRIEF_PATH = HERE.parent / "briefs" / "wire_repair_agent_brief.json"
EVENTS_PER_QUARTER_CASES = 1800     # modeled: 600 cases in the 30-day window, 3 windows a quarter, flat volume


def pct(x, nd: int = 1) -> str:
    return "n/a" if x is None else f"{100 * x:.{nd}f}%"


def fnum(x, nd: int = 1) -> str:
    return f"{x:,.{nd}f}"


def quantile(values, q: float) -> float:
    v = sorted(values)
    if not v:
        return 0.0
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def median(values) -> float:
    return statistics.median(values) if values else 0.0


def write_json(name: str, obj) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return p


def write_csv(name: str, header, rows) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow(r)
    return p


def table(rows, header, widths=None) -> str:
    cols = list(zip(*([header] + [[str(c) for c in r] for r in rows]))) if rows else [[h] for h in header]
    widths = widths or [max(len(str(c)) for c in col) for col in cols]
    def fmt(r):
        return "  ".join(str(c).ljust(w) if i == 0 else str(c).rjust(w) for i, (c, w) in enumerate(zip(r, widths)))
    out = [fmt(header), "  ".join("-" * w for w in widths)]
    out += [fmt([str(c) for c in r]) for r in rows]
    return "\n".join(out)
