"""Step 3 - Deficiencies exposed: where re-adding the form goes wrong, and what each check buys alone.

The form answers are wrong in three places the rubric cares about: the data class is set below the
dataset's true class, the vendor dependency is left as 'none', and the customer-facing answer is wrong,
blank or 'unsure'. Each of the three checks in tiergate.py addresses one of them from a second source:
the data catalog, the vendor registry, and the words in the title and description.

KNOWN LIMIT, left in on purpose: when the form understates the data class and the catalog is stale or
has no entry, there is no second source to disagree with the form. Step 4 does not catch these either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from __future__ import annotations

from common import form_as_written_tier, load_cases, load_second_sources, metrics, pct
from tiergate import CLASS_ORDER, recompute

cases = load_cases()
catalog, registry = load_second_sources()

basic = {c["use_case_id"]: form_as_written_tier(c) for c in cases}
variants = [
    ("form as written", basic),
    ("text rules only", {c["use_case_id"]: recompute(c, None, None)["tier"] for c in cases}),
    ("catalog only", {c["use_case_id"]: recompute(c, catalog, None, check_text=False)["tier"] for c in cases}),
    ("registry only", {c["use_case_id"]: recompute(c, None, registry, check_text=False)["tier"] for c in cases}),
    ("all three", {c["use_case_id"]: recompute(c, catalog, registry)["tier"] for c in cases}),
]


def below(a: str, b: str) -> bool:
    return CLASS_ORDER.index(a) < CLASS_ORDER.index(b)


wrong = [c for c in cases if basic[c["use_case_id"]] != c["reference_tier"]]
class_low = [c for c in wrong if below(c["data_class"], c["true_data_class"])]
vendor_low = [c for c in wrong if c["vendor_model"] != c["true_vendor_model"]]
cf_wrong = [c for c in wrong if c["customer_facing"] != c["true_customer_facing"]]

print("STEP 3 - where the form-as-written recompute goes wrong")
print(f"  forms still at the wrong tier after step 2: {len(wrong)} of {len(cases)}")
print(f"  a form can have more than one wrong input; among those {len(wrong)}:")
print(f"    data class set below the true class: {len(class_low)}")
print(f"    vendor model left as none or understated: {len(vendor_low)}")
print(f"    customer-facing answer wrong, blank or 'unsure': {len(cf_wrong)}")
print("  one check at a time (tier equals the reference; tier 3-4 caught; below; above):")
for label, tiers in variants:
    m = metrics(cases, tiers)
    print(f"    {label:<16} equal {m['exact']:>3}   tier 3-4 caught {m['full_caught']:>2} of {m['full']}   "
          f"below {m['under']:>2}   above {m['over']:>2}")
text_only = variants[1][1]
raised_wrong = sum(1 for c in cases
                   if text_only[c["use_case_id"]] > c["reference_tier"] and basic[c["use_case_id"]] <= c["reference_tier"])
print(f"  the text rules alone push {raised_wrong} forms above their reference tier that the form had at or below it")

planted_cat = [c for c in cases if "class_understated_in_form_and_catalog" in c["planted"]]
planted_unl = [c for c in cases if "class_understated_dataset_not_listed" in c["planted"]]
print("  KNOWN LIMIT: the data class is wrong on the form and no second source disagrees:")
print(f"    catalog entry is stale and understates the class too: {len(planted_cat)} of {len(cases)}")
print(f"    dataset has no catalog entry: {len(planted_unl)} of {len(cases)}")
print(f"    together: {len(planted_cat) + len(planted_unl)} of {len(cases)} ({pct(len(planted_cat) + len(planted_unl), len(cases))})")
