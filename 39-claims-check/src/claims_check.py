#!/usr/bin/env python3
"""claims-check: fail when a number cited as measured in a README is not printed by a script.

A README tags each figure with a credibility circle: green for measured, yellow for modeled, red for
hypothetical. This tool reads the numbers that follow a green circle and checks each one against
the text the scripts printed (the evidence files). Standard library only, Python 3.9 or newer.

    python3 claims_check.py check README.md --evidence out/*.txt
    python3 claims_check.py --demo

What counts as a claim
  - Text after a green circle, up to the next circle or the end of the paragraph or list item.
    A bullet that wraps onto a second line is one item.
  - Not claims: fenced code blocks, `code spans`, link targets and bare URLs. Wrap an identifier
    such as step_04 or p95 in backticks and its digits are ignored.
  - "a of b" is one claim: some evidence line must print the pair as "a of b" or "a/b".
  - Any other number is a claim: it must be printed as a whole number. 12 is not supported by a
    line that prints 112, and 40 is not supported by 40.3. Commas and trailing zeros do not matter.
  - A number with fewer than --min-digits digits (default 2) is skipped and counted.

Exit status: 0 when nothing is unsupported, 1 when at least one claim is, 2 for bad input.
"""
from __future__ import annotations

import argparse
import bisect
import glob
import os
import re
import sys

GREEN = "\U0001F7E2"
TAGS = (GREEN, "\U0001F7E1", "\U0001F534")
MIN_DIGITS = 2
MAX_BYTES = 5_000_000

_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
NUMBER = re.compile(r"(?<![\d.])" + _NUM + r"(?!\d)", re.ASCII)
CLAIMED_RATIO = re.compile(r"(?<![\d.])(" + _NUM + r")\s+of\s+(" + _NUM + r")(?!\d)", re.ASCII)
PRINTED_RATIO = re.compile(r"(?<![\d.])(" + _NUM + r")\s*(?:of|/)\s*(" + _NUM + r")(?!\d)", re.ASCII)
BLOCK_START = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|#|\|)")
INERT = (re.compile(r"`[^`]*`"), re.compile(r"(?<=\])\([^)\s]*\)"), re.compile(r"https?://[^\s)>\]]+"))
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


# ---------------------------------------------------------------- numbers
def norm(token: str) -> str:
    """Compare numbers by value as printed: no thousands commas, no trailing zeros after a point."""
    token = token.replace(",", "")
    return token.rstrip("0").rstrip(".") if "." in token else token


def digit_count(token: str) -> int:
    return sum(ch.isdigit() for ch in token)


# ---------------------------------------------------------------- reading a README
def blocks(text: str) -> list:
    """Paragraphs, list items and table rows. Each is {"text": joined text, "marks": [(offset, line number)]}."""
    out, cur, fenced = [], None, False
    for no, raw in enumerate(text.split("\n"), 1):
        line = raw.rstrip("\r")
        stripped = line.strip()
        if stripped.startswith("```"):
            fenced, cur = not fenced, None
        elif fenced or not stripped:
            cur = None
        elif cur is None or BLOCK_START.match(line):
            cur = {"text": stripped, "marks": [(0, no)]}
            out.append(cur)
        else:
            cur["marks"].append((len(cur["text"]) + 1, no))
            cur["text"] += " " + stripped
    return out


def extract_claims(readme: str) -> list:
    """Every number after a green circle: [{"line", "kind": "ratio" or "number", "text", "key"}], in reading order."""
    claims = []
    for block in blocks(readme):
        text = block["text"]
        for pattern in INERT:
            text = pattern.sub(lambda m: " " * len(m.group()), text)
        starts = [offset for offset, _ in block["marks"]]
        found = []
        for seg in re.finditer(re.escape(GREEN) + "(.*?)(?=" + "|".join(TAGS) + "|$)", text):
            body, base = seg.group(1), seg.start(1)
            for m in CLAIMED_RATIO.finditer(body):
                found.append((base + m.start(), {"kind": "ratio", "text": " ".join(m.group().split()),
                                                 "key": (norm(m.group(1)), norm(m.group(2)))}))
            rest = CLAIMED_RATIO.sub(lambda m: " " * len(m.group()), body)
            for m in NUMBER.finditer(rest):
                found.append((base + m.start(), {"kind": "number", "text": m.group(), "key": norm(m.group())}))
        for pos, claim in sorted(found, key=lambda f: f[0]):
            claim["line"] = block["marks"][bisect.bisect_right(starts, pos) - 1][1]
            claims.append(claim)
    return claims


# ---------------------------------------------------------------- checking against the evidence
def index_evidence(texts: list) -> dict:
    """What the scripts printed: every whole number, and every "a of b" or "a/b" pair on one line."""
    tokens, pairs = set(), set()
    for text in texts:
        for line in text.split("\n"):
            tokens.update(norm(m.group()) for m in NUMBER.finditer(line))
            pairs.update((norm(m.group(1)), norm(m.group(2))) for m in PRINTED_RATIO.finditer(line))
    return {"tokens": tokens, "pairs": pairs}


def _lookup(key: str, tokens: set, min_digits: int):
    """None when key is too short to check, "" when it is printed, else the reason it is not."""
    if digit_count(key) < min_digits:
        return None
    if key in tokens:
        return ""
    why = f"{key} is not printed by any script"
    near = sorted(t for t in tokens if key in t)[:3]
    if near:
        why += " (a longer figure that contains it is printed: " + ", ".join(near) + ")"
    return why


def check_claims(claims: list, evidence: dict, min_digits: int = MIN_DIGITS, pairs: bool = True) -> list:
    """Add "status" (supported, unsupported, skipped) and "why" to each claim."""
    tokens, printed = evidence["tokens"], evidence["pairs"]
    results = []
    for c in claims:
        status, why = "supported", ""
        if c["kind"] == "ratio" and pairs:
            a, b = c["key"]
            if max(digit_count(a), digit_count(b)) < min_digits:
                status = "skipped"
            elif (a, b) not in printed:
                status = "unsupported"
                missing = [w for w in (_lookup(a, tokens, 1), _lookup(b, tokens, 1)) if w]
                why = missing[0] if missing else f'both numbers are printed, never as "{c["text"]}" on one line'
        else:
            keys = list(c["key"]) if c["kind"] == "ratio" else [c["key"]]
            looked = [w for w in (_lookup(k, tokens, min_digits) for k in keys) if w is not None]
            if not looked:
                status = "skipped"
            elif any(looked):
                status, why = "unsupported", next(w for w in looked if w)
        results.append(dict(c, status=status, why=why))
    return results


# ---------------------------------------------------------------- output
def clean(text) -> str:
    """One printable line: control characters, newlines included, become spaces."""
    return CONTROL.sub(" ", str(text))


def escape_data(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so input text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(text) -> str:
    return escape_data(text).replace(":", "%3A").replace(",", "%2C")


def tally(results: list) -> dict:
    counts = {"supported": 0, "unsupported": 0, "skipped": 0}
    for r in results:
        counts[r["status"]] += 1
    counts["checked"] = counts["supported"] + counts["unsupported"]
    return counts


def render_text(shown: str, n_files: int, evidence: dict, results: list, min_digits: int) -> str:
    n = tally(results)
    plural = "" if n_files == 1 else "s"
    lines = [f"claims-check: {clean(shown)} against {n_files} evidence file{plural} "
             f"({len(evidence['tokens'])} numbers, {len(evidence['pairs'])} ratios printed)"]
    for r in results:
        if r["status"] == "unsupported":
            quoted = '"' + r["text"] + '"'
            lines.append(f"  line {r['line']:<4} not supported  {quoted:<14} {r['why']}")
    if not results:
        lines.append("claims: none. No number follows a green circle, so nothing was checked.")
    else:
        lines.append(f"claims: {n['checked']} checked, {n['supported']} supported, {n['unsupported']} not supported, "
                     f"{n['skipped']} skipped (fewer than {min_digits} digit{'' if min_digits == 1 else 's'})")
    lines.append("result: " + ("FAIL" if n["unsupported"] else "PASS" if n["checked"] else "NOTHING CHECKED"))
    return "\n".join(lines)


def render_github(shown: str, results: list, min_digits: int) -> str:
    n = tally(results)
    where = escape_property(shown)
    lines = [f"::error file={where},line={r['line']},title=claims-check::" + escape_data(f"{r['text']}: {r['why']}")
             for r in results if r["status"] == "unsupported"]
    if n["checked"]:
        lines.append(f"::notice title=claims-check::{n['checked']} checked, {n['unsupported']} not supported, "
                     f"{n['skipped']} skipped (fewer than {min_digits} digits)")
    else:
        lines.append(f"::warning file={where},title=claims-check::nothing was checked: "
                     f"{n['skipped']} numbers after a green circle were too short and none was long enough")
    return "\n".join(lines)


# ---------------------------------------------------------------- command line
def read_text(path: str, label: str) -> str:
    """Read a UTF-8 text file, or raise ValueError with a one-line reason."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_BYTES + 1)
    except OSError as e:
        raise ValueError(f"cannot read {label} {clean(path)}: {e.strerror or type(e).__name__}") from None
    if len(raw) > MAX_BYTES:
        raise ValueError(f"{label} {clean(path)} is larger than {MAX_BYTES // 1_000_000} MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"{label} {clean(path)} is not valid UTF-8 text (truncated or binary?)") from None
    if "\x00" in text:
        raise ValueError(f"{label} {clean(path)} contains NUL bytes, so it is not a text file")
    if not text.strip():
        raise ValueError(f"{label} {clean(path)} is empty")
    return text


def expand_evidence(values: list) -> list:
    """Paths from --evidence values. A value may hold several patterns, one per line. A pattern that matches no file is an error."""
    patterns = [p.strip() for v in values for p in v.split("\n") if p.strip()]
    if not patterns:
        raise ValueError("no evidence file was given")
    paths = set()
    for pattern in patterns:
        hits = [h for h in glob.glob(pattern, recursive=True) if os.path.isfile(h)]
        if not hits:
            raise ValueError(f"no evidence file matches {clean(pattern)}")
        paths.update(hits)
    return sorted(paths)


def run_check(readme_path, patterns, fail_on="unsupported", fmt="text", min_digits=MIN_DIGITS, pairs=True,
              shown=None) -> int:
    try:
        readme = read_text(readme_path, "README")
        paths = expand_evidence(patterns)
        texts = [read_text(p, "evidence file") for p in paths]
    except ValueError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    evidence = index_evidence(texts)
    results = check_claims(extract_claims(readme), evidence, min_digits, pairs)
    shown = readme_path if shown is None else shown
    if fmt == "github":
        print(render_github(shown, results, min_digits))
    else:
        print(render_text(shown, len(paths), evidence, results, min_digits))
    failed = any(r["status"] == "unsupported" for r in results)
    return 1 if failed and fail_on == "unsupported" else 0


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print("usage error: " + clean(message), file=sys.stderr)
        sys.exit(2)


def main(argv=None) -> int:
    ap = _Parser(prog="claims_check", description="Fail when a number after a green circle in a README is not printed by a script.")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_claims.md)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check one README against evidence files")
    c.add_argument("readme")
    c.add_argument("--evidence", nargs="+", required=True, help="files or glob patterns holding what the scripts printed")
    c.add_argument("--fail-on", choices=["unsupported", "never"], default="unsupported")
    c.add_argument("--format", choices=["text", "github"], default="text")
    c.add_argument("--min-digits", type=int, default=MIN_DIGITS, help="skip numbers with fewer digits (default 2)")
    c.add_argument("--no-pairs", action="store_true", help='check "a of b" as two separate numbers')
    a = ap.parse_args(argv)
    if a.demo:
        data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(data, "example_claims.md"), [os.path.join(data, "example_output.txt")],
                         "never", "text", shown="example_claims.md")
    if a.cmd == "check":
        if a.min_digits < 1:
            ap.error("--min-digits must be 1 or more")
        return run_check(a.readme, a.evidence, a.fail_on, a.format, a.min_digits, not a.no_pairs)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
