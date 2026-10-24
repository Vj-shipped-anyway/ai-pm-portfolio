"""Step 3 - Where each reader fails when the exception is somewhere else.

The full sweep: 210 questions over three manuals (50, 150 and 300 pages), seven forms (a plain rule, and an
exception inline, adjacent, crossref, restated, register or nested), five depths, and for each exception one
question where it applies and one where it does not. Three deficiencies show up, one per faulty reader.

KNOWN LIMIT, left in on purpose: a score that only compares answers cannot tell a reader that read an
exception and decided it did not apply from one that never looked. Step 4 does not remove it.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import READERS, load_manuals, load_sweep, run_reader
from credit_policy_needle import score_probes

probes, manuals = load_sweep(), load_manuals()
FORMS = ["plain", "inline", "adjacent", "crossref", "restated", "register", "nested"]
DEPTHS = [0, 25, 50, 75, 100]
answers = {name: run_reader(name, probes, manuals) for name in READERS}


def passed(name, subset):
    return score_probes(subset, answers[name])["passed"]


print("STEP 3 - the full sweep, 210 questions")
print("  pass by form, out of 30 per form (3 manuals x 5 depths x 2 questions)")
print(f"  {'form':<10}" + "".join(f"{n:>12}" for n in READERS))
for form in FORMS:
    sub = [p for p in probes if p["form"] == form]
    print(f"  {form:<10}" + "".join(f"{passed(n, sub):>12}" for n in READERS))
print(f"  {'all':<10}" + "".join(f"{passed(n, probes):>12}" for n in READERS))

print("  Deficiency 1, position (truncating): pass by depth of the rule clause, out of 42 per depth")
print("    " + "   ".join(f"{d}%: {passed('truncating', [p for p in probes if p['depth_pct'] == d])}" for d in DEPTHS))
for pages in (50, 150, 300):
    sub = [p for p in probes if p["length_pages"] == pages]
    print(f"    {pages} pages: {passed('truncating', sub)} of {len(sub)}")
applies = [p for p in probes if p["variant"] == "applies"]
print(f"  Deficiency 2, exception never read (base_only): passes {passed('base_only', applies)} of {len(applies)} questions where an exception applies")
far = [p for p in probes if p["form"] in ("crossref", "restated", "register") and p["variant"] == "applies"]
near = [p for p in probes if p["form"] in ("inline", "adjacent") and p["variant"] == "applies"]
carved = [p for p in probes if p["variant"] == "carved_out"]
print(f"  Deficiency 3, exception out of reach (retrieval): passes {passed('retrieval', near)} of {len(near)} with the exception beside the rule,"
      f" {passed('retrieval', far)} of {len(far)} with it elsewhere, {passed('retrieval', carved)} of {len(carved)} when a far clause cancels it")

not_applying = [p for p in probes if p["variant"] in ("not_met", "carved_out")]
print("  KNOWN LIMIT: answers alone do not show whether the exception was read")
print(f"    base_only never reads an exception and passes {passed('base_only', not_applying)} of {len(not_applying)} questions where the exception does not apply")
print("    a suite made only of those questions would pass it; the paired question where the exception applies is what fails it")
