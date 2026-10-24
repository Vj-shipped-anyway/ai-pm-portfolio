"""Generate the synthetic data for project 63: relationship-manager call notes, the actions they
really commit to, and the candidate actions a stub extractor proposes from them.

Everything is seeded, so the files are byte-for-byte reproducible. The planted truth comes from
this generator, not from the checker in src/: each note is built from sentence templates whose
role (commitment, conditional, negated, past, declined, hedged, background) is known when the
sentence is written, and the stub extractor is a seeded corruption process over that truth. The
stub copies a sentence into a citation, fills the slots from it, and then, at fixed rates, drops
an action, invents a quote, cites a sentence that does not carry the action, changes a date or an
amount, flips the owner, swaps slots between two clauses, or turns a conditional, negated, past,
declined or hedged sentence into an action. Some phrasings are hard on purpose: valid actions the
checker could wrongly hold (a reformatted quote, a spelled-out amount, a negation about something
else) and unsafe actions it cannot see (soft hedges, phrasal negations, a clause swap).

Run (from data/):  python3 _generate.py
Writes:  notes.csv, sentence_roles.csv, truth_actions.csv, candidates.csv, candidate_truth.csv,
         example_notes.csv, example_candidates.csv
"""
from __future__ import annotations

import csv
import random
from collections import Counter
from datetime import date, timedelta

rng = random.Random(63)
N_NOTES = 120

CLIENTS = [("Ms.", "Okafor", "f"), ("Mr.", "Alvarez", "m"), ("Mr.", "Brandt", "m"), ("Ms.", "Chen", "f"),
           ("Ms.", "Dubois", "f"), ("Mr.", "Eriksen", "m"), ("Mr.", "Farouk", "m"), ("Ms.", "Gallagher", "f"),
           ("Mr.", "Haddad", "m"), ("Ms.", "Ito", "f"), ("Ms.", "Jansen", "f"), ("Mr.", "Kowalski", "m"),
           ("Ms.", "Lindqvist", "f"), ("Mr.", "Moreau", "m"), ("Ms.", "Novak", "f"), ("Mr.", "Oyelaran", "m"),
           ("Mr.", "Petrov", "m"), ("Ms.", "Quinn", "f"), ("Mr.", "Rahman", "m"), ("Ms.", "Santos", "f"),
           ("Mr.", "Tanaka", "m"), ("Ms.", "Umarova", "f"), ("Ms.", "Varga", "f"), ("Mr.", "Walsh", "m"),
           ("Ms.", "Xu", "f"), ("Mr.", "Yilmaz", "m"), ("Ms.", "Zielinski", "f"), ("Mr.", "Abebe", "m"),
           ("Ms.", "Bianchi", "f"), ("Mr.", "Castillo", "m")]
DOCS = ["rate sheet", "fee schedule", "product summary", "account statement", "term sheet"]
CDOCS = ["KYC form", "income proof", "signed mandate", "address proof"]
TOPICS = ["overdraft", "term deposit", "card replacement", "wire limit", "mortgage rate"]
RATE_TOPICS = ["mortgage rate", "term deposit rate"]
REVIEWS = ["annual review", "portfolio review", "rate review"]
LIMITS = ["overdraft limit", "wire limit"]
COMPLAINTS = ["card replacement delay", "wire fee", "statement error", "branch queue time"]
CHANNELS = ["email", "phone", "post"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
FILLERS = ["also", "personally", "promptly", "definitely"]
ONES = {5: "five", 10: "ten", 15: "fifteen"}
TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety"}
TYPES = ["send_document", "await_document", "callback", "schedule_review", "limit_request", "log_complaint",
         "update_preference"]
COMMITMENT = {"send_document", "await_document", "callback", "schedule_review", "limit_request"}


def pick(pairs):
    """Weighted choice from [(value, weight), ...] using the seeded generator."""
    r = rng.random() * sum(w for _, w in pairs)
    for v, w in pairs:
        r -= w
        if r < 0:
            return v
    return pairs[-1][0]


def act(type_, owner, due, subject, amount):
    return {"type": type_, "owner": owner, "due": due, "subject": subject, "amount": amount}


def pick_due(call):
    d = call + timedelta(days=rng.randint(1, 12))
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def dtext(call, due, prep):
    """The date as an RM would write it: tomorrow, a weekday within a week, or day and month."""
    delta = (due - call).days
    r = rng.random()
    if delta == 1 and r < 0.4:
        return "tomorrow" if prep == "on" else f"{prep} tomorrow"
    if delta <= 7 and r < 0.75:
        return f"{prep} {WEEKDAYS[due.weekday()]}"
    return f"{prep} {due.day} {MONTHS[due.month - 1]}"


def words(k):
    if k in ONES:
        return ONES[k]
    if k == 100:
        return "one hundred"
    return TENS[k // 10] + ("-" + ONES[k % 10] if k % 10 else "")


def amount_text(k):
    """k is thousands of dollars. Returns (text, quirk)."""
    r = rng.random()
    if r < 0.45:
        return f"${k * 1000:,}", ""
    if r < 0.75:
        return f"${k}k", ""
    return f"{words(k)} thousand dollars", "spelled_amount"


# ---------------------------------------------------------------- sentences that carry an action
def b_send(c):
    due, doc = pick_due(c["call"]), rng.choice(DOCS)
    a = [act("send_document", "rm", due.isoformat(), doc, "")]
    r = rng.random()
    if r < 0.10:
        t = f"I will send {c['T']} the {doc} {dtext(c['call'], due, 'by')}; {c['s']} does not need anything else."
        return dict(text=t, role="commit", acts=a, quirk="negation_elsewhere")
    k = rng.randrange(3)
    if k == 0:
        t = f"I will send {c['T']} the {doc} {dtext(c['call'], due, 'by')}."
    elif k == 1:
        t = f"I'll email the {doc} to {c['T']} {dtext(c['call'], due, 'by')}."
    else:
        t = f"Agreed that I forward the {doc} {dtext(c['call'], due, 'by')}."
    return dict(text=t, role="commit", acts=a, quirk="")


def b_await(c):
    due, doc = pick_due(c["call"]), rng.choice(CDOCS)
    k = rng.randrange(3)
    if k == 0:
        t = f"{c['T']} will return the {doc} {dtext(c['call'], due, 'by')}."
    elif k == 1:
        t = f"{c['S']} will upload the {doc} {dtext(c['call'], due, 'by')}."
    else:
        t = f"{c['S']} is going to send the {doc} {dtext(c['call'], due, 'by')}."
    return dict(text=t, role="commit", acts=[act("await_document", "client", due.isoformat(), doc, "")], quirk="")


def b_call(c):
    due, topic = pick_due(c["call"]), rng.choice(TOPICS)
    k = rng.randrange(3)
    if k == 0:
        t = f"I will call {c['o']} {dtext(c['call'], due, 'on')} about the {topic}."
    elif k == 1:
        t = f"I'll phone {c['T']} {dtext(c['call'], due, 'on')} to talk through the {topic}."
    else:
        t = f"{c['S']} asked me to ring {c['o']} {dtext(c['call'], due, 'on')} about the {topic}."
    return dict(text=t, role="commit", acts=[act("callback", "rm", due.isoformat(), topic, "")], quirk="")


def b_review(c):
    due, rev = pick_due(c["call"]), rng.choice(REVIEWS)
    if rng.randrange(2) == 0:
        t = f"I will book the {rev} {dtext(c['call'], due, 'for')}."
    else:
        t = f"I'll schedule the {rev} with {c['T']} {dtext(c['call'], due, 'for')}."
    return dict(text=t, role="commit", acts=[act("schedule_review", "rm", due.isoformat(), rev, "")], quirk="")


def b_limit(c):
    due, lim, k = pick_due(c["call"]), rng.choice(LIMITS), rng.randrange(2, 21) * 5
    amt, quirk = amount_text(k)
    if rng.randrange(2) == 0:
        t = f"I will submit the request to raise the {lim} to {amt} {dtext(c['call'], due, 'by')}."
    else:
        t = f"{c['S']} wants the {lim} increased to {amt}; I will submit the request {dtext(c['call'], due, 'by')}."
    return dict(text=t, role="commit", acts=[act("limit_request", "rm", due.isoformat(), lim, str(k * 1000))], quirk=quirk)


def b_complaint(c):
    comp = rng.choice(COMPLAINTS)
    if rng.randrange(2) == 0:
        t = f"{c['S']} complained about the {comp}."
    else:
        t = f"{c['S']} was unhappy about the {comp} and wants it logged."
    return dict(text=t, role="commit", acts=[act("log_complaint", "rm", "", comp, "")], quirk="")


def b_pref(c):
    ch = rng.choice(CHANNELS)
    if rng.randrange(2) == 0:
        t = f"{c['S']} now prefers contact by {ch}."
    else:
        t = f"{c['S']} asked to be contacted by {ch} from now on."
    return dict(text=t, role="commit", acts=[act("update_preference", "rm", "", ch, "")], quirk="")


def b_compound(c):
    d1 = pick_due(c["call"])
    d2 = pick_due(c["call"])
    while d2 == d1:
        d2 = pick_due(c["call"])
    cdoc, doc = rng.choice(CDOCS), rng.choice(DOCS)
    t = (f"{c['T']} will return the {cdoc} {dtext(c['call'], d1, 'by')}, "
         f"and I will send the {doc} {dtext(c['call'], d2, 'by')}.")
    acts = [act("await_document", "client", d1.isoformat(), cdoc, ""), act("send_document", "rm", d2.isoformat(), doc, "")]
    return dict(text=t, role="commit_compound", acts=acts, quirk="")


BUILDERS = {"send_document": b_send, "await_document": b_await, "callback": b_call, "schedule_review": b_review,
            "limit_request": b_limit, "log_complaint": b_complaint, "update_preference": b_pref}


# ---------------------------------------------------------------- sentences that must not become an action
def d_conditional(c):
    k = rng.randrange(3)
    if k == 0:
        topic, bp = rng.choice(RATE_TOPICS), rng.choice([10, 15, 25, 50])
        t = f"If the {topic} moves by more than {bp} basis points, {c['s']} wants me to call {c['o']}."
        return dict(text=t, role="conditional", implied=act("callback", "rm", "", topic, ""))
    if k == 1:
        doc = rng.choice(DOCS)
        t = f"I will send {c['T']} the {doc} once {c['s']} confirms the amount."
        return dict(text=t, role="conditional", implied=act("send_document", "rm", "", doc, ""))
    doc = rng.choice(CDOCS)
    t = f"{c['S']} will return the {doc} if the branch confirms the fee."
    return dict(text=t, role="conditional", implied=act("await_document", "client", "", doc, ""))


def d_negated(c):
    k = rng.randrange(3)
    if k == 0:
        return dict(text=f"{c['S']} does not want a follow-up call this quarter.", role="negated",
                    implied=act("callback", "rm", "", "", ""))
    if k == 1:
        doc = rng.choice(DOCS)
        return dict(text=f"{c['S']} said there is no need to send the {doc}.", role="negated",
                    implied=act("send_document", "rm", "", doc, ""))
    return dict(text=f"{c['S']} asked me to hold off calling {c['o']} until January.", role="negated_phrasal",
                implied=act("callback", "rm", "", "", ""))


def d_past(c):
    k = rng.randrange(3)
    if k == 0:
        doc = rng.choice(DOCS)
        return dict(text=f"I already sent {c['T']} the {doc} last week.", role="past",
                    implied=act("send_document", "rm", "", doc, ""))
    if k == 1:
        doc = rng.choice(CDOCS)
        return dict(text=f"{c['S']} returned the {doc} last week.", role="past",
                    implied=act("await_document", "client", "", doc, ""))
    topic = rng.choice(TOPICS)
    return dict(text=f"I called {c['o']} yesterday about the {topic}.", role="past",
                implied=act("callback", "rm", "", topic, ""))


def d_declined(c):
    lim, k = rng.choice(LIMITS), rng.randrange(2, 21) * 5
    amt, _ = amount_text(k)
    if rng.randrange(2) == 0:
        return dict(text=f"{c['S']} declined the offer to raise the {lim} to {amt}.", role="declined",
                    implied=act("limit_request", "rm", "", lim, str(k * 1000)))
    return dict(text=f"{c['S']} turned down the increase of the {lim} to {amt}.", role="declined_phrasal",
                implied=act("limit_request", "rm", "", lim, str(k * 1000)))


def d_hedged(c):
    doc, topic = rng.choice(DOCS), rng.choice(TOPICS)
    r = rng.random()
    if r < 0.34:
        return dict(text=f"I might send the {doc} next month if there is time.", role="hedged",
                    implied=act("send_document", "rm", "", doc, ""))
    due = pick_due(c["call"])
    if r < 0.67:
        t = f"I will try to call {c['o']} {dtext(c['call'], due, 'on')} about the {topic}."
        return dict(text=t, role="hedged_soft", implied=act("callback", "rm", due.isoformat(), topic, ""))
    t = f"I'll try to send the {doc} {dtext(c['call'], due, 'by')}."
    return dict(text=t, role="hedged_soft", implied=act("send_document", "rm", due.isoformat(), doc, ""))


DISTRACTORS = [d_conditional, d_negated, d_past, d_declined, d_hedged]


def info_sentence(c):
    return rng.choice([
        f"{c['S']} holds a term deposit and a current account with us.",
        "Rates were discussed at length.",
        f"{c['S']} travels in November and reads email in the evening.",
        f"{c['S']} is considering a larger deposit in the new year.",
        f"{c['S']} runs a small catering business.",
        f"{c['S']} was pleased with the last statement.",
    ])


# ---------------------------------------------------------------- the stub extractor
def candidate(a, sid, quote):
    return {"type": a["type"], "owner": a["owner"], "due": a["due"], "subject": a["subject"], "amount": a["amount"],
            "sid": sid, "quote": quote}


def reformat(q):
    """A quote the way a model often returns it: curly apostrophe, doubled space, cut short with an ellipsis, lower case."""
    k = rng.randrange(4)
    if k == 0 and "'" in q:
        return q.replace("'", "’")
    if k <= 1:
        return q.replace(" ", "  ", 1)
    if k == 2:
        w = q.split()
        return " ".join(w[:max(3, int(len(w) * 0.6))]) + "…"
    return q[0].lower() + q[1:]


def corrupt_single(a, sent, sid, n_sent, sentences):
    """One candidate for one planted action. Returns (candidate, defect, valid)."""
    kind = pick([("valid", 0.60), ("reformatted", 0.12), ("fabricated", 0.07), ("wrong_sentence", 0.05),
                 ("slot_changed", 0.10), ("owner_flipped", 0.06)])
    cand = candidate(a, sid, sent["text"])
    if kind == "reformatted":
        cand["quote"] = reformat(sent["text"])
        return cand, ("valid_" + sent["quirk"] if sent["quirk"] else "valid_reformatted_quote"), True
    if kind == "fabricated":
        if rng.random() < 0.6:
            w = sent["text"].split()
            w.insert(rng.randint(1, len(w) - 1), rng.choice(FILLERS))
            cand["quote"] = " ".join(w)
        else:
            cand["sid"] = n_sent + rng.randint(1, 3)
        return cand, "fabricated_cite", False
    if kind == "wrong_sentence":
        others = [i for i in range(1, n_sent + 1) if i != sid]
        o = rng.choice(others)
        cand["sid"], cand["quote"] = o, sentences[o - 1]["text"]
        return cand, "wrong_sentence", False
    if kind == "slot_changed" and a["due"]:
        cand["due"] = (date.fromisoformat(a["due"]) + timedelta(days=rng.choice([2, 3, 4, 5]))).isoformat()
        return cand, "slot_changed", False
    if kind == "slot_changed" and a["amount"]:
        cand["amount"] = str(int(a["amount"]) + rng.choice([5000, 10000]))
        return cand, "slot_changed", False
    if kind == "owner_flipped" and a["type"] in COMMITMENT:
        cand["owner"] = "client" if a["owner"] == "rm" else "rm"
        return cand, "owner_flipped", False
    return cand, ("valid_" + sent["quirk"] if sent["quirk"] else "valid"), True


def corrupt_compound(acts, sent, sid):
    """Candidates for a sentence that holds two commitments. A clause swap keeps the owner and the type but takes the
    date or the document from the other clause."""
    out = []
    for i, a in enumerate(acts):
        other = acts[1 - i]
        cand = candidate(a, sid, sent["text"])
        if rng.random() < 0.3:
            if rng.random() < 0.6:
                cand["due"] = other["due"]
            else:
                cand["subject"] = other["subject"]
            out.append((cand, "clause_swap", False))
        else:
            out.append((cand, "valid", True))
    return out


def build_note(n):
    title, surname, g = CLIENTS[(n * 7) % len(CLIENTS)]
    he = g == "m"
    c = {"T": f"{title} {surname}", "S": "He" if he else "She", "s": "he" if he else "she", "o": "him" if he else "her"}
    call = date(2026, 10, 1) + timedelta(days=rng.randint(0, 25))
    while call.weekday() >= 5:
        call += timedelta(days=1)
    c["call"] = call
    body = []
    pool = list(TYPES)
    if rng.random() < 0.2:
        body.append(b_compound(c))
        pool.remove("send_document")
        pool.remove("await_document")
        extra = rng.randrange(2)
    else:
        extra = rng.choice([1, 2, 2, 3])
    for _ in range(extra):
        t = rng.choice(pool)
        pool.remove(t)
        body.append(BUILDERS[t](c))
    for _ in range(rng.choice([1, 2, 2, 3])):
        body.append(rng.choice(DISTRACTORS)(c))
    for _ in range(rng.randrange(3)):
        body.append({"text": info_sentence(c), "role": "info"})
    rng.shuffle(body)
    seen, uniq = set(), []
    for s in body:
        if s["text"] not in seen:
            seen.add(s["text"])
            uniq.append(s)
    opener = {"text": f"Spoke with {c['T']} for {rng.randint(8, 30)} minutes about the {rng.choice(TOPICS)}.", "role": "info"}
    return (n * 7) % len(CLIENTS) + 1, call, [opener] + uniq


def write_csv(name, header, rows):
    with open(name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


EXAMPLE_NOTE = ["Spoke with Ms. Okafor for 12 minutes about her term deposit.",
                "I will send Ms. Okafor the rate sheet by Friday.",
                "She will return the KYC form by 21 October.",
                "If the term deposit rate moves by more than 25 basis points, she wants me to call her.",
                "She complained about the card replacement delay.",
                "I already sent the fee schedule last week."]
EXAMPLE_CANDS = [
    ("E01", "send_document", "rm", "2026-10-16", "rate sheet", "", 2, EXAMPLE_NOTE[1]),
    ("E02", "await_document", "client", "2026-10-21", "KYC form", "", 3, EXAMPLE_NOTE[2]),
    ("E03", "callback", "rm", "", "term deposit", "", 4, EXAMPLE_NOTE[3]),
    ("E04", "log_complaint", "rm", "", "card replacement delay", "", 5, EXAMPLE_NOTE[4]),
    ("E05", "send_document", "rm", "", "fee schedule", "", 6, EXAMPLE_NOTE[5]),
    ("E06", "send_document", "rm", "2026-10-17", "rate sheet", "", 2, EXAMPLE_NOTE[1]),
    ("E07", "schedule_review", "rm", "2026-10-20", "annual review", "", 7, "I will book the annual review for 20 October."),
]


def main():
    notes_rows, role_rows, truth_rows, cand_rows, ctruth_rows = [], [], [], [], []
    action_n = cand_n = 0
    for n in range(1, N_NOTES + 1):
        nid = f"N-{n:03d}"
        client_no, call, sentences = build_note(n)
        n_sent = len(sentences)
        for i, s in enumerate(sentences, 1):
            notes_rows.append([nid, f"CL-{client_no:03d}", call.isoformat(), i, s["text"]])
            role_rows.append([nid, i, s["role"]])
        for i, s in enumerate(sentences, 1):
            produced = []  # (candidate, defect, valid, truth_id)
            if s.get("acts"):
                ids = []
                for a in s["acts"]:
                    action_n += 1
                    ids.append(f"A-{action_n:04d}")
                    truth_rows.append([ids[-1], nid, a["type"], a["owner"], a["due"], a["subject"], a["amount"], i])
                if s["role"] == "commit_compound":
                    for (cand, defect, valid), tid in zip(corrupt_compound(s["acts"], s, i), ids):
                        produced.append((cand, defect, valid, tid))
                else:
                    for a, tid in zip(s["acts"], ids):
                        if rng.random() < 0.06:
                            continue  # the extractor misses this action altogether
                        cand, defect, valid = corrupt_single(a, s, i, n_sent, sentences)
                        produced.append((cand, defect, valid, tid))
            elif s.get("implied"):
                if rng.random() < 0.7:
                    produced.append((candidate(s["implied"], i, s["text"]), s["role"], False, ""))
            elif rng.random() < 0.10:
                t = rng.choice(TYPES)
                subj = {"send_document": DOCS, "await_document": CDOCS, "callback": TOPICS, "schedule_review": REVIEWS,
                        "limit_request": LIMITS, "log_complaint": COMPLAINTS, "update_preference": CHANNELS}[t]
                owner = "client" if t == "await_document" else "rm"
                produced.append((candidate(act(t, owner, "", rng.choice(subj), ""), i, s["text"]), "wrong_sentence", False, ""))
            for cand, defect, valid, tid in produced:
                cand_n += 1
                cid = f"C-{cand_n:03d}"
                cand_rows.append([cid, nid, cand["type"], cand["owner"], cand["due"], cand["subject"], cand["amount"], cand["sid"], cand["quote"]])
                ctruth_rows.append([cid, defect, 1 if valid else 0, tid])
    write_csv("notes.csv", ["note_id", "client_id", "call_date", "sent_id", "text"], notes_rows)
    write_csv("sentence_roles.csv", ["note_id", "sent_id", "role"], role_rows)
    write_csv("truth_actions.csv", ["action_id", "note_id", "action_type", "owner", "due", "subject", "amount", "sent_id"], truth_rows)
    cand_header = ["cand_id", "note_id", "action_type", "owner", "due", "subject", "amount", "cite_sent_id", "cite_quote"]
    write_csv("candidates.csv", cand_header, cand_rows)
    write_csv("candidate_truth.csv", ["cand_id", "defect", "valid", "truth_action_id"], ctruth_rows)
    write_csv("example_notes.csv", ["note_id", "client_id", "call_date", "sent_id", "text"],
              [["EX-1", "CL-000", "2026-10-14", i, t] for i, t in enumerate(EXAMPLE_NOTE, 1)])
    write_csv("example_candidates.csv", cand_header,
              [[cid, "EX-1", ty, ow, due, sub, amt, sid, q] for cid, ty, ow, due, sub, amt, sid, q in EXAMPLE_CANDS])
    kinds = Counter(r[1] for r in ctruth_rows)
    print(f"wrote {N_NOTES} notes, {len(notes_rows)} sentences, {len(truth_rows)} planted actions, {len(cand_rows)} candidates")
    print("candidate kinds: " + ", ".join(f"{k} {kinds[k]}" for k in sorted(kinds)))


if __name__ == "__main__":
    main()
