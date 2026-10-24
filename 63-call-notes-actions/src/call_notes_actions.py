"""call_notes_actions: check that each CRM action proposed from a relationship manager's call note is
grounded in a sentence of that note. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 call_notes_actions.py --demo
    python3 call_notes_actions.py check NOTES.csv CANDIDATES.csv [--fail-on reject|hold|never] [--format text|json]

NOTES.csv has one row per sentence: note_id, call_date (YYYY-MM-DD), sent_id (integer), text.
CANDIDATES.csv has one row per proposed action: cand_id, note_id, action_type, cite_sent_id, cite_quote,
and optionally owner (rm or client), due (YYYY-MM-DD), subject, amount (whole dollars).

Each candidate gets one of three decisions:
    ACCEPT  the cited sentence exists, carries the action, and agrees with every slot
    REVIEW  the sentence exists but something is off (a date, an owner, or a conditional, negated, past or hedged
            sentence); a person decides
    REJECT  the citation is not in the note, or the cited sentence does not carry this kind of action

Exit status: 0 when nothing reaches --fail-on (default: a REJECT), 1 when something does, 2 for missing or
malformed input. There is no model in this file: the checks are plain rules over the cited sentence.

Rules read the cited sentence only. They do not split a sentence into clauses, resolve a pronoun, or read words
outside the lists below, so a commitment softened in other words ("I will try to") passes.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from datetime import date, timedelta

# action type -> (trigger words that must appear in the cited sentence, whether the type is a commitment by a person)
ACTION_TYPES = {
    "send_document": (re.compile(r"\b(?:send|sent|email|forward|share|mail)\w*", re.I), True),
    "await_document": (re.compile(r"\b(?:return|send|sent|provide|upload|sign|deliver|submit)\w*", re.I), True),
    "callback": (re.compile(r"\b(?:call|phone|ring)\w*", re.I), True),
    "schedule_review": (re.compile(r"\b(?:book|schedule|arrange|set up)\w*", re.I), True),
    "limit_request": (re.compile(r"\b(?:raise|increase|lift)\w*", re.I), True),
    "log_complaint": (re.compile(r"\b(?:complain|unhappy|upset|escalat)\w*", re.I), False),
    "update_preference": (re.compile(r"\b(?:prefer|asked to be contacted)\w*", re.I), False),
}
ALL_CHECKS = ("cite", "support", "slots", "owner", "modality")
MIN_QUOTE_CHARS = 8
NOTE_COLS = ["note_id", "call_date", "sent_id", "text"]
CAND_COLS = ["cand_id", "note_id", "action_type", "cite_sent_id", "cite_quote"]
CAND_OPTIONAL = ["owner", "due", "subject", "amount"]

_MONTH = "jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
_DAY_MONTH = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + _MONTH + r")\b", re.I)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_WEEKDAY = re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)
_TOMORROW = re.compile(r"\btomorrow\b", re.I)
_MONTH_NO = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DAY_NO = {d: i for i, d in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])}
_AMOUNT = re.compile(r"(\$)?\s?(\d[\d,]*(?:\.\d+)?)\s?(k|thousand|million|m)?(?![A-Za-z0-9])", re.I)
_MULT = {"k": 1000, "thousand": 1000, "m": 1000000, "million": 1000000}

_RM = re.compile(r"\bI(?:'ll| will| shall| am going to|'m going to| agreed to)\b|\bme to\b|\bthat I\b")
_CLIENT = re.compile(r"\b(?:he|she|they)(?:'ll| will| is going to| are going to| has agreed to| agreed to)\b"
                     r"|\b(?:Mr|Ms|Mrs|Dr)\.? [A-Z][\w'-]+ (?:will|is going to)\b", re.I)
MODALITY = {
    "conditional": re.compile(r"\b(?:if|unless|once|provided|depending|subject to|as soon as|in case|when)\b", re.I),
    "negated": re.compile(r"\b(?:not|no|never|without|nothing|declined|refused|rejected)\b|n't\b", re.I),
    "past": re.compile(r"\b(?:already|yesterday|previously|earlier|last (?:week|month|year|quarter)|sent|called|emailed|"
                       r"returned|booked|forwarded|phoned)\b", re.I),
    "hedged": re.compile(r"\b(?:maybe|might|perhaps|possibly|probably|could)\b", re.I),
}
_COMMITMENT_MODALITY = ("conditional", "negated", "past", "hedged")
_STATEMENT_MODALITY = ("conditional", "negated", "hedged")


class InputError(Exception):
    """Bad or malformed input: reported as one line on stderr, exit status 2."""


def esc(s, limit: int = 120) -> str:
    """Make text from an input file safe to print on one line or to place in a workflow command: % -> %25, CR -> %0D,
    LF -> %0A, other control characters as %XX, and cut to `limit` characters."""
    out = []
    for ch in str(s):
        if ch == "%":
            out.append("%25")
        elif ch == "\r":
            out.append("%0D")
        elif ch == "\n":
            out.append("%0A")
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append("%%%02X" % ord(ch))
        else:
            out.append(ch)
    t = "".join(out)
    return t if len(t) <= limit else t[:limit - 3] + "..."


# ---------------------------------------------------------------- text helpers
def normalize(s: str) -> str:
    """Compare-ready text: compatibility forms folded, curly quotes and dashes straightened, whitespace collapsed, case folded."""
    s = unicodedata.normalize("NFKC", s)
    for a, b in (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'), ("–", "-"), ("—", "-")):
        s = s.replace(a, b)
    return " ".join(s.split()).casefold()


def quote_in(sentence: str, quote: str) -> bool:
    """True when the quote is the cited sentence, or a part of it, after normalizing. An ellipsis inside the quote means
    'text omitted here': the parts on each side must appear in order. A quote shorter than MIN_QUOTE_CHARS is not a citation."""
    s = normalize(sentence)
    parts = [p.strip(" \"'.,;:") for p in re.split(r"\.\.\.|…", normalize(quote))]
    parts = [p for p in parts if p]
    if sum(len(p) for p in parts) < MIN_QUOTE_CHARS:
        return False
    pos = 0
    for p in parts:
        i = s.find(p, pos)
        if i < 0:
            return False
        pos = i + len(p)
    return True


def resolve_dates(sentence: str, call: date) -> set:
    """ISO dates a sentence names. 'D Month' takes the call's year, or the next year when that falls before the call;
    a weekday name means its first occurrence after the call date; 'tomorrow' is the day after the call."""
    found = set()
    for m in _ISO.finditer(sentence):
        try:
            found.add(date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat())
        except ValueError:
            pass
    for m in _DAY_MONTH.finditer(sentence):
        try:
            d = date(call.year, _MONTH_NO[m.group(2)[:3].lower()], int(m.group(1)))
            if d < call:
                d = date(call.year + 1, d.month, d.day)
            found.add(d.isoformat())
        except ValueError:
            pass
    for m in _WEEKDAY.finditer(sentence):
        found.add((call + timedelta(days=(_DAY_NO[m.group(1).lower()] - call.weekday()) % 7 or 7)).isoformat())
    if _TOMORROW.search(sentence):
        found.add((call + timedelta(days=1)).isoformat())
    return found


def find_amounts(sentence: str) -> set:
    """Whole-dollar amounts written with a dollar sign or a k / thousand / million suffix. Spelled-out numbers are not read."""
    found = set()
    for m in _AMOUNT.finditer(sentence):
        if not (m.group(1) or m.group(3)):
            continue
        try:
            found.add(int(round(float(m.group(2).replace(",", "")) * _MULT.get((m.group(3) or "").lower(), 1))))
        except ValueError:
            pass
    return found


def owner_markers(sentence: str) -> tuple:
    """(rm, client): whether the sentence has a first-person commitment, and whether it has a third-person one."""
    return bool(_RM.search(sentence.replace("’", "'"))), bool(_CLIENT.search(sentence.replace("’", "'")))


# ---------------------------------------------------------------- the checks
def _as_int(v):
    v = str(v).strip()
    return int(v) if re.fullmatch(r"[0-9]+", v) else None


def check_candidate(notes: dict, cand: dict, checks: tuple = ALL_CHECKS) -> tuple:
    """Decide one candidate. Returns (decision, reasons). `checks` picks which rule groups run; the order below is fixed."""
    ctype = cand["action_type"].strip()
    if ctype not in ACTION_TYPES:
        return "REJECT", ["unknown_action_type"]
    note = notes.get(cand["note_id"])
    if note is None:
        return "REJECT", ["note_not_found"]
    sid = _as_int(cand["cite_sent_id"])
    sentence = note["sentences"].get(sid) if sid is not None else None
    if sentence is None or ("cite" in checks and not quote_in(sentence, cand["cite_quote"])):
        return "REJECT", ["cite_not_found"]
    trigger, is_commitment = ACTION_TYPES[ctype]
    if "support" in checks:
        if not trigger.search(sentence):
            return "REJECT", ["no_support:trigger"]
        subject = cand["subject"].strip()
        if subject and normalize(subject) not in normalize(sentence):
            return "REJECT", ["no_support:subject"]
    reasons = []
    if "slots" in checks:
        due = cand["due"].strip()
        if due and due not in resolve_dates(sentence, note["call_date"]):
            reasons.append("due_not_in_sentence")
        amount = cand["amount"].strip()
        if amount:
            try:
                ok = int(round(float(amount.replace(",", "")))) in find_amounts(sentence)
            except ValueError:
                ok = False
            if not ok:
                reasons.append("amount_not_in_sentence")
    if "owner" in checks and is_commitment:
        owner = cand["owner"].strip().lower()
        rm, client = owner_markers(sentence)
        mine, theirs = (rm, client) if owner == "rm" else (client, rm)
        if owner not in ("rm", "client"):
            reasons.append("owner_missing")
        elif not mine:
            reasons.append("owner_mismatch" if theirs else "owner_unclear")
    if "modality" in checks:
        for name in (_COMMITMENT_MODALITY if is_commitment else _STATEMENT_MODALITY):
            m = MODALITY[name].search(sentence)
            if m:
                reasons.append(f"{name}:{m.group(0).lower()}")
    return ("REVIEW" if reasons else "ACCEPT"), reasons


def check_all(notes: dict, cands: list, checks: tuple = ALL_CHECKS) -> list:
    out = []
    for c in cands:
        decision, reasons = check_candidate(notes, c, checks)
        out.append(dict(c, decision=decision, reasons=reasons))
    return out


# ---------------------------------------------------------------- loading
def _read_rows(path: str, required: list, label: str) -> list:
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise InputError(f"{label}: {esc(path)} is empty")
            missing = [c for c in required if c not in reader.fieldnames]
            if missing:
                raise InputError(f"{label}: missing column(s) {', '.join(missing)}")
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise InputError(f"{label}: cannot read {esc(path)} ({type(e).__name__})")
    for i, r in enumerate(rows, 2):
        if None in r or any(r[c] is None for c in required):
            raise InputError(f"{label}: line {i} is truncated or has extra fields")
    return rows


def load_notes(path: str) -> dict:
    """{note_id: {"call_date": date, "sentences": {sent_id: text}}}"""
    rows = _read_rows(path, NOTE_COLS, "notes")
    if not rows:
        raise InputError(f"notes: {esc(path)} has a header and no rows")
    notes = {}
    for i, r in enumerate(rows, 2):
        nid = r["note_id"].strip()
        if not nid:
            raise InputError(f"notes: line {i}: note_id is empty")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["call_date"].strip()):
            raise InputError(f"notes: line {i}: call_date must be YYYY-MM-DD")
        try:
            call = date.fromisoformat(r["call_date"].strip())
        except ValueError:
            raise InputError(f"notes: line {i}: call_date is not a real date")
        sid = _as_int(r["sent_id"])
        if sid is None:
            raise InputError(f"notes: line {i}: sent_id must be a whole number")
        note = notes.setdefault(nid, {"call_date": call, "sentences": {}})
        if note["call_date"] != call:
            raise InputError(f"notes: line {i}: call_date differs inside note {esc(nid, 40)}")
        if sid in note["sentences"]:
            raise InputError(f"notes: line {i}: sentence {sid} of note {esc(nid, 40)} appears twice")
        note["sentences"][sid] = r["text"]
    return notes


def load_candidates(path: str) -> list:
    rows = _read_rows(path, CAND_COLS, "candidates")
    seen, out = set(), []
    for i, r in enumerate(rows, 2):
        cid = r["cand_id"].strip()
        if not cid:
            raise InputError(f"candidates: line {i}: cand_id is empty")
        if cid in seen:
            raise InputError(f"candidates: line {i}: cand_id {esc(cid, 40)} appears twice")
        seen.add(cid)
        c = {k: r[k] for k in CAND_COLS}
        c["cand_id"] = cid
        for k in CAND_OPTIONAL:
            c[k] = r.get(k) or ""
        out.append(c)
    return out


# ---------------------------------------------------------------- command line
def render_text(results: list, notes: dict) -> str:
    lines = []
    for r in results:
        why = ("  -> " + "; ".join(esc(x, 60) for x in r["reasons"])) if r["reasons"] else ""
        lines.append(f"  {r['decision']:<6} {esc(r['cand_id'], 12):<6} {esc(r['action_type'], 18):<17} "
                     f"{esc(r['owner'], 8):<7} {esc(r['due'], 10):<11} S{esc(r['cite_sent_id'], 6):<4} "
                     f"\"{esc(r['cite_quote'], 56)}\"{why}")
    n = {d: sum(1 for r in results if r["decision"] == d) for d in ("ACCEPT", "REVIEW", "REJECT")}
    head = (f"call_notes_actions: {len(results)} candidate{'' if len(results) == 1 else 's'} "
            f"against {len(notes)} note{'' if len(notes) == 1 else 's'}")
    matched = {r["note_id"] for r in results if r["note_id"] in notes}
    tail = [f"checked {len(results)}: {n['ACCEPT']} accepted, {n['REVIEW']} held for review, {n['REJECT']} rejected"]
    if results and not matched:
        tail.append("none of the candidates names a note in the notes file; nothing could be grounded")
    if not results:
        tail.append("no candidates: nothing was checked")
    tail.append(f"notes with no proposed action: {len(set(notes) - matched)} of {len(notes)}")
    return "\n".join([head] + lines + tail)


def run_check(notes_path: str, cands_path: str, fail_on: str, fmt: str) -> int:
    notes, cands = load_notes(notes_path), load_candidates(cands_path)
    results = check_all(notes, cands)
    if fmt == "json":
        print(json.dumps({"results": results}, sort_keys=True, indent=1))
    else:
        print(render_text(results, notes))
    bad = {"reject": ("REJECT",), "hold": ("REJECT", "REVIEW"), "never": ()}[fail_on]
    return 1 if any(r["decision"] in bad for r in results) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="call_notes_actions")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_*.csv)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="ground candidate actions against call notes")
    c.add_argument("notes")
    c.add_argument("candidates")
    c.add_argument("--fail-on", choices=["reject", "hold", "never"], default="reject")
    c.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)
    try:
        if a.demo:
            d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
            return run_check(os.path.join(d, "example_notes.csv"), os.path.join(d, "example_candidates.csv"), "never", "text")
        if a.cmd == "check":
            return run_check(a.notes, a.candidates, a.fail_on, a.format)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
