import unittest
from types import SimpleNamespace

import _bootstrap  # noqa: F401
import support
from agentkit import shadow
from agentkit.brief import load_brief
from agentkit.data_io import load_world
from agentkit.kit import build_kit

IDS = [g["id"] for g in support.golden()]


def R(proposed, field=None, new=None, route="to_person"):
    corr = {"field": field, "new": new} if field else None
    return SimpleNamespace(proposed_outcome=proposed, correction=corr, redelivery=False, route=route, gate=None,
                           state="", reason_kind="", case_id="C")


def H(outcome, field="", value=""):
    return {"human_outcome": outcome, "corrected_field": field, "corrected_value": value}


class TestJudgePair(unittest.TestCase):
    def test_agree_on_resubmit_needs_the_same_correction(self):
        self.assertEqual(shadow.judge_pair(R("RESUBMIT", "beneficiary_account", "1"), H("RESUBMIT", "beneficiary_account", "1")), "agree")

    def test_same_outcome_different_value_is_a_disagreement(self):
        self.assertEqual(shadow.judge_pair(R("RESUBMIT", "beneficiary_account", "1"), H("RESUBMIT", "beneficiary_account", "2")), "disagree_correction")

    def test_same_outcome_different_field_is_a_disagreement(self):
        self.assertEqual(shadow.judge_pair(R("RESUBMIT", "beneficiary_name", "x"), H("RESUBMIT", "beneficiary_account", "x")), "disagree_correction")

    def test_different_outcome(self):
        self.assertEqual(shadow.judge_pair(R("RETURN_TO_ORIGINATOR"), H("RESUBMIT", "a", "b")), "disagree_outcome")

    def test_return_agrees_without_a_correction(self):
        self.assertEqual(shadow.judge_pair(R("RETURN_TO_ORIGINATOR"), H("RETURN_TO_ORIGINATOR")), "agree")

    def test_deferred_and_queued_are_not_scored(self):
        self.assertEqual(shadow.judge_pair(R("DEFER_TO_PERSON"), H("RESUBMIT", "a", "b")), "deferred")
        self.assertEqual(shadow.judge_pair(R("HUMAN_QUEUE"), H("RETURN_TO_ORIGINATOR")), "queued")


class TestScore(unittest.TestCase):
    def setUp(self):
        self.k, self.w = support.kit()
        self.res = self.k.orchestrator.run_all(IDS)
        self.out = {}
        for r in self.res:
            if r.proposed_outcome == "RESUBMIT":
                self.out[r.case_id] = H("RESUBMIT", r.correction["field"], r.correction["new"])
            elif r.proposed_outcome in ("DEFER_TO_PERSON", "HUMAN_QUEUE"):
                self.out[r.case_id] = H("RESUBMIT", "beneficiary_name", "x")
            else:
                self.out[r.case_id] = H(r.proposed_outcome)

    def test_all_agree_when_the_human_did_the_same(self):
        sc = shadow.score(self.res, self.out)
        self.assertEqual(sc["agreement_rate"], 1.0)
        self.assertEqual((sc["deferred"], sc["queued"]), (1, 4))
        self.assertEqual(sc["scored"] + sc["deferred"] + sc["queued"], sc["cases"])

    def test_one_flipped_outcome_shows_up_by_class_and_in_the_confusion_matrix(self):
        self.out["G05"] = H("RESUBMIT", "beneficiary_name", "x")
        sc = shadow.score(self.res, self.out)
        self.assertEqual(sc["disagree"], 1)
        self.assertEqual(sc["confusion"]["RETURN_TO_ORIGINATOR"]["RESUBMIT"], 1)
        self.assertLess(sc["by_human_class"]["RESUBMIT"]["agreement_rate"], 1.0)
        self.assertEqual(sc["disagreements"][0]["case_id"], "G05")

    def test_auto_wrong(self):
        self.assertEqual(shadow.auto_wrong(self.res, self.out)["wrong"], 0)
        self.out["G06"] = H("RESUBMIT", "beneficiary_account", support.RIGHT)
        aw = shadow.auto_wrong(self.res, self.out)
        self.assertEqual((aw["wrong"], aw["cases"]), (1, ["G06"]))

    def test_redeliveries_are_not_scored(self):
        k, _ = support.kit(fault_rows=[{"fault_id": "F", "case_id": "G01", "step": "S01", "tool": "", "action": "",
                                        "attempts": "1", "fault_type": "duplicate_delivery", "payload": ""}])
        res = k.orchestrator.run_all(["G01"])
        sc = shadow.score(res, {"G01": H("RESUBMIT", "beneficiary_account", support.RIGHT)})
        self.assertEqual(sc["cases"], 1)


class TestReplay(unittest.TestCase):
    def test_replay_changes_nothing_in_the_systems(self):
        k, w = support.kit()
        before = dict(k.env.payments["P-1"])
        shadow.replay(k, IDS)
        self.assertEqual((k.env.ledger, k.env.cases, k.env.worksheet, k.env.cancelled), ([], {}, {}, []))
        self.assertEqual(k.env.payments["P-1"], before)
        self.assertTrue(all(c[2] == "read" for c in k.env.call_log))

    def test_two_replays_give_the_same_trace(self):
        a, _ = support.kit()
        b, _ = support.kit()
        shadow.replay(a, IDS)
        shadow.replay(b, IDS)
        self.assertEqual(a.audit.events()[-1]["hash"], b.audit.events()[-1]["hash"])
        self.assertEqual(len(a.audit), len(b.audit))

    def test_replay_needs_ids_or_a_world(self):
        k, _ = support.kit()
        with self.assertRaises(ValueError):
            shadow.replay(k)


class TestOnTheShippedData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = load_world()
        cls.brief = load_brief(support.BRIEF_PATH)
        cls.k = build_kit(cls.w, cls.brief)
        cls.res = shadow.replay(cls.k, world=cls.w)
        cls.sc = shadow.score(cls.res, cls.w["outcomes"], cls.w["truth"])

    def test_every_case_is_accounted_for(self):
        self.assertEqual(self.sc["cases"], 600)
        self.assertEqual(sum(self.sc["routes"].values()), 600)
        self.assertEqual(self.sc["scored"] + self.sc["deferred"] + self.sc["queued"], 600)

    def test_every_malformed_record_goes_to_the_human_queue_with_a_reason(self):
        mal = [c for c, t in self.w["truth"].items() if t["scenario"] == "malformed"]
        got = {r.case_id: r for r in self.res}
        self.assertEqual(len(mal), 12)
        self.assertTrue(all(got[c].route == "human_queue" and got[c].reason_kind == "record_invalid" for c in mal))

    def test_every_duplicate_delivery_is_caught(self):
        dup = [c for c, t in self.w["truth"].items() if t["scenario"] == "duplicate"]
        got = {r.case_id: r for r in self.res}
        self.assertEqual(len(dup), 14)
        self.assertTrue(all(got[c].proposed_outcome == "DUPLICATE_CLOSED" for c in dup))

    def test_every_exact_watch_list_name_is_escalated(self):
        ex = [c for c, t in self.w["truth"].items() if t["scenario"] == "watch_exact"]
        got = {r.case_id: r for r in self.res}
        self.assertEqual(len(ex), 10)
        self.assertTrue(all(got[c].proposed_outcome == "ESCALATE_COMPLIANCE" for c in ex))

    def test_shadow_mode_wrote_nothing(self):
        self.assertEqual((self.k.env.ledger, self.k.env.cases, self.k.env.worksheet), ([], {}, {}))

    def test_nothing_ended_in_an_unexpected_error(self):
        self.assertNotIn("unexpected_error", self.sc["queue_reasons"])
        self.assertNotIn("kit_error", self.sc["queue_reasons"])


if __name__ == "__main__":
    unittest.main()
