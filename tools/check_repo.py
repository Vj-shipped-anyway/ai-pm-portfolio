#!/usr/bin/env python3
"""Check that every project in this repo runs as its README claims.

Standard library only, Python 3.9 or newer. From the repo root:

    python3 tools/check_repo.py                # every project
    python3 tools/check_repo.py 11 26          # only projects 11 and 26
    python3 tools/check_repo.py --exclude 02   # every project except 02 (it needs numpy, pandas and scipy)
    python3 tools/check_repo.py --list         # show the checks and exit

For each project folder it checks:

  steps      the four step scripts in src/ exit 0 (run from src/, with a clean copy of the folder)
  generator  data/_generate.py, when present, reproduces the committed data files byte for byte
  svg        every assets/*.svg parses
  links      every relative link in README, PRD and ARCHITECTURE points at a file that exists
  demo       the inline scripts in demo.html pass `node --check` (skipped when node is missing)
  tests      tests/ runs under unittest, when present
  numbers    every digit string after a green tag in the README appears in the scripts' printed output,
             the files they write to src/out/, or data/README.md. A few older projects have known
             exceptions; tools/claims_baseline.json holds the count for each, and the check fails only
             when a project has more unmatched numbers than its baseline.

Exit status is 0 when every hard check passes.
"""
from __future__ import annotations

import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = json.loads((ROOT / "tools" / "claims_baseline.json").read_text(encoding="utf-8")) \
    if (ROOT / "tools" / "claims_baseline.json").exists() else {}
STEP_TIMEOUT = 300
GREEN = "\U0001F7E2"
TAGS = ("\U0001F7E1", "\U0001F534")


def projects(only, exclude=()):
    folders = sorted(p for p in ROOT.iterdir() if p.is_dir() and re.match(r"\d\d-", p.name))
    if only:
        folders = [p for p in folders if p.name[:2] in only]
    return [p for p in folders if p.name[:2] not in exclude]


def run(cmd, cwd, timeout=STEP_TIMEOUT):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)


def check_steps(work: Path):
    """Run the step scripts in the scratch copy. Returns (problems, corpus_text)."""
    problems, corpus = [], []
    steps = sorted((work / "src").glob("step_0[1-4]_*.py"))
    if len(steps) != 4:
        problems.append("expected 4 step scripts, found %d" % len(steps))
    for s in steps:
        try:
            r = run([sys.executable, s.name], work / "src")
        except subprocess.TimeoutExpired:
            problems.append("%s timed out after %ds" % (s.name, STEP_TIMEOUT))
            continue
        corpus.append(r.stdout)
        if r.returncode != 0:
            tail = (r.stderr.strip().splitlines() or [""])[-1][:140]
            problems.append("%s exit %d: %s" % (s.name, r.returncode, tail))
    out = work / "src" / "out"
    if out.exists():
        for f in out.iterdir():
            try:
                corpus.append(f.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, OSError):
                pass
    return problems, "\n".join(corpus)


def check_generator(src: Path, work: Path):
    gen = src / "data" / "_generate.py"
    if not gen.exists():
        return []
    try:
        r = run([sys.executable, "_generate.py"], work / "data")
    except subprocess.TimeoutExpired:
        return ["_generate.py timed out"]
    if r.returncode != 0:
        return ["_generate.py exit %d: %s" % (r.returncode, (r.stderr.strip().splitlines() or [""])[-1][:140])]
    bad = []
    for f in sorted((src / "data").glob("*")):
        if f.suffix not in (".csv", ".json", ".txt"):
            continue
        g = work / "data" / f.name
        if not g.exists() or not filecmp.cmp(str(f), str(g), shallow=False):
            bad.append(f.name)
    return ["regenerated data differs from committed: " + ", ".join(bad)] if bad else []


def check_svg(src: Path):
    bad = []
    for f in sorted((src / "assets").glob("*.svg")) if (src / "assets").exists() else []:
        try:
            ET.parse(str(f))
        except ET.ParseError as e:
            bad.append("%s: %s" % (f.name, e))
    return bad


def check_links(src: Path):
    bad = []
    for name in ("README.md", "PRD.md", "ARCHITECTURE.md"):
        f = src / name
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        for m in re.findall(r"\]\((\.{1,2}/[^)#\s]*)", text):
            if not (src / m).resolve().exists():
                bad.append("%s -> %s" % (name, m))
    return bad


def check_demo(src: Path):
    demo = src / "demo.html"
    if not demo.exists():
        return ["demo.html missing"]
    node = shutil.which("node")
    if not node:
        return []
    text = demo.read_text(encoding="utf-8")
    bad = []
    for i, js in enumerate(re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", text, re.S)):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
            t.write(js)
        try:
            r = subprocess.run([node, "--check", t.name], capture_output=True, text=True)
            if r.returncode != 0:
                bad.append("inline script %d: %s" % (i, (r.stderr.strip().splitlines() or [""])[0][:120]))
        finally:
            os.unlink(t.name)
    return bad


def check_tests(work: Path):
    if not (work / "tests").exists():
        return []
    r = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], work, timeout=900)
    if r.returncode != 0:
        return ["unittest failed: " + (r.stderr.strip().splitlines() or [""])[-1][:140]]
    return []


def unmatched_numbers(src: Path, corpus: str):
    """Digit strings that follow a green tag in the README but appear in no printed output."""
    readme = (src / "README.md").read_text(encoding="utf-8")
    data_readme = src / "data" / "README.md"
    evidence = corpus + "\n" + (data_readme.read_text(encoding="utf-8") if data_readme.exists() else "")
    evidence = evidence.replace(",", "")
    missing = []
    for line in readme.split("\n"):
        if GREEN not in line:
            continue
        for seg in re.findall(GREEN + r"(.*?)(?=" + GREEN + "|" + TAGS[0] + "|" + TAGS[1] + "|$)", line):
            for tok in re.findall(r"\d[\d,]*\.?\d*", seg):
                t = tok.replace(",", "").rstrip(".")
                if len(t.replace(".", "")) < 2 or t in ("2025", "2026"):
                    continue
                if t not in evidence:
                    missing.append(t)
    return missing


def check_project(src: Path):
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / src.name
        shutil.copytree(str(src), str(work), ignore=shutil.ignore_patterns("out", "__pycache__"))
        steps, corpus = check_steps(work)
        results["steps"] = steps
        results["generator"] = check_generator(src, work)
        results["tests"] = check_tests(work)
    results["svg"] = check_svg(src)
    results["links"] = check_links(src)
    results["demo"] = check_demo(src)
    miss = unmatched_numbers(src, corpus)
    allowed = BASELINE.get(src.name[:2], 0)
    results["numbers"] = (
        ["%d unmatched green numbers, baseline %d: %s" % (len(miss), allowed, ", ".join(miss[:8]))]
        if len(miss) > allowed else [])
    return results, len(miss), allowed


def main(argv):
    if "--list" in argv:
        print(__doc__)
        return 0
    exclude = []
    if "--exclude" in argv:
        exclude = argv[argv.index("--exclude") + 1].split(",")
    only = [a for a in argv if re.fullmatch(r"\d\d", a) and a not in exclude]
    failed = 0
    for src in projects(only, exclude):
        results, n_miss, allowed = check_project(src)
        problems = [(k, p) for k, v in results.items() for p in v]
        mark = "ok  " if not problems else "FAIL"
        note = "" if n_miss == 0 else "  (%d green numbers outside the printed output; baseline %d)" % (n_miss, allowed)
        print("%s %s%s" % (mark, src.name, note))
        for k, p in problems:
            print("       %-9s %s" % (k, p))
        failed += 1 if problems else 0
    print("\n%d project(s) failed" % failed if failed else "\nall checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
