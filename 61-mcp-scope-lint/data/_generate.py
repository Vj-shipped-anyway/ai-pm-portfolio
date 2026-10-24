"""Generate the synthetic data for project 61: 30 MCP server manifests that ask for scopes, and the truth
about which of those scopes the tools really need.

Everything is seeded, so the files are byte-for-byte reproducible. The truth comes from the profile each
resource was built with, not from any lint rule. A profile decides which tools exist, which scopes they
declare, which scopes they truly need and whether anyone calls them. Three groups of profiles:
  caught by the rules    an unused grant, a wildcard used in part, a read-only tool that declares write,
                         a tool that declares a wildcard
  hard cases, missed     a tool with no hints that declares more than it needs, a hint that overstates what
                         the tool needs, a tool nobody calls that keeps a grant alive
  hard negatives         a wildcard whose every scope is used, a tool that truly needs two resources, a legitimate admin
                         scope, and a tool whose read-only hint is wrong while its scope is right (the proposal cuts a
                         scope that is needed)

Run (from data/):  python3 _generate.py
Writes:  manifests.json, entitlement_truth.csv, tool_scope_truth.csv, example_manifest.json, example_clean.json
"""
import csv
import json
import random

SEED = 61
rng = random.Random(SEED)

N_SERVERS = 30
POOL = ["accounts", "ledger", "payments", "cases", "documents", "messages", "kyc", "reports"]
NOUNS = {"accounts": ["balance", "transactions", "profile"], "ledger": ["entry", "journal", "adjustment"],
         "payments": ["payment", "payee", "quote"], "cases": ["case", "note", "attachment"],
         "documents": ["document", "statement", "template"], "messages": ["message", "draft", "thread"],
         "kyc": ["check", "review", "file"], "reports": ["report", "extract", "summary"], "keys": ["key", "secret", "credential"]}
VERBS = {"read": ["get", "list", "search"], "write": ["update", "create", "submit"], "delete": ["delete", "close", "void"],
         "admin": ["rotate", "revoke", "reissue"]}
DESC = {"read": "Return the {noun} for one {res} record.", "write": "Change the {noun} on one {res} record.",
        "delete": "Remove the {noun} from one {res} record.", "admin": "Change how the {noun} for the {res} integration is issued."}
SCHEMA = {"read": {"record_id": {"type": "string"}}, "write": {"record_id": {"type": "string"}, "changes": {"type": "object"}},
          "delete": {"record_id": {"type": "string"}, "reason": {"type": "string"}}, "admin": {"key_id": {"type": "string"}}}
HINTS = {"read": {"readOnlyHint": True}, "write": {"readOnlyHint": False, "destructiveHint": False},
         "delete": {"readOnlyHint": False, "destructiveHint": True}, "admin": {"readOnlyHint": False, "destructiveHint": True}}
NO_HINT_SHARE = 0.25

# (profile, how many resources get it). The remaining resources are clean.
QUOTA = [("unused_specific", 12), ("unused_wildcard", 5), ("wildcard_partly_used", 8), ("read_tool_write_scope", 9),
         ("read_tool_wildcard", 5), ("nondestructive_tool_delete", 4), ("wildcard_nohint", 4), ("overscoped_nohint", 6),
         ("overscoped_wrong_hint", 4), ("dead_tool", 4), ("wildcard_fully_used", 5), ("hint_wrong_scope_right", 3),
         ("legit_admin", 4)]
N_CROSS_READERS = 6


def sid(res, access):
    return f"{res}:*" if access == "any" else f"{res}:{access}"


def catalog_for(res):
    accesses = ["read", "admin"] if res == "keys" else ["read", "write", "delete"]
    return [{"id": sid(res, a), "resource": res, "access": a} for a in accesses + ["any"]]


class Server:
    def __init__(self, index):
        self.name = f"synthetic-mcp-{index:02d}"
        self.resources = []      # (resource, profile)
        self.tools = []
        self.grants = set()
        self.names = set()

    def add_tool(self, res, kind, declared, true, hints="auto", called=True, planted="clean", name=None, description=None):
        if name is None:
            for _ in range(100):
                name = f"{rng.choice(VERBS[kind])}_{rng.choice(NOUNS[res])}"
                if name not in self.names:
                    break
            else:
                raise RuntimeError("no free tool name")
            description = DESC[kind].format(noun=name.split("_", 1)[1], res=res)
        self.names.add(name)
        if hints == "auto":
            hints = None if rng.random() < NO_HINT_SHARE else HINTS[kind]
        tool = {"name": name, "description": description,
                "inputSchema": {"type": "object", "properties": SCHEMA[kind], "required": sorted(SCHEMA[kind])[:1]},
                "requires_scopes": list(declared)}
        if hints is not None:
            tool["annotations"] = dict(hints)
        self.tools.append({"manifest": tool, "true": list(true), "called": called, "planted": planted})
        self.grants.update(declared)


def build_resource(srv, res, profile):
    r, w, d, a, x = (sid(res, k) for k in ("read", "write", "delete", "admin", "any"))
    if profile == "clean":
        for _ in range(rng.choice([1, 2])):
            srv.add_tool(res, "read", [r], [r], planted=profile)
        if rng.random() < 0.6:
            srv.add_tool(res, "write", [w], [w], planted=profile)
    elif profile == "unused_specific":
        for _ in range(rng.choice([1, 2])):
            srv.add_tool(res, "read", [r], [r], planted=profile)
        srv.grants.add(rng.choice([w, d]))
    elif profile == "unused_wildcard":
        srv.grants.add(x)
    elif profile == "wildcard_partly_used":
        srv.add_tool(res, "read", [r], [r], planted=profile)
        if rng.random() < 0.5:
            srv.add_tool(res, "write", [w], [w], planted=profile)
        srv.grants.add(x)
    elif profile == "wildcard_fully_used":
        srv.add_tool(res, "read", [r], [r], planted=profile)
        srv.add_tool(res, "write", [w], [w], planted=profile)
        srv.add_tool(res, "delete", [d], [d], planted=profile)
        srv.grants.add(x)
    elif profile == "read_tool_write_scope":
        srv.add_tool(res, "read", [r, w], [r], HINTS["read"], planted=profile)
    elif profile == "read_tool_wildcard":
        srv.add_tool(res, "read", [x], [r], HINTS["read"], planted=profile)
    elif profile == "nondestructive_tool_delete":
        srv.add_tool(res, "read", [r], [r], planted=profile)
        srv.add_tool(res, "write", [w, d], [w], HINTS["write"], planted=profile)
    elif profile == "wildcard_nohint":
        srv.add_tool(res, "read", [x], [r], None, planted=profile)
    elif profile == "overscoped_nohint":
        srv.add_tool(res, "read", [r, w], [r], None, planted=profile)
    elif profile == "overscoped_wrong_hint":
        srv.add_tool(res, "read", [r, w], [r], HINTS["write"], planted=profile)
    elif profile == "dead_tool":
        srv.add_tool(res, "read", [r], [r], planted=profile)
        srv.add_tool(res, "write", [w], [w], called=False, planted=profile)
    elif profile == "hint_wrong_scope_right":
        srv.add_tool(res, "read", [r], [r], planted=profile)
        srv.add_tool(res, "write", [w], [w], HINTS["read"], planted=profile)
    elif profile == "legit_admin":
        srv.add_tool(res, "read", [r], [r], planted=profile)
        srv.add_tool(res, "admin", [a], [a], planted=profile)
    else:
        raise ValueError(profile)


def members(res, scope):
    """Specific scopes a scope reaches, from the generator's own catalog."""
    if scope.endswith(":*"):
        return [c["id"] for c in catalog_for(res) if c["access"] != "any"]
    return [scope]


def make_servers():
    sizes = [rng.choice([3, 4, 4, 5]) for _ in range(N_SERVERS)]
    servers = [Server(i + 1) for i in range(N_SERVERS)]
    admin_at = sorted(rng.sample(range(N_SERVERS), dict(QUOTA)["legit_admin"]))
    profiles = [p for p, n in QUOTA if p != "legit_admin" for _ in range(n)]
    slots = sum(sizes) - len(admin_at)
    if slots < len(profiles):
        raise RuntimeError("not enough resource slots for the quota")
    profiles += ["clean"] * (slots - len(profiles))
    rng.shuffle(profiles)
    for i, srv in enumerate(servers):
        mine = []
        if i in admin_at:
            mine.append(("keys", "legit_admin"))
        n = sizes[i] - len(mine)
        for res, p in zip(rng.sample(POOL, n), profiles[:n]):
            mine.append((res, p))
        profiles = profiles[n:]
        srv.resources = mine
        for res, p in mine:
            build_resource(srv, res, p)
    plain = [s for s in servers if sum(1 for _r, p in s.resources if p in ("clean", "unused_specific")) >= 2]
    for srv in rng.sample(plain, N_CROSS_READERS):
        a, b = [res for res, p in srv.resources if p in ("clean", "unused_specific")][:2]
        both = [sid(a, "read"), sid(b, "read")]
        srv.add_tool(a, "read", both, both, HINTS["read"], planted="multi_resource_reader",
                     name=f"lookup_{a}_and_{b}", description=f"Return data from {a} and {b} in one call.")
    return servers


def manifest_of(srv):
    catalog = [c for res, _p in srv.resources for c in catalog_for(res)]
    return {"server": {"name": srv.name, "version": "1.0.0"}, "scope_catalog": catalog, "granted_scopes": sorted(srv.grants),
            "tools": sorted((t["manifest"] for t in srv.tools), key=lambda t: t["name"])}


def truth_rows(srv):
    """Entitlement rows (each scope the grants reach) and declared-scope rows (each scope a tool asks for)."""
    res_of = {sid(res, k): res for res, _p in srv.resources for k in ("read", "write", "delete", "admin", "any")}
    profile_of = dict(srv.resources)
    needed = {s for t in srv.tools if t["called"] for s in t["true"]}
    reach = sorted({m for g in srv.grants for m in members(res_of[g], g)})
    ent = [[srv.name, s, "yes" if s in needed else "no", profile_of[res_of[s]]] for s in reach]
    decl = []
    for t in srv.tools:
        for s in t["manifest"]["requires_scopes"]:
            decl.append([srv.name, t["manifest"]["name"], s, "yes" if t["called"] and s in t["true"] else "no", t["planted"]])
    return ent, sorted(decl)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.write("\n")


def example_manifests():
    def cat(res, accesses):
        return [{"id": sid(res, a), "resource": res, "access": a} for a in accesses + ["any"]]

    def tool(name, desc, requires, hints=None):
        t = {"name": name, "description": desc, "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}, "required": ["record_id"]},
             "requires_scopes": requires}
        if hints is not None:
            t["annotations"] = hints
        return t

    ex = {"server": {"name": "demo-ledger-desk", "version": "1.0.0"},
          "scope_catalog": cat("accounts", ["read", "write", "delete"]) + cat("payments", ["read", "write", "delete"])
          + cat("ledger", ["read", "write", "delete"]) + cat("reports", ["read"]),
          "granted_scopes": ["accounts:read", "accounts:write", "ledger:*", "payments:*", "reports:read"],
          "tools": [tool("get_balance", "Return the balance of one account.", ["accounts:read"], HINTS["read"]),
                    tool("list_transactions", "List recent transactions on one account.", ["accounts:read", "accounts:write"], HINTS["read"]),
                    tool("initiate_payment", "Start one payment.", ["payments:write"], HINTS["write"]),
                    tool("get_payment_status", "Return where one payment is.", ["payments:read"]),
                    tool("post_ledger_entry", "Post one ledger entry.", ["ledger:*"])]}
    clean = {"server": {"name": "demo-case-desk", "version": "1.0.0"},
             "scope_catalog": cat("cases", ["read", "write", "delete"]) + cat("documents", ["read", "write", "delete"]),
             "granted_scopes": ["cases:read", "cases:write", "documents:read"],
             "tools": [tool("get_case", "Return one case.", ["cases:read"], HINTS["read"]),
                       tool("update_case", "Change one case.", ["cases:write"], HINTS["write"]),
                       tool("get_document", "Return one document.", ["documents:read"], HINTS["read"])]}
    return ex, clean


def main():
    servers = make_servers()
    ent, decl = [], []
    for srv in servers:
        e, d = truth_rows(srv)
        ent += e
        decl += d
    write_json("manifests.json", [manifest_of(s) for s in servers])
    for path, header, rows in (("entitlement_truth.csv", ["server", "scope", "needed", "planted"], sorted(ent)),
                               ("tool_scope_truth.csv", ["server", "tool", "scope", "needed", "planted"], decl)):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
    ex, clean = example_manifests()
    write_json("example_manifest.json", ex)
    write_json("example_clean.json", clean)
    print(f"wrote {len(servers)} manifests, {sum(len(s.tools) for s in servers)} tools, {len(ent)} reachable scopes, {len(decl)} declared tool scopes")


if __name__ == "__main__":
    main()
