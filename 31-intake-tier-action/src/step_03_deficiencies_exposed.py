"""Step 3 - Where the issue form and the regex break: seven named deficiencies, each with a count.

  (a) a body the regex cannot read still gets a tier label
  (b) the data class is never compared with the catalog
  (c) the customer-facing answer is blank, unsure or wrong, and scores 0
  (d) a vendor dependency left off the form is never checked against the registry
  (e) a pasted block that repeats a heading overrides the real answer
  (f) a re-run on edit leaves two tier labels and a second comment
  (g) the workflow echoes issue text into the log as written

KNOWN LIMIT, left in on purpose and printed at the end: when the form AND the catalog both understate a
data class, the cross-check in step 4 agrees with the wrong answer.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
import os

from common import DATA, CHOICES, assess, events, load_catalog, load_issues, load_registry, naive_assess, naive_field

issues = load_issues()
catalog = load_catalog(os.path.join(DATA, "catalog.csv"))
registry = load_registry(os.path.join(DATA, "registry.csv"))
order = CHOICES["data_class"].index
n = len(issues)
naive = {i["issue"]: naive_assess(i["body_v1"]) for i in issues}
print("STEP 3 - seven deficiencies of the issue form and regex (green, measured on %d synthetic issues)" % n)

unread = [i for i in issues if naive[i["issue"]]["found"] < 5]
print("\n(a) A BODY THE REGEX CANNOT READ STILL GETS A TIER")
print(f"    {len(unread)} of {n} bodies lack at least one of the 5 required inputs and were labeled anyway; "
      f"{sum(1 for i in unread if i['ref'] >= 3)} of them are tier 3-4 and {sum(1 for i in unread if i['ref'] >= 3 and naive[i['issue']]['tier'] < 3)} got tier 1-2.")

def below_catalog(i) -> bool:
    ds, cls = naive_field(i["body_v1"], "Dataset name"), naive_field(i["body_v1"], "Data class")
    return ds in catalog and cls in CHOICES["data_class"] and order(cls) < order(catalog[ds])


below_cat = [i for i in issues if below_catalog(i)]
below_true = [i for i in issues if order(i["form_data_class"]) < order(i["true"]["data_class"])]
both = [i for i in below_true if order(catalog[i["dataset"]]) < order(i["true"]["data_class"])]
print("\n(b) THE DATA CLASS IS NEVER COMPARED WITH THE CATALOG")
print(f"    comparisons made: 0. {len(below_cat)} forms declare a class below the one the catalog records.")
print(f"    {len(below_true)} forms declare a class below the true class; on {len(both)} of those the catalog is below the true class too.")

blank = [i for i in issues if naive_field(i["body_v1"], "Customer-facing") == ""]
unsure = [i for i in issues if naive_field(i["body_v1"], "Customer-facing") == "unsure"]
wrong_no = [i for i in issues if naive_field(i["body_v1"], "Customer-facing") == "no" and i["true"]["customer_facing"] == "yes"]
print("\n(c) THE CUSTOMER-FACING ANSWER SCORES 0 WHEN IT IS BLANK, UNSURE OR WRONG")
print(f"    {len(blank)} blank or unreadable, {len(unsure)} 'unsure', {len(wrong_no)} 'no' on a customer-facing case: {len(blank) + len(unsure) + len(wrong_no)} of {n}.")

dependent = [i for i in issues if i["true"]["vendor"] != "none"]
omitted = [i for i in dependent if naive_field(i["body_v1"], "Vendor model") == "none"]
listed = [i for i in omitted if i["issue"] in registry]
print("\n(d) A VENDOR DEPENDENCY LEFT OFF THE FORM IS NEVER CHECKED")
print(f"    {len(dependent)} of {n} issues depend on a self-hosted or vendor model; {len(omitted)} of those say 'none'; "
      f"the registry lists {len(listed)} of those {len(omitted)}.")

pasted = [i for i in issues if i["kind"] == "pasted_heading"]
wrong_read = [i for i in pasted if naive_field(i["body_v1"], "Data class") == i["pasted"] != i["form_data_class"]]
print("\n(e) A PASTED BLOCK THAT REPEATS A HEADING OVERRIDES THE REAL ANSWER")
print(f"    {len(pasted)} bodies repeat the 'Data class' heading inside the summary; the regex reads the pasted value on {len(wrong_read)} of them.")

edited = [i for i in issues if i["edited"]]
two = [i for i in edited if len({naive_assess(b)["tier"] for b in events(i)}) > 1]
print("\n(f) A RE-RUN ON EDIT LEAVES TWO TIER LABELS AND A SECOND COMMENT")
print(f"    {len(edited)} issues were edited after opening. With add-only labels, {len(two)} of them end with two tier labels.")
print(f"    Comments posted: {sum(len(events(i)) for i in issues)} for {n} issues.")

forged = [i for i in issues if any(ln.startswith("::") for ln in i["body_v1"].splitlines())]
print("\n(g) THE WORKFLOW ECHOES ISSUE TEXT INTO THE LOG AS WRITTEN")
print(f"    {len(forged)} of {n} bodies carry a line that starts with '::', the form a workflow command takes; echoed unescaped, it can be read as one.")

print("\nKNOWN LIMIT, left in on purpose")
rows = {i["issue"]: assess(i["body_v1"], catalog, registry, i["issue"]) for i in issues}
still = [i for i in below_true if rows[i["issue"]]["decision"] == "TIERED" and order(rows[i["issue"]]["rows"][2][1]) < order(i["true"]["data_class"])]
no_dataset = [i for i in still if any(f["code"] == "DATASET_NOT_GIVEN" for f in rows[i["issue"]]["flags"])]
print(f"    The cross-check in step 4 still reads a data class below the true class on {len(still)} of {len(below_true)} understated forms")
print(f"    (the dataset is named and the catalog is below the true class too on {len(still) - len(no_dataset)}; the sponsor left the dataset blank on {len(no_dataset)}).")
