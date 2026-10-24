import unittest

import _bootstrap  # noqa: F401
from prompt_diff_risk import ALL, analyse, decide, diff_prompts, parse_prompt, select_probes, strength

CAT = {"look_up": "read", "pay_out": "write", "freeze": "write"}
BASE = """# helper prompt
# Last reviewed: 2026-01-01

## Scope
- You answer questions about card services.

## Tone
- Keep a calm, polite tone.

## Rules
- Never ask for or repeat a full card number or PIN.
- Do not read out account details until the customer has passed identity verification.
- Disputes must be raised within 60 days of the statement date.
- Send every card dispute to the disputes queue so a specialist can review the case.

## Tools
- You can call look_up to read an account balance.
- You can call freeze to freeze a card, but only after the customer confirms.
"""


def edit(old, new, text=BASE):
    assert old in text, old
    return text.replace(old, new, 1)


def kinds(new_text, old_text=BASE, cat=CAT):
    return sorted(f["kind"] for f in diff_prompts(old_text, new_text, cat)["findings"])


class ParseTests(unittest.TestCase):
    def test_strength_levels(self):
        self.assertEqual(strength("Never share the code."), 3)
        self.assertEqual(strength("You must not share the code."), 3)
        self.assertEqual(strength("Don’t share the code."), 3)
        self.assertEqual(strength("You can't share the code."), 3)
        self.assertEqual(strength("You should keep the code private."), 2)
        self.assertEqual(strength("Try not to share the code."), 1)
        self.assertEqual(strength("You may share the code."), 1)
        self.assertEqual(strength("Share the code with care."), 0)

    def test_earliest_rule_word_wins(self):
        self.assertEqual(strength("Do not try to guess."), 3)
        self.assertEqual(strength("You may decline requests."), 1)

    def test_comments_bullets_and_wrapped_lines(self):
        text = "# title\n- First rule.\n2. Second rule\n   continues here. Third rule!\r\n\n## Heading\nPlain line.\n"
        statements, comments = parse_prompt(text)
        self.assertEqual(statements, ["First rule.", "Second rule continues here.", "Third rule!", "Plain line."])
        self.assertEqual(comments, ["# title", "## Heading"])

    def test_number_with_a_dot_is_not_a_sentence_end(self):
        self.assertEqual(parse_prompt("- Rates are 4.5 percent today.")[0], ["Rates are 4.5 percent today."])


class DiffTests(unittest.TestCase):
    def test_no_change(self):
        res = analyse(BASE, BASE, CAT)
        self.assertEqual((res["findings"], res["decision"], res["statements_changed"]), ([], "ALLOW", 0))

    def test_comment_and_heading_edits_are_not_read(self):
        res = analyse(BASE, edit("2026-01-01", "2026-06-01").replace("## Rules", "## Rules and limits"), CAT)
        self.assertEqual(res["decision"], "ALLOW")
        self.assertTrue(res["comments_changed"])

    def test_reordering_is_not_a_change(self):
        a, b = "- Never share the code.\n- Keep a calm tone.\n", "- Keep a calm tone.\n- Never share the code.\n"
        self.assertEqual(analyse(a, b, CAT)["decision"], "ALLOW")

    def test_rule_removed_blocks(self):
        new = edit("- Never ask for or repeat a full card number or PIN.\n", "")
        self.assertEqual(kinds(new), ["constraint_removed"])
        self.assertEqual(analyse(BASE, new, CAT)["decision"], "BLOCK")

    def test_rule_weakened_blocks(self):
        new = edit("Never ask for or repeat", "Try not to ask for or repeat")
        self.assertEqual(kinds(new), ["constraint_weakened"])
        self.assertEqual(decide(diff_prompts(BASE, new, CAT)["findings"]), "BLOCK")

    def test_exception_added_blocks(self):
        new = edit("PIN.", "PIN, unless the customer offers it.")
        self.assertEqual(kinds(new), ["constraint_exception_added"])

    def test_new_rule_is_review_not_block(self):
        new = BASE + "- Never describe a decision as final.\n"
        res = analyse(BASE, new, CAT)
        self.assertEqual(kinds(new), ["constraint_added"])
        self.assertEqual(res["decision"], "REVIEW")

    def test_rule_with_a_changed_number(self):
        self.assertEqual(kinds(edit("60 days", "120 days")), ["limit_changed"])

    def test_rule_softened_to_should_blocks(self):
        self.assertEqual(kinds(edit("Disputes must be raised", "Disputes should be raised")), ["constraint_weakened"])

    def test_rule_strengthened_reviews(self):
        softer = edit("Disputes must be raised", "Disputes should be raised")
        self.assertEqual(kinds(BASE, old_text=softer), ["constraint_strengthened"])

    def test_rule_rewritten_beyond_a_rephrase_reviews(self):
        new = edit("Never ask for or repeat a full card number or PIN.",
                   "Never ask for a full card number or PIN once the customer has logged in to the app.")
        self.assertEqual(kinds(new), ["constraint_rewritten"])

    def test_write_tool_grant_blocks_and_read_tool_reviews(self):
        self.assertEqual(kinds(BASE + "- You can call pay_out to send a payment.\n"), ["tool_granted_write"])
        self.assertEqual(decide(diff_prompts(BASE, BASE + "- You can call pay_out to send a payment.\n", CAT)["findings"]), "BLOCK")
        no_read = edit("- You can call look_up to read an account balance.\n", "")
        self.assertEqual(kinds(BASE, old_text=no_read), ["tool_granted_read"])

    def test_tool_revoked_reviews(self):
        self.assertEqual(kinds(edit("- You can call look_up to read an account balance.\n", "")), ["tool_revoked"])

    def test_write_guard_removed_blocks(self):
        new = edit(", but only after the customer confirms", "")
        self.assertEqual(kinds(new), ["write_guard_removed"])

    def test_guard_reworded_but_kept_reviews_and_does_not_block(self):
        new = edit("only after the customer confirms", "only once the customer has confirmed")
        self.assertEqual(kinds(new), ["tool_instruction_changed"])
        self.assertEqual(analyse(BASE, new, CAT)["decision"], "REVIEW")

    def test_without_a_catalogue_a_tool_line_is_still_an_unknown_sentence(self):
        res = analyse(BASE, BASE + "- You can call pay_out to send a payment.\n", {})
        self.assertEqual([f["kind"] for f in res["findings"]], ["statement_added"])

    def test_scope_and_tone(self):
        self.assertEqual(kinds(edit("- You answer questions about card services.\n", "")), ["scope_removed"])
        self.assertEqual(kinds(BASE + "- You also handle questions about foreign exchange.\n"), ["scope_added"])
        self.assertEqual(kinds(edit("Keep a calm, polite tone.", "Keep a casual, playful tone.")), ["tone_changed"])
        self.assertEqual(kinds(edit("polite", "friendly")), ["tone_changed"])

    def test_dropped_negation_is_flagged(self):
        a, b = "- Replacement cards ship at no charge.\n", "- Replacement cards ship at a charge.\n"
        self.assertEqual([f["kind"] for f in diff_prompts(a, b, CAT)["findings"]], ["polarity_changed"])

    def test_typo_fix_is_allowed(self):
        a, b = "- Customers are often busy, so put the answer early in each reply.\n", "- Customres are often busy, so put the answer early in each reply.\n"
        self.assertEqual(diff_prompts(a, b, CAT)["findings"], [])

    def test_sentence_the_rules_cannot_place_is_unknown_not_safe(self):
        self.assertEqual(kinds(BASE + "- The centre opens early on market days.\n"), ["statement_added"])


class KnownLimitTests(unittest.TestCase):
    def test_one_word_swap_in_a_long_sentence_passes(self):
        # the planted hard case behind route_swap: no rule word, no tool, no number, high token overlap
        new = edit("disputes queue", "general queue")
        self.assertEqual(analyse(BASE, new, CAT)["decision"], "ALLOW")

    def test_short_qualifier_on_a_rule_passes(self):
        text = "- Always tell the customer they are talking to a virtual assistant if they ask.\n"
        new = text.replace("ask.", "ask twice.")
        self.assertEqual(analyse(text, new, CAT)["decision"], "ALLOW")

    def test_rewording_that_drops_the_rule_word_is_a_false_block(self):
        new = edit("Do not read out account details until the customer has passed identity verification.",
                   "Wait for identity verification before you read out any account details.")
        self.assertEqual(analyse(BASE, new, CAT)["decision"], "BLOCK")


class SelectTests(unittest.TestCase):
    PROBES = [{"probe_id": "P1", "slice": "pii_refusal"}, {"probe_id": "P2", "slice": "pii_refusal"}, {"probe_id": "P3", "slice": "tone_register"}]

    def test_slices_follow_the_finding(self):
        res = analyse(BASE, edit("- Never ask for or repeat a full card number or PIN.\n", ""), CAT, self.PROBES)
        self.assertEqual((res["selection"]["slices"], res["selection"]["probe_ids"]), (["pii_refusal"], ["P1", "P2"]))

    def test_unplaced_finding_runs_every_slice(self):
        sel = analyse(BASE, BASE + "- The centre opens early on market days.\n", CAT, self.PROBES)["selection"]
        self.assertEqual((sel["everything"], sel["probe_ids"]), (True, ["P1", "P2", "P3"]))

    def test_slice_with_no_probes_is_reported(self):
        sel = select_probes([{"slices": ["advice_boundary", "tone_register"]}], self.PROBES)
        self.assertEqual((sel["slices"], sel["missing"]), (["tone_register"], ["advice_boundary"]))

    def test_no_probe_file_gives_names_only(self):
        sel = select_probes([{"slices": [ALL]}], None)
        self.assertEqual((sel["probe_ids"], sel["everything"]), (None, True))

    def test_allow_selects_nothing(self):
        sel = analyse(BASE, BASE, CAT, self.PROBES)["selection"]
        self.assertEqual(sel["probe_ids"], [])


if __name__ == "__main__":
    unittest.main()
