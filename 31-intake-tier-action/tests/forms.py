"""A small renderer for test bodies, written the way an issue form writes them."""
DEFAULT = {"summary": "Drafts internal reports for the operations team.", "unit": "Cards Operations", "dataset": "d_policy_library",
           "customer_facing": "no", "autonomy": "advisory", "data_class": "internal", "vendor": "none", "regulatory": "none",
           "exposure": "lt_1m", "declared": "1"}
LABELS = [("summary", "Use case summary"), ("unit", "Sponsor unit"), ("dataset", "Dataset name"), ("customer_facing", "Customer-facing"),
          ("autonomy", "Decision autonomy"), ("data_class", "Data class"), ("vendor", "Vendor model"), ("regulatory", "Regulatory scope"),
          ("exposure", "Financial exposure band"), ("declared", "Declared tier")]


def body(**over) -> str:
    v = dict(DEFAULT)
    v.update(over)
    return "\n\n".join("### %s\n\n%s" % (label, v[k] or "_No response_") for k, label in LABELS) + "\n"
