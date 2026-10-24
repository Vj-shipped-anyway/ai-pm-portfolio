"""kyb_packet_check: compare a model's reading of a business-onboarding packet with the packet's own text.

You give it two things: the text of the packet (what the model was shown) and the model's extraction
as JSON. It prints what does not hold up and a decision, PASS or REVIEW. It never calls a model; the
extraction is an input, so any extractor can sit in front of it.

Three families of check:
  completeness  the details the order recites for each beneficial owner and the control person are present
  arithmetic    the percentages add up, and an entity that holds 25 percent or more has its owners shown
  grounding     each name, percentage and personal detail in the extraction appears on a line of the
                packet text that names the same holder or person

Run:  python3 kyb_packet_check.py --demo
      python3 kyb_packet_check.py check packet.txt extraction.json
Exit: 0 = PASS (or --fail-on never), 1 = REVIEW, 2 = the input could not be read.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

OWNERSHIP_THRESHOLD = 25.0     # percent; the order recites "25 percent or more of the equity interests"
DEFAULT_TOLERANCE = 0.1        # percentage points; an assumption, not from the order (see README)
FAMILIES = ("completeness", "arithmetic", "grounding")
HOLDER_KINDS = ("individual", "entity")
PERSON_FIELDS = (("address", "address"), ("dob", "date of birth"), ("id_last4", "ID number"))
EPS = 1e-9
MAX_BYTES = 5_000_000


class InputError(ValueError):
    """Input that cannot be checked. The command line turns it into exit 2 and a one-line message."""


# ---------------------------------------------------------------- text helpers
def _esc(ch: str) -> str:
    o = ord(ch)
    return "\\x%02x" % o if o < 0x100 else "\\u%04x" % o if o < 0x10000 else "\\U%08x" % o


def clean(text, limit: int = 80) -> str:
    """Untrusted text made safe for one line of output: control characters shown as escapes, long text cut."""
    s = str(text)
    cut = len(s) > limit
    s = "".join(ch if ch.isprintable() else _esc(ch) for ch in s[:limit])
    return s + "..." if cut else s


def fmt_pct(x: float) -> str:
    return ("%.2f" % x).rstrip("0").rstrip(".")


def words(text: str) -> list:
    return re.findall(r"\w+", text.lower())


def name_words(name: str) -> list:
    """Words of a name without single-letter initials, so 'Dana A. Whitfield' and 'Whitfield, Dana' agree."""
    return [w for w in words(name) if len(w) > 1]


def name_key(name: str) -> str:
    return " ".join(sorted(set(name_words(name))))


def finding(family: str, kind: str, subject: str, detail: str) -> dict:
    return {"family": family, "kind": kind, "subject": subject, "detail": detail}


# ---------------------------------------------------------------- reading the extraction
def _text(value, where: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise InputError(f"{where} must be a string")
    return value.strip()


def _number(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{where} must be a number")
    try:
        x = float(value)
    except OverflowError:
        raise InputError(f"{where} is too large") from None
    if not math.isfinite(x):
        raise InputError(f"{where} must be a finite number")
    return x


def _rows(obj: dict, key: str) -> list:
    v = obj.get(key)
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(r, dict) for r in v):
        raise InputError(f"`{key}` must be a list of objects")
    return v


def _record(value, key: str, fields: tuple):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise InputError(f"`{key}` must be an object or null")
    return {f: _text(value.get(f), f"{key}.{f}") for f in fields}


def parse_extraction(obj) -> dict:
    """Validate the shape of an extraction and return it with every text field a string."""
    if not isinstance(obj, dict):
        raise InputError("extraction must be a JSON object")
    if not isinstance(obj.get("holders"), list):
        raise InputError("extraction needs a `holders` list")
    holders = []
    for i, r in enumerate(_rows(obj, "holders")):
        kind = _text(r.get("kind"), f"holders[{i}].kind")
        if kind not in HOLDER_KINDS:
            raise InputError(f"holders[{i}].kind must be individual or entity")
        holders.append({"name": _text(r.get("name"), f"holders[{i}].name"), "kind": kind,
                        "pct": _number(r.get("pct"), f"holders[{i}].pct")})
    lookthrough = [{"entity": _text(r.get("entity"), f"lookthrough[{i}].entity"),
                    "name": _text(r.get("name"), f"lookthrough[{i}].name"),
                    "pct": _number(r.get("pct"), f"lookthrough[{i}].pct")} for i, r in enumerate(_rows(obj, "lookthrough"))]
    people = [{f: _text(r.get(f), f"people[{i}].{f}") for f in ("name", "address", "dob", "id_last4")}
              for i, r in enumerate(_rows(obj, "people"))]
    return {"packet_id": _text(obj.get("packet_id"), "packet_id"), "legal_name": _text(obj.get("legal_name"), "legal_name"),
            "holders": holders, "lookthrough": lookthrough, "people": people,
            "control_person": _record(obj.get("control_person"), "control_person", ("name", "title")),
            "certification": _record(obj.get("certification"), "certification", ("signed_by", "date"))}


# ---------------------------------------------------------------- ownership
def ownership(ex: dict) -> list:
    """[(name, effective percent)] per individual: direct holdings plus one level of look-through."""
    via = {}
    for h in ex["holders"]:
        if h["kind"] == "entity" and name_key(h["name"]):
            via[name_key(h["name"])] = via.get(name_key(h["name"]), 0.0) + h["pct"]
    total = {}

    def add(name: str, pct: float) -> None:
        k = name_key(name)
        if k:
            total.setdefault(k, [name, 0.0])[1] += pct

    for h in ex["holders"]:
        if h["kind"] == "individual":
            add(h["name"], h["pct"])
    for r in ex["lookthrough"]:
        if name_key(r["entity"]) in via:
            add(r["name"], via[name_key(r["entity"])] * r["pct"] / 100)
    return [(n, round(p, 6)) for _, (n, p) in sorted(total.items())]


def beneficial_owners(ex: dict) -> list:
    """Individuals at or above the ownership threshold, largest first."""
    return sorted(((n, p) for n, p in ownership(ex) if p >= OWNERSHIP_THRESHOLD - EPS), key=lambda x: (-x[1], name_key(x[0])))


# ---------------------------------------------------------------- the checks
def _completeness(ex: dict) -> list:
    out = []
    if not ex["legal_name"]:
        out.append(finding("completeness", "legal_name_missing", "(packet)", "no legal name was read"))
    if not ex["holders"]:
        out.append(finding("completeness", "no_holders", "(packet)", "no holder was read, so ownership cannot be checked"))
    for i, h in enumerate(ex["holders"]):
        if not h["name"]:
            out.append(finding("completeness", "name_missing", f"holders[{i}]", "a holder row has no name"))
    cp = ex["control_person"]
    control = cp["name"] if cp and cp["name"] else ""
    if not control:
        out.append(finding("completeness", "control_person_missing", "(packet)", "no control person was read"))
    needed = [(n, f"holds {fmt_pct(p)}%") for n, p in beneficial_owners(ex)] + ([(control, "control person")] if control else [])
    people = {}
    for p in ex["people"]:
        people.setdefault(name_key(p["name"]), p)
    seen = set()
    for name, why in needed:
        k = name_key(name)
        if k in seen:
            continue
        seen.add(k)
        rec = people.get(k)
        if rec is None:
            out.append(finding("completeness", "person_record_missing", clean(name), f"{why}; no details were read for this person"))
            continue
        for f, label in PERSON_FIELDS:
            if not rec[f]:
                out.append(finding("completeness", "person_field_missing", clean(name), f"{label} is empty ({why})"))
    cert = ex["certification"]
    if cert is None:
        out.append(finding("completeness", "certification_incomplete", "(packet)", "no certification was read"))
    else:
        gaps = [label for f, label in (("signed_by", "signer"), ("date", "date")) if not cert[f]]
        if gaps:
            out.append(finding("completeness", "certification_incomplete", "(packet)", "certification has no " + " and no ".join(gaps)))
    return out


def _arithmetic(ex: dict, tolerance: float) -> list:
    out = []
    for label, rows in (("holders", ex["holders"]), ("lookthrough", ex["lookthrough"])):
        for i, r in enumerate(rows):
            if not 0 < r["pct"] <= 100:
                out.append(finding("arithmetic", "pct_out_of_range", f"{label}[{i}]", f"{fmt_pct(r['pct'])}% is not above 0 and at most 100"))
    total = sum(h["pct"] for h in ex["holders"])
    if ex["holders"] and abs(total - 100) > tolerance + EPS:
        out.append(finding("arithmetic", "direct_sum", "(holders)", f"holders add up to {fmt_pct(total)}, expected 100 (tolerance {fmt_pct(tolerance)})"))
    held, shown, label = {}, {}, {}
    for h in ex["holders"]:
        if h["kind"] == "entity" and name_key(h["name"]):
            held[name_key(h["name"])] = held.get(name_key(h["name"]), 0.0) + h["pct"]
            label.setdefault(name_key(h["name"]), h["name"])
    for r in ex["lookthrough"]:
        shown.setdefault(name_key(r["entity"]), []).append(r)
        label.setdefault(name_key(r["entity"]), r["entity"])
    for k in sorted(shown):
        if k not in held:
            out.append(finding("arithmetic", "lookthrough_orphan", clean(label[k]), "look-through rows name an entity that is not a holder"))
        total = sum(r["pct"] for r in shown[k])
        if abs(total - 100) > tolerance + EPS:
            out.append(finding("arithmetic", "lookthrough_sum", clean(label[k]), f"its owners add up to {fmt_pct(total)}, expected 100 (tolerance {fmt_pct(tolerance)})"))
    for k in sorted(held):
        if held[k] >= OWNERSHIP_THRESHOLD - EPS and k not in shown:
            out.append(finding("arithmetic", "lookthrough_missing", clean(label[k]),
                               f"holds {fmt_pct(held[k])}% and no owners behind it were read"))
    return out


def _index(source_text: str) -> list:
    lines = []
    for raw in source_text.splitlines():
        if raw.strip():
            lines.append({"words": set(words(raw)), "norm": " ".join(words(raw)),
                          "lookthrough": raw.strip().lower().startswith("look-through"),
                          "pcts": [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", raw)]})
    return lines


def _names(ln: dict, ws: list) -> bool:
    return bool(ws) and all(w in ln["words"] for w in ws)


def _pct_detail(read: float, lines: list) -> str:
    seen = sorted({p for ln in lines for p in ln["pcts"]})
    shown = ", ".join(fmt_pct(p) + "%" for p in seen)
    return f"read {fmt_pct(read)}%, " + (f"source line shows {shown}" if seen else "no percent figure on a source line that names this holder")


def _grounding(ex: dict, source_text: str) -> list:
    out, src = [], _index(source_text)
    cp = ex["control_person"]
    named = [("legal name", ex["legal_name"])] + [("holder", h["name"]) for h in ex["holders"]] \
        + [("owner behind an entity", r["name"]) for r in ex["lookthrough"]] + [("person", p["name"]) for p in ex["people"]] \
        + ([("control person", cp["name"])] if cp else [])
    lost = set()
    for role, name in named:
        k = name_key(name)
        if k and k not in lost and not any(_names(ln, name_words(name)) for ln in src):
            lost.add(k)
            out.append(finding("grounding", "name_not_in_source", clean(name), f"{role}: no source line names this"))
    for h in ex["holders"]:
        if name_key(h["name"]) in lost or not name_key(h["name"]):
            continue
        lines = [ln for ln in src if not ln["lookthrough"] and _names(ln, name_words(h["name"]))]
        if not any(abs(p - h["pct"]) < 1e-6 for ln in lines for p in ln["pcts"]):
            out.append(finding("grounding", "pct_not_in_source", clean(h["name"]), _pct_detail(h["pct"], lines)))
    for r in ex["lookthrough"]:
        if name_key(r["name"]) in lost or not name_key(r["name"]):
            continue
        lines = [ln for ln in src if ln["lookthrough"] and _names(ln, name_words(r["name"])) and _names(ln, name_words(r["entity"]))]
        if not any(abs(p - r["pct"]) < 1e-6 for ln in lines for p in ln["pcts"]):
            out.append(finding("grounding", "pct_not_in_source", clean(r["name"]) + " (look-through)", _pct_detail(r["pct"], lines)))
    for p in ex["people"]:
        if name_key(p["name"]) in lost or not name_key(p["name"]):
            continue
        lines = [ln for ln in src if _names(ln, name_words(p["name"]))]
        for f, label in PERSON_FIELDS:
            if not p[f]:
                continue
            want = " ".join(words(p[f]))
            ok = bool(want) and any((want in ln["words"]) if f == "id_last4" else (f" {want} " in f" {ln['norm']} ") for ln in lines)
            if not ok:
                out.append(finding("grounding", "detail_not_in_source", clean(p["name"]), f"{label} is not on any source line that names this person"))
    return out


def check_parsed(source_text: str, ex: dict, tolerance: float = DEFAULT_TOLERANCE, families: tuple = FAMILIES) -> list:
    """All findings for one packet whose extraction has already gone through parse_extraction."""
    out = []
    if "completeness" in families:
        out += _completeness(ex)
    if "arithmetic" in families:
        out += _arithmetic(ex, tolerance)
    if "grounding" in families:
        out += _grounding(ex, source_text)
    return out


def check_packet(source_text: str, extraction, tolerance: float = DEFAULT_TOLERANCE, families: tuple = FAMILIES) -> list:
    """All findings for one packet. `extraction` is the decoded JSON; raises InputError when its shape is wrong."""
    return check_parsed(source_text, parse_extraction(extraction), tolerance, families)


def decide(findings: list) -> str:
    return "REVIEW" if findings else "PASS"


# ---------------------------------------------------------------- command line
def read_text(path: str, label: str) -> str:
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_BYTES + 1)
    except OSError as e:
        raise InputError(f"cannot read {label} {clean(path)}: {clean(e.strerror or type(e).__name__)}") from None
    if len(raw) > MAX_BYTES:
        raise InputError(f"{label} is larger than {MAX_BYTES} bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise InputError(f"{label} is not UTF-8 text") from None
    if not text.strip():
        raise InputError(f"{label} is empty")
    return text


def load_json(path: str, label: str):
    text = read_text(path, label)
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        raise InputError(f"{label} is not valid JSON (empty, truncated or too deeply nested)") from None


def render(ex: dict, findings: list, source_lines: int) -> str:
    bos = ", ".join(f"{clean(n)} {fmt_pct(p)}%" for n, p in beneficial_owners(ex)) or "none"
    cp = ex["control_person"]
    out = [f"packet {clean(ex['packet_id'] or '(no id)')}  {clean(ex['legal_name'] or '(no legal name read)')}"]
    out += [f"  [{f['family']:<12}] {f['kind']:<22} {f['subject']}: {f['detail']}" for f in findings]
    out.append(f"checked: {len(ex['holders'])} holders, {len(ex['lookthrough'])} look-through rows, {len(ex['people'])} people "
               f"against {source_lines} source lines")
    out.append(f"owners at 25 percent or more as read: {bos}; control person: {clean(cp['name']) if cp and cp['name'] else 'none'}")
    out.append(f"decision: {decide(findings)} ({len(findings)} finding{'' if len(findings) == 1 else 's'})")
    return "\n".join(out)


def run_check(source_path: str, extraction_path: str, tolerance: float, fail_on: str) -> int:
    try:
        if not math.isfinite(tolerance) or tolerance < 0:
            raise InputError("--tolerance must be a number of at least 0")
        source = read_text(source_path, "source")
        ex = parse_extraction(load_json(extraction_path, "extraction"))
        findings = check_parsed(source, ex, tolerance)
    except InputError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    print(render(ex, findings, len([ln for ln in source.splitlines() if ln.strip()])))
    return 1 if findings and fail_on == "review" else 0


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(f"{self.prog}: error: {clean(message, 200)}", file=sys.stderr)
        raise SystemExit(2)


def main(argv=None) -> int:
    ap = _Parser(prog="kyb_packet_check")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_source.txt, data/example_extracted.json)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check one extraction against its packet text")
    c.add_argument("source", help="text of the packet, UTF-8")
    c.add_argument("extraction", help="the model's extraction, JSON")
    c.add_argument("--fail-on", choices=["review", "never"], default="review")
    c.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE, help="allowed distance of a percentage total from 100")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_source.txt"), os.path.join(d, "example_extracted.json"), DEFAULT_TOLERANCE, "never")
    if a.cmd == "check":
        return run_check(a.source, a.extraction, a.tolerance, a.fail_on)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
