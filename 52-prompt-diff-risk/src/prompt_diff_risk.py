"""prompt_diff_risk: classify a change to an agent's system prompt before it merges, and name the probe
slices to run. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 prompt_diff_risk.py --demo
    python3 prompt_diff_risk.py check OLD.txt NEW.txt [--tools TOOLS.json] [--probes PROBES.csv]
                                                      [--fail-on block|review|never] [--format text|github]

Exit status: 0 when the decision is below --fail-on, 1 when it is at or above it, 2 for bad or malformed input.
Decision per change:
    BLOCK   a rule was removed or weakened, a write tool was granted, or a guard on a write tool was dropped
    REVIEW  the behavior may have moved: scope, tone, a number, a new rule, a read tool, an unclassified sentence
    ALLOW   nothing but wording, comments or headings changed
There is no model in this file. Four dimensions are read from the text with word lists: constraints (rule
words such as never, must, should), scope (what the assistant answers), tone (register words) and tools
(names from a catalogue you supply, with an explicit read or write access field).

Prompt format: UTF-8 text. A line that starts with # is a heading or comment and is not read. Every other
sentence is one statement; bullets and numbering are stripped, and lines of one paragraph are joined.
Reordering statements is not a change. English only.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

SAME_MIN = 0.75   # assumption: two statements with at least this token overlap are one statement reworded
PAIR_MIN = 0.4    # assumption: below this overlap a removed and an added statement are not one edited statement
ALL = "*"         # slice marker for a finding no topic word could place: run every slice
DECISION_RANK = {"ALLOW": 0, "REVIEW": 1, "BLOCK": 2}

# ---------------------------------------------------------------- word lists
_CUE_LEVELS = {
    3: ["never", "must not", "mustn't", "do not", "don't", "cannot", "can't", "must", "always", "under no circumstances",
        "refuse", "decline", "not allowed", "prohibited", "have to"],
    2: ["should not", "shouldn't", "should", "avoid", "ought to"],
    1: ["try not to", "try to", "where possible", "when possible", "if appropriate", "ideally", "may", "might", "can",
        "consider", "feel free to", "prefer to"],
}
_CUE_RX = {lvl: re.compile(r"(?<![\w'])(?:" + "|".join(re.escape(w) for w in sorted(ws, key=len, reverse=True)) + r")(?![\w'])")
           for lvl, ws in _CUE_LEVELS.items()}
_SCOPE = re.compile(r"\byou (?:also )?(?:answer|help|handle|cover|support)\b|\bquestions? (?:about|on)\b|\b(?:in|out of) scope\b"
                    r"|\blimited to\b|\bonly discuss\b", re.I)
_TONE = re.compile(r"\b(?:tone|formal|informal|casual|friendly|polite|warm|calm|empath\w*|apolog\w*|acknowledge|frustrat\w*"
                   r"|plain language|jargon|slang|concise|brief|short|detailed|thorough|humou?r|emoji|reassur\w*|playful|upbeat)\b", re.I)
_TOPICS = sorted({
    "advice_boundary": r"invest|\btax\b|\blegal\b|advice|recommend|product comparison",
    "disclosure": r"virtual assistant|recorded|automated|chatbot|\ban ai\b",
    "fee_limits": r"\bfees?\b|limit|charge|refund|waive|overdraft|dollars|cut-?off|business day|payee|payment|amount|\d",
    "pii_refusal": r"card number|\bpin\b|one-time|identity|verif|account details|password|another customer",
    "routing_escalation": r"hand over|hand off|handoff|escalat|queue|\bteam\b|\bdesk\b|\brefer\b|specialist|colleague|banker",
}.items())
_TOPIC_RX = [(name, re.compile(rx, re.I)) for name, rx in _TOPICS]
_LOOPHOLE = frozenset(["unless", "except", "excluding", "although", "however", "otherwise", "but"])
_NEGATION = frozenset(["no", "not", "never", "without", "cannot", "none", "neither"])
_GUARDS = {"confirm": "confirm", "confirms": "confirm", "confirmed": "confirm", "confirmation": "confirm",
           "verify": "verify", "verifies": "verify", "verified": "verify", "verification": "verify",
           "approve": "approve", "approves": "approve", "approved": "approve", "approval": "approve",
           "consent": "consent", "consents": "consent"}
_TOKEN = re.compile(r"[a-z0-9_]+(?:'[a-z]+)?")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_BULLET = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


# ---------------------------------------------------------------- reading a prompt
def _norm(text: str) -> str:
    return text.replace("’", "'")


def _tokens(text: str) -> frozenset:
    return frozenset(_TOKEN.findall(_norm(text).lower()))


def _key(text: str) -> tuple:
    return tuple(_TOKEN.findall(_norm(text).lower()))


def _jaccard(a: frozenset, b: frozenset) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def parse_prompt(text: str):
    """Split a prompt into statements and comment lines. Returns (statements, comments)."""
    statements, comments, buf = [], [], []

    def flush():
        if buf:
            statements.extend(s.strip() for s in _SENTENCE_END.split(" ".join(buf)) if s.strip())
            del buf[:]

    for raw in re.split(r"\r\n|\r|\n", text):
        line = raw.strip()
        if not line:
            flush()
        elif line.startswith("#"):
            flush()
            comments.append(line)
        else:
            if _BULLET.match(line):
                flush()
                line = _BULLET.sub("", line)
            buf.append(line)
    flush()
    return statements, comments


def strength(text: str) -> int:
    """How firmly a statement binds: 3 absolute (never, must), 2 firm (should), 1 soft (may, try to), 0 no rule word.
    The earliest rule word wins; at the same position the stronger one wins."""
    t = _norm(text).lower()
    best = None
    for lvl, rx in _CUE_RX.items():
        m = rx.search(t)
        if m and (best is None or m.start() < best[0] or (m.start() == best[0] and lvl > best[1])):
            best = (m.start(), lvl)
    return best[1] if best else 0


def _numbers(text: str) -> list:
    return sorted(n.replace(",", "") for n in _NUMBER.findall(text))


def _negations(text: str) -> int:
    return sum(1 for t in _TOKEN.findall(_norm(text).lower()) if t in _NEGATION or t.endswith("n't"))


def _tone_words(text: str) -> frozenset:
    return frozenset(w.lower() for w in _TONE.findall(text))


def _guards(text: str) -> frozenset:
    return frozenset(_GUARDS[t] for t in _TOKEN.findall(_norm(text).lower()) if t in _GUARDS)


def _tools_in(text: str, catalogue: dict) -> frozenset:
    return frozenset(n for n in catalogue if re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", text))


def _topic_slices(*texts) -> list:
    joined = " ".join(t for t in texts if t)
    return [name for name, rx in _TOPIC_RX if rx.search(joined)] or [ALL]


# ---------------------------------------------------------------- aligning two prompts
def _align(old: list, new: list):
    """old, new: lists of statements. Returns (removed, added, pairs) where pairs are (old, new) of one edited statement."""
    new_by_key = {}
    for i, s in enumerate(new):
        new_by_key.setdefault(_key(s), []).append(i)
    used, rest_old = set(), []
    for s in old:
        slot = new_by_key.get(_key(s))
        if slot:
            used.add(slot.pop(0))
        else:
            rest_old.append(s)
    rest_new = [s for i, s in enumerate(new) if i not in used]
    cands = []
    for i, o in enumerate(rest_old):
        for j, n in enumerate(rest_new):
            sim = _jaccard(_tokens(o), _tokens(n))
            if sim >= PAIR_MIN:
                cands.append((sim, i, j))
    cands.sort(key=lambda c: (-c[0], c[1], c[2]))
    pairs, took_o, took_n = [], set(), set()
    for _sim, i, j in cands:
        if i not in took_o and j not in took_n:
            pairs.append((rest_old[i], rest_new[j]))
            took_o.add(i)
            took_n.add(j)
    removed = [s for i, s in enumerate(rest_old) if i not in took_o]
    added = [s for j, s in enumerate(rest_new) if j not in took_n]
    return removed, added, pairs


# ---------------------------------------------------------------- classification
def _finding(kind, dimension, cls, slices, old, new, reason) -> dict:
    return {"kind": kind, "dimension": dimension, "class": cls, "slices": sorted(set(slices)),
            "old": old, "new": new, "reason": reason}


def _tool_slices(tools, catalogue) -> list:
    return sorted({"tool_" + catalogue[t] for t in tools})


def _classify_lone(text, removed, catalogue, stable) -> list:
    """A statement that only exists in one revision."""
    old, new = (text, "") if removed else ("", text)
    verb = "removed" if removed else "added"
    tools = _tools_in(text, catalogue)
    if tools:
        # a grant or a revocation is reported once per prompt; here only a change to a tool that stays granted
        if any(t not in stable for t in tools):
            return []
        return [_finding("tool_instruction_changed", "tools", "REVIEW", _tool_slices(tools, catalogue), old, new,
                         f"a sentence about a tool that stays granted was {verb}")]
    if strength(text) >= 2:
        if removed:
            return [_finding("constraint_removed", "constraints", "BLOCK", _topic_slices(text), old, new,
                             "a rule the assistant was given is gone")]
        return [_finding("constraint_added", "constraints", "REVIEW", _topic_slices(text), old, new,
                         "a new rule; it can make the assistant refuse what it used to answer")]
    if _SCOPE.search(text):
        return [_finding("scope_" + verb, "scope", "REVIEW", ["scope_boundary"], old, new,
                         f"a statement about what the assistant answers was {verb}")]
    if _tone_words(text):
        return [_finding("tone_" + verb, "tone", "REVIEW", ["tone_register"], old, new,
                         f"a statement about register was {verb}")]
    return [_finding("statement_" + verb, "other", "REVIEW", _topic_slices(text), old, new,
                     f"a sentence the rules cannot place was {verb}; treated as unknown, not safe")]


def _classify_pair(old, new, catalogue) -> list:
    """One statement present in both revisions in different words."""
    to, tn = _tools_in(old, catalogue), _tools_in(new, catalogue)
    sim = _jaccard(_tokens(old), _tokens(new))
    if to or tn:
        if to != tn:
            return []
        slices = _tool_slices(to, catalogue)
        if "tool_write" in slices and _guards(old) - _guards(new):
            return [_finding("write_guard_removed", "tools", "BLOCK", slices, old, new,
                             "a write tool lost its confirmation or verification condition")]
        if sim < SAME_MIN:
            return [_finding("tool_instruction_changed", "tools", "REVIEW", slices, old, new,
                             "the instruction for a tool was rewritten")]
        return []
    so, sn = strength(old), strength(new)
    if max(so, sn) >= 2:
        slices = _topic_slices(old, new)
        if sn < so:
            return [_finding("constraint_weakened", "constraints", "BLOCK", slices, old, new,
                             f"rule word strength fell from {so} to {sn} (3 absolute, 2 firm, 1 soft, 0 none)")]
        added = (_tokens(new) - _tokens(old)) & _LOOPHOLE
        if added:
            return [_finding("constraint_exception_added", "constraints", "BLOCK", slices, old, new,
                             f"an exception was added to a rule ({', '.join(sorted(added))})")]
        if _numbers(old) != _numbers(new):
            return [_finding("limit_changed", "constraints", "REVIEW", slices, old, new, "a number in a rule changed")]
        if sn > so:
            return [_finding("constraint_strengthened", "constraints", "REVIEW", slices, old, new,
                             f"rule word strength rose from {so} to {sn}")]
        if sim < SAME_MIN:
            return [_finding("constraint_rewritten", "constraints", "REVIEW", slices, old, new,
                             "a rule keeps its rule word but the wording changed beyond a rephrase")]
        return []
    if _numbers(old) != _numbers(new):
        return [_finding("number_changed", "other", "REVIEW", _topic_slices(old, new), old, new, "a number in a statement changed")]
    if _negations(old) != _negations(new):
        return [_finding("polarity_changed", "other", "REVIEW", _topic_slices(old, new), old, new, "a negation was added or dropped")]
    if _SCOPE.search(old) or _SCOPE.search(new):
        if sim < SAME_MIN:
            return [_finding("scope_changed", "scope", "REVIEW", ["scope_boundary"], old, new, "what the assistant answers was reworded")]
        return []
    if _tone_words(old) or _tone_words(new):
        if _tone_words(old) != _tone_words(new) or sim < SAME_MIN:
            return [_finding("tone_changed", "tone", "REVIEW", ["tone_register"], old, new, "the register words changed")]
        return []
    if sim < SAME_MIN:
        return [_finding("statement_rewritten", "other", "REVIEW", _topic_slices(old, new), old, new,
                         "a sentence the rules cannot place was rewritten; treated as unknown, not safe")]
    return []


def diff_prompts(old_text: str, new_text: str, catalogue: dict | None = None) -> dict:
    """Compare two revisions of one prompt. Returns the findings, whether comment lines changed, and how many statements changed."""
    catalogue = catalogue or {}
    old_s, old_c = parse_prompt(old_text)
    new_s, new_c = parse_prompt(new_text)
    removed, added, pairs = _align(old_s, new_s)
    names_old = frozenset(t for s in old_s for t in _tools_in(s, catalogue))
    names_new = frozenset(t for s in new_s for t in _tools_in(s, catalogue))
    stable = names_old & names_new
    findings = []
    for t in sorted(names_new - names_old):
        write = catalogue[t] == "write"
        findings.append(_finding("tool_granted_write" if write else "tool_granted_read", "tools", "BLOCK" if write else "REVIEW",
                                 ["tool_" + catalogue[t]], "", t,
                                 f"`{t}` is now granted and it {'changes something' if write else 'only reads'}"))
    for t in sorted(names_old - names_new):
        findings.append(_finding("tool_revoked", "tools", "REVIEW", ["tool_" + catalogue[t]], t, "",
                                 f"`{t}` is no longer mentioned, so the assistant may stop using it"))
    for s in removed:
        findings.extend(_classify_lone(s, True, catalogue, stable))
    for s in added:
        findings.extend(_classify_lone(s, False, catalogue, stable))
    for o, n in pairs:
        findings.extend(_classify_pair(o, n, catalogue))
    findings.sort(key=lambda f: (-DECISION_RANK[f["class"]], f["kind"], f["old"], f["new"]))
    return {"findings": findings, "comments_changed": old_c != new_c, "statements_changed": len(removed) + len(added) + len(pairs)}


def decide(findings: list) -> str:
    return max((f["class"] for f in findings), key=lambda c: DECISION_RANK[c], default="ALLOW")


def select_probes(findings: list, probes: list | None) -> dict:
    """The probe slices a change puts at risk, and the probes in them. probes is None when no probe file was given."""
    wanted = sorted({s for f in findings for s in f["slices"]})
    if probes is None:
        return {"slices": [s for s in wanted if s != ALL], "everything": ALL in wanted, "probe_ids": None, "missing": [], "total": None}
    known = sorted({p["slice"] for p in probes})
    chosen = known if ALL in wanted else [s for s in wanted if s in known]
    return {"slices": chosen, "everything": ALL in wanted, "probe_ids": [p["probe_id"] for p in probes if p["slice"] in chosen],
            "missing": [] if ALL in wanted else [s for s in wanted if s not in known], "total": len(probes)}


def analyse(old_text: str, new_text: str, catalogue: dict | None = None, probes: list | None = None) -> dict:
    result = diff_prompts(old_text, new_text, catalogue)
    result["decision"] = decide(result["findings"])
    result["selection"] = select_probes(result["findings"], probes)
    return result


# ---------------------------------------------------------------- loading
def load_prompt(path: str) -> str:
    """Read a prompt file. Raises ValueError when it is empty or holds nothing but headings and comments."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if not text.strip():
        raise ValueError(f"{path}: the prompt file is empty")
    if not parse_prompt(text)[0]:
        raise ValueError(f"{path}: no statements found (only headings or comments)")
    return text


def load_catalogue(path: str) -> dict:
    """{tool name: 'read' or 'write'} from a JSON list of {"name", "access"} objects."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path}: expected a non-empty JSON list of tools")
    out = {}
    for i, t in enumerate(data):
        if not isinstance(t, dict) or not isinstance(t.get("name"), str) or not t["name"].strip():
            raise ValueError(f"{path}: tool {i} needs a string name")
        if t.get("access") not in ("read", "write"):
            raise ValueError(f"{path}: tool {t['name']!r} needs access set to read or write")
        if t["name"] in out:
            raise ValueError(f"{path}: tool {t['name']!r} appears twice")
        out[t["name"]] = t["access"]
    return out


def load_probes(path: str) -> list:
    """Probes from a CSV with at least the columns probe_id and slice."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or not {"probe_id", "slice"} <= set(reader.fieldnames):
            raise ValueError(f"{path}: needs the columns probe_id and slice")
        rows = []
        for n, r in enumerate(reader, 2):
            if not r.get("probe_id") or not r.get("slice"):
                raise ValueError(f"{path}: line {n} has no probe_id or slice")
            rows.append({"probe_id": r["probe_id"], "slice": r["slice"]})
    if not rows:
        raise ValueError(f"{path}: no probes")
    return rows


# ---------------------------------------------------------------- command line
def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so prompt text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(text) -> str:
    return escape_annotation(text).replace(":", "%3A").replace(",", "%2C")


def _clean(text) -> str:
    """Replace control characters other than CR and LF, so prompt text cannot move a terminal cursor or recolor a log."""
    return "".join("?" if (ord(c) < 32 and c not in "\r\n") or 127 <= ord(c) < 160 else c for c in str(text))


def _flat(text, limit=70) -> str:
    t = _clean(text).replace("\r", " ").replace("\n", " ")
    return t if len(t) <= limit else t[:limit - 3] + "..."


def _change(f, limit=70) -> str:
    old = f'"{_flat(f["old"], limit)}"' if f["old"] else "(added)"
    new = f'"{_flat(f["new"], limit)}"' if f["new"] else "(removed)"
    return f"{old} -> {new}"


def _probe_line(sel, decision) -> str:
    if sel["probe_ids"] is None:
        names = "every slice" if sel["everything"] else ", ".join(sel["slices"]) or "none"
        return f"probe slices to run: {names} (no probe file given)"
    if not sel["probe_ids"]:
        return "probes to run: none" if decision == "ALLOW" else "probes to run: none found for the slices this change puts at risk"
    names = "every slice" if sel["everything"] else ", ".join(sel["slices"])
    return f"probes to run: {len(sel['probe_ids'])} of {sel['total']} ({names})"


def render(res, old_path, new_path, fmt, catalogue_given) -> str:
    findings, sel, decision = res["findings"], res["selection"], res["decision"]
    notes = []
    if res["comments_changed"]:
        notes.append("heading or comment lines changed; they are not read")
    if not catalogue_given:
        notes.append("no tool catalogue given (--tools), so tool grants were not checked")
    if sel["missing"]:
        notes.append("the probe file has no probes in: " + ", ".join(sel["missing"]))
    if not res["statements_changed"] and not findings:
        notes.append("no statement changed")
    elif not findings:
        notes.append("statements changed only in wording; no finding")
    if fmt == "github":
        out = []
        for f in findings:
            level = "error" if f["class"] == "BLOCK" else "warning"
            out.append(f"::{level} title={escape_property('prompt-diff-risk ' + f['kind'])}::"
                       + escape_annotation(f"{_clean(os.path.basename(new_path))} {f['dimension']}: {f['reason']}. {_change(f, 90)}"))
        for n in notes:
            out.append("::notice title=prompt-diff-risk::" + escape_annotation(_clean(n)))
        out.append("::notice title=prompt-diff-risk::" + escape_annotation(f"decision {decision}; " + _probe_line(sel, decision)))
        return "\n".join(out)
    lines = [f"prompt: {_flat(os.path.basename(new_path))}   (before: {_flat(os.path.basename(old_path))})"]
    for f in findings:
        lines.append(f"  [{f['class']:<6}] {f['kind']:<27} {f['dimension']:<11} {_change(f)}")
        lines.append(f"             {f['reason']}. slices: {'every slice' if sel['everything'] and ALL in f['slices'] else ', '.join(f['slices'])}")
    lines.extend(f"  note: {n}" for n in notes)
    lines.append(_probe_line(sel, decision))
    lines.append(f"decision: {decision}")
    return "\n".join(lines)


def run_check(old_path, new_path, tools_path, probes_path, fail_on, fmt) -> int:
    try:
        old, new = load_prompt(old_path), load_prompt(new_path)
        catalogue = load_catalogue(tools_path) if tools_path else {}
        probes = load_probes(probes_path) if probes_path else None
    except (OSError, ValueError, csv.Error, RecursionError) as e:
        print(f"input error: {_flat(e, 300)}", file=sys.stderr)
        return 2
    res = analyse(old, new, catalogue, probes)
    print(render(res, old_path, new_path, fmt, bool(tools_path)))
    if fail_on == "never":
        return 0
    return 1 if DECISION_RANK[res["decision"]] >= DECISION_RANK[{"block": "BLOCK", "review": "REVIEW"}[fail_on]] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="prompt_diff_risk")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_*.txt)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="compare two prompt files")
    c.add_argument("old")
    c.add_argument("new")
    c.add_argument("--tools", help="tool catalogue (JSON list of {name, access}); without it tool grants are not checked")
    c.add_argument("--probes", help="probe set (CSV with probe_id and slice); without it only slice names are printed")
    c.add_argument("--fail-on", choices=["block", "review", "never"], default="block")
    c.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_old.txt"), os.path.join(d, "example_new.txt"),
                         os.path.join(d, "tools.json"), os.path.join(d, "probes.csv"), "never", "text")
    if a.cmd == "check":
        return run_check(a.old, a.new, a.tools, a.probes, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
