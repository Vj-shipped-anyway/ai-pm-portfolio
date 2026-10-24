"""Generate the synthetic data for project 28: 67 pull requests that each change one tool schema,
and 400 recorded calls made against the schemas as they were before the changes.

Everything is seeded, so the files are byte-for-byte reproducible. The truth label of each pull
request comes from the change that was planted, not from any classifier. Two kinds are hard on
purpose: rewording that keeps the same numbers (a harmless change a unit check could flag) and a
scale change that keeps the unit word (a risky change the unit check cannot see).

Run (from data/):  python3 _generate.py
Writes:  tools_base.json, pr_cases.csv, pr_truth.csv, recorded_calls.csv, example_old.json,
         example_new.json, example_calls.csv
"""
import copy
import csv
import json
import random

rng = random.Random(28)


def P(t, d, **kw):
    return dict(type=t, description=d, **kw)


TOOLS = {
    "get_account_balance": dict(version="1.0.0", description="Return the balance of one account.", required=["account_id"], properties={
        "account_id": P("string", "Account identifier."),
        "balance_type": P("string", "Which balance to return.", enum=["available", "pending", "ledger"], default="available"),
        "include_holds": P("boolean", "Include funds on hold.")}),
    "transfer_funds": dict(version="1.2.0", description="Move money between two accounts of one customer.", required=["from_account", "to_account", "amount"], properties={
        "from_account": P("string", "Source account identifier."),
        "to_account": P("string", "Destination account identifier."),
        "amount": P("number", "Amount to move, in dollars.", minimum=0.01, maximum=50000),
        "memo": P("string", "Free-text note.", maxLength=140)}),
    "get_transaction_history": dict(version="1.3.0", description="List recent transactions.", required=["account_id"], properties={
        "account_id": P("string", "Account identifier."),
        "days_back": P("integer", "How many days back to look, 1 to 90 days.", minimum=1, maximum=90, default=30),
        "limit": P("integer", "Maximum rows returned.", minimum=1, maximum=200, default=50)}),
    "block_card": dict(version="1.0.0", description="Block a card.", required=["card_id", "reason"], properties={
        "card_id": P("string", "Card identifier."),
        "reason": P("string", "Why the card is blocked.", enum=["lost", "stolen", "fraud_suspected", "customer_request"]),
        "notify_customer": P("boolean", "Send a notification to the customer.")}),
    "calculate_loan_payment": dict(version="1.0.0", description="Calculate the periodic payment on an amortizing loan.", required=["principal", "annual_rate_pct", "term_months"], properties={
        "principal": P("number", "Loan amount, in dollars.", minimum=1000, maximum=2000000),
        "annual_rate_pct": P("number", "Annual interest rate as a percent.", minimum=0, maximum=40),
        "term_months": P("integer", "Loan term, in months.", minimum=6, maximum=360)}),
    "create_support_ticket": dict(version="1.1.0", description="Open a support ticket for a customer.", required=["customer_id", "category"], properties={
        "customer_id": P("string", "Customer identifier."),
        "category": P("string", "Ticket category.", enum=["card", "payments", "online_banking", "other"]),
        "priority": P("string", "Ticket priority.", enum=["low", "normal", "high"], default="normal"),
        "description": P("string", "What the customer reports.", maxLength=500)}),
    "schedule_payment": dict(version="2.0.0", description="Schedule a bill payment.", required=["account_id", "payee_id", "amount"], properties={
        "account_id": P("string", "Paying account identifier."),
        "payee_id": P("string", "Payee identifier."),
        "amount": P("number", "Payment amount, in dollars.", minimum=1, maximum=25000),
        "run_in_days": P("integer", "Days until the payment runs, 0 to 60 days.", minimum=0, maximum=60, default=0)}),
    "get_fx_rate": dict(version="1.0.0", description="Return an indicative exchange rate.", required=["base_currency", "quote_currency"], properties={
        "base_currency": P("string", "Three-letter base currency code.", enum=["USD", "EUR", "GBP", "CAD", "CHF"]),
        "quote_currency": P("string", "Three-letter quote currency code.", enum=["USD", "EUR", "GBP", "CAD", "CHF"]),
        "rate_type": P("string", "Rate to return.", enum=["mid", "buy", "sell"], default="mid")}),
    "order_checks": dict(version="1.0.0", description="Order a box of checks.", required=["account_id", "quantity"], properties={
        "account_id": P("string", "Account identifier."),
        "quantity": P("integer", "Number of checks, 25 to 400.", minimum=25, maximum=400),
        "expedite": P("boolean", "Pay for faster delivery.")}),
    "update_contact_preferences": dict(version="1.4.0", description="Change how a customer is contacted.", required=["customer_id", "channel"], properties={
        "customer_id": P("string", "Customer identifier."),
        "channel": P("string", "Contact channel.", enum=["email", "sms", "phone", "mail"]),
        "opt_in": P("boolean", "Whether the customer agrees to be contacted on this channel.")}),
}

QUOTA = [("rename_param", "breaking", 5), ("remove_param", "breaking", 4), ("add_required", "breaking", 5),
         ("enum_remove", "breaking", 4), ("type_narrow", "breaking", 3), ("bounds_tighten", "breaking", 4),
         ("add_optional", "non_breaking", 5), ("enum_add", "non_breaking", 4), ("type_widen", "non_breaking", 3),
         ("reword", "non_breaking", 6), ("version_only", "non_breaking", 5),
         ("default_change", "behavior_risk", 4), ("unit_swap", "behavior_risk", 5), ("meaning_flip", "behavior_risk", 3),
         ("reword_numbers", "non_breaking", 4), ("unit_scale", "behavior_risk", 3)]


def bump(v, level):
    a, b, c = (int(x) for x in v.split("."))
    return f"{a + 1}.0.0" if level == "major" else f"{a}.{b + 1}.0" if level == "minor" else f"{a}.{b}.{c + 1}"


def mutate(kind, s):
    """Return (new_schema, changed_param) or None when the tool has nothing this change can touch."""
    n = copy.deepcopy(s)
    props = n["parameters"]["properties"]
    req = n["parameters"]["required"]
    opt = [k for k in props if k not in req]
    if kind == "rename_param":
        c = [k for k in props if k not in req or props[k]["type"] != "boolean"]
        k = rng.choice(c)
        props[k + "_v2" if k.endswith("id") is False else k.replace("_id", "_ref")] = props.pop(k)
        if k in req:
            new = k + "_v2" if k.endswith("id") is False else k.replace("_id", "_ref")
            req[req.index(k)] = new
        n["version"] = bump(s["version"], "patch")
        return n, k
    if kind == "remove_param":
        if not opt:
            return None
        k = rng.choice(opt)
        del props[k]
        n["version"] = bump(s["version"], "minor")
        return n, k
    if kind == "add_required":
        props["channel_code"] = P("string", "Channel that originated the request.")
        req.append("channel_code")
        n["version"] = bump(s["version"], "minor")
        return n, "channel_code"
    if kind == "enum_remove":
        c = [k for k in props if "enum" in props[k] and len(props[k]["enum"]) > 2]
        if not c:
            return None
        k = rng.choice(c)
        props[k]["enum"] = props[k]["enum"][:-1]
        if props[k].get("default") not in props[k]["enum"]:
            props[k]["default"] = props[k]["enum"][0]
        n["version"] = bump(s["version"], "minor")
        return n, k
    if kind == "type_narrow":
        c = [k for k in props if props[k]["type"] == "number"]
        if not c:
            return None
        k = rng.choice(c)
        props[k]["type"] = "integer"
        n["version"] = bump(s["version"], "minor")
        return n, k
    if kind == "bounds_tighten":
        c = [k for k in props if "maximum" in props[k]]
        if not c:
            return None
        k = rng.choice(c)
        lo, hi = props[k].get("minimum", 0), props[k]["maximum"]
        props[k]["maximum"] = type(hi)(lo + (hi - lo) * 0.4) if isinstance(hi, int) else round(lo + (hi - lo) * 0.4, 2)
        n["version"] = bump(s["version"], "patch")
        return n, k
    if kind == "add_optional":
        props["trace_id"] = P("string", "Caller trace identifier.")
        n["version"] = bump(s["version"], "minor")
        return n, "trace_id"
    if kind == "enum_add":
        c = [k for k in props if "enum" in props[k] and props[k]["type"] == "string"]
        if not c:
            return None
        k = rng.choice(c)
        props[k]["enum"] = props[k]["enum"] + ["other_value"]
        n["version"] = bump(s["version"], "minor")
        return n, k
    if kind == "type_widen":
        c = [k for k in props if props[k]["type"] == "integer"]
        if not c:
            return None
        k = rng.choice(c)
        props[k]["type"] = "number"
        n["version"] = bump(s["version"], "minor")
        return n, k
    if kind == "reword":
        k = rng.choice([k for k in props if props[k]["description"]])
        props[k]["description"] = props[k]["description"].rstrip(".") + ", as supplied by the caller."
        n["version"] = bump(s["version"], "patch")
        return n, k
    if kind == "version_only":
        n["version"] = bump(s["version"], "patch")
        return n, ""
    if kind == "default_change":
        c = [k for k in props if "default" in props[k]]
        if not c:
            return None
        k = rng.choice(c)
        d = props[k]["default"]
        if "enum" in props[k]:
            props[k]["default"] = [e for e in props[k]["enum"] if e != d][0]
        else:
            props[k]["default"] = d * 2 if d else 7
        n["version"] = bump(s["version"], "patch")
        return n, k
    if kind == "unit_swap":
        swaps = [("in dollars", "in cents"), ("in months", "in years"), ("1 to 90 days", "1 to 90 hours"),
                 ("0 to 60 days", "0 to 60 hours"), ("25 to 400", "25 to 400 sheets"), ("as a percent", "in basis points")]
        for k in rng.sample(list(props), len(props)):
            for a, b in swaps:
                if a in props[k]["description"]:
                    props[k]["description"] = props[k]["description"].replace(a, b)
                    n["version"] = bump(s["version"], "patch")
                    return n, k
        return None
    if kind == "reword_numbers":
        # same numbers and units, different words: a harmless change a naive unit check could flag
        forms = [("1 to 90 days", "between 1 and 90 days"), ("0 to 60 days", "between 0 and 60 days"), ("25 to 400", "between 25 and 400")]
        for k in rng.sample(list(props), len(props)):
            for a, b in forms:
                if a in props[k]["description"]:
                    props[k]["description"] = props[k]["description"].replace(a, b)
                    n["version"] = bump(s["version"], "patch")
                    return n, k
        return None
    if kind == "unit_scale":
        # the unit word is unchanged but the scale moves: dollars become thousands of dollars
        for k in rng.sample(list(props), len(props)):
            if "in dollars" in props[k]["description"]:
                props[k]["description"] = props[k]["description"].replace("in dollars", "in thousands of dollars")
                n["version"] = bump(s["version"], "patch")
                return n, k
        return None
    if kind == "meaning_flip":
        k = rng.choice(list(props))
        props[k]["description"] = props[k]["description"].rstrip(".") + ", exclusive of the end date."
        n["version"] = bump(s["version"], "patch")
        return n, k
    return None


def full(name, t):
    return dict(name=name, version=t["version"], description=t["description"],
                parameters=dict(type="object", properties=copy.deepcopy(t["properties"]), required=list(t["required"])))


BASE = {name: full(name, t) for name, t in TOOLS.items()}


def make_value(k, spec):
    if "enum" in spec:
        return rng.choice(spec["enum"])
    t = spec["type"]
    if t == "string":
        if k.endswith("_id") or k.endswith("_account") or k.endswith("_ref"):
            return f"{k[:3].upper()}-{rng.randint(100000, 999999)}"
        return "note " + str(rng.randint(1, 99))
    if t == "boolean":
        return rng.choice([True, False])
    lo, hi = spec.get("minimum", 1), spec.get("maximum", 100)
    if t == "integer":
        return rng.randint(int(lo), int(hi))
    return round(rng.uniform(lo, hi), 2)


def make_calls():
    calls = []
    for name, s in BASE.items():
        props, req = s["parameters"]["properties"], s["parameters"]["required"]
        for _ in range(40):
            args = {k: make_value(k, v) for k, v in props.items() if k in req or rng.random() < 0.6}
            calls.append((name, args))
    rng.shuffle(calls)
    return calls


def main():
    calls = make_calls()
    cases, truth = [], []
    names = sorted(BASE)
    for kind, cls, count in QUOTA:
        made = 0
        while made < count:
            tool = rng.choice(names)
            res = mutate(kind, BASE[tool])
            if res is None:
                continue
            new, param = res
            cases.append((tool, BASE[tool], new))
            truth.append((kind, cls, param))
            made += 1
    order = list(range(len(cases)))
    rng.shuffle(order)
    with open("tools_base.json", "w", encoding="utf-8") as f:
        json.dump(BASE, f, indent=1, sort_keys=True)
        f.write("\n")
    with open("pr_cases.csv", "w", newline="", encoding="utf-8") as f, open("pr_truth.csv", "w", newline="", encoding="utf-8") as g:
        w, t = csv.writer(f), csv.writer(g)
        w.writerow(["pr_id", "tool", "old_schema_json", "new_schema_json"])
        t.writerow(["pr_id", "change_kind", "truth_class", "changed_param"])
        for i, j in enumerate(order, 1):
            pid = f"PR-{i:03d}"
            tool, old, new = cases[j]
            w.writerow([pid, tool, json.dumps(old, sort_keys=True), json.dumps(new, sort_keys=True)])
            t.writerow([pid, truth[j][0], truth[j][1], truth[j][2]])
    with open("recorded_calls.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["call_id", "tool", "args_json"])
        for i, (tool, args) in enumerate(calls, 1):
            w.writerow([f"C{i:04d}", tool, json.dumps(args, sort_keys=True)])
    # a small worked example for the command line: one breaking change on transfer_funds
    ex_old = BASE["block_card"]
    ex_new = copy.deepcopy(ex_old)
    ex_new["version"] = "1.0.1"
    ex_new["parameters"]["properties"]["reason"]["enum"] = ["lost", "stolen", "fraud_suspected"]
    with open("example_old.json", "w", encoding="utf-8") as f:
        json.dump(ex_old, f, indent=1, sort_keys=True); f.write("\n")
    with open("example_new.json", "w", encoding="utf-8") as f:
        json.dump(ex_new, f, indent=1, sort_keys=True); f.write("\n")
    with open("example_calls.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["call_id", "tool", "args_json"])
        k = 0
        for tool, args in calls:
            if tool == "block_card":
                k += 1
                w.writerow([f"E{k:03d}", tool, json.dumps(args, sort_keys=True)])
    print(f"wrote {len(cases)} pull requests and {len(calls)} recorded calls")


if __name__ == "__main__":
    main()
