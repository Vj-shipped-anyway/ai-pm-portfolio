"""Bad input: every case must raise InputError with a one-line message, never another exception."""
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import failover_scorecard as fs

SERVICE_HEAD = ",".join(fs.SERVICE_COLUMNS)
DRILL_HEAD = ",".join(fs.DRILL_COLUMNS)
GOOD_SERVICE = "S1,svc,payments,1,region-a,region-b,warm_standby,30,2,,no"
GOOD_DRILL = "D1,S1,2026-09-01,live,region_failover,region-b,2,20,pass,"


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, text, binary=False):
        p = os.path.join(self.dir.name, "f.csv")
        with open(p, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8", "newline": ""})) as fh:
            fh.write(text)
        return p

    def bad_services(self, body, head=SERVICE_HEAD):
        with self.assertRaises(fs.InputError) as cm:
            fs.load_services(self.write(head + "\n" + body + "\n"))
        self.assertNotIn("\n", str(cm.exception))
        return str(cm.exception)

    def bad_drills(self, body):
        with self.assertRaises(fs.InputError) as cm:
            fs.load_drills(self.write(DRILL_HEAD + "\n" + body + "\n"))
        self.assertNotIn("\n", str(cm.exception))
        return str(cm.exception)

    def test_good_files_load(self):
        self.assertEqual(len(fs.load_services(self.write(SERVICE_HEAD + "\n" + GOOD_SERVICE + "\n"))), 1)
        self.assertEqual(len(fs.load_drills(self.write(DRILL_HEAD + "\n" + GOOD_DRILL + "\n"))), 1)

    def test_empty_file(self):
        for loader in (fs.load_services, fs.load_drills):
            with self.assertRaises(fs.InputError):
                loader(self.write(""))

    def test_header_only_services_is_an_error_and_header_only_drills_is_not(self):
        with self.assertRaises(fs.InputError):
            fs.load_services(self.write(SERVICE_HEAD + "\n"))
        self.assertEqual(fs.load_drills(self.write(DRILL_HEAD + "\n")), [])

    def test_missing_file(self):
        with self.assertRaises(fs.InputError):
            fs.load_services(os.path.join(self.dir.name, "nope.csv"))

    def test_binary_file(self):
        with self.assertRaises(fs.InputError):
            fs.load_services(self.write(b"\xff\xfe\x00\x01\x02", binary=True))

    def test_missing_column(self):
        self.assertIn("missing column", self.bad_services(GOOD_SERVICE, head=SERVICE_HEAD.replace(",tier", "")))

    def test_wrong_type_tier(self):
        self.assertIn("tier", self.bad_services(GOOD_SERVICE.replace(",1,region-a", ",one,region-a")))

    def test_tier_out_of_range(self):
        self.assertIn("must be 1 to 3", self.bad_services(GOOD_SERVICE.replace(",1,region-a", ",4,region-a")))

    def test_negative_and_float_numbers(self):
        self.bad_services(GOOD_SERVICE.replace(",30,2,", ",-5,2,"))
        self.bad_services(GOOD_SERVICE.replace(",30,2,", ",30.5,2,"))

    def test_truncated_row(self):
        self.assertIn("truncated", self.bad_services("S1,svc,payments,1,region-a"))

    def test_extra_values(self):
        self.assertIn("more values", self.bad_services(GOOD_SERVICE + ",extra"))

    def test_unknown_mode_and_bad_accepted_risk(self):
        self.bad_services(GOOD_SERVICE.replace("warm_standby", "hot"))
        self.bad_services(GOOD_SERVICE[:-2] + "maybe")

    def test_duplicate_service_id(self):
        self.assertIn("twice", self.bad_services(GOOD_SERVICE + "\n" + GOOD_SERVICE))

    def test_dependency_on_unknown_service(self):
        self.assertIn("not in the file", self.bad_services(GOOD_SERVICE.replace(",2,,no", ",2,S9,no")))

    def test_dependency_on_itself(self):
        self.assertIn("itself", self.bad_services(GOOD_SERVICE.replace(",2,,no", ",2,S1,no")))

    def test_bad_dates(self):
        for bad in ("2026-13-45", "24/10/2026", "2026-9-1", "yesterday", ""):
            self.bad_drills(GOOD_DRILL.replace("2026-09-01", bad))

    def test_unknown_outcome_type_and_scenario(self):
        self.bad_drills(GOOD_DRILL.replace(",pass,", ",ok,"))
        self.bad_drills(GOOD_DRILL.replace(",live,", ",drill,"))
        self.bad_drills(GOOD_DRILL.replace("region_failover", "dr"))

    def test_passing_live_drill_needs_minutes(self):
        self.assertIn("minutes_to_recover", self.bad_drills(GOOD_DRILL.replace(",20,pass", ",,pass")))

    def test_tabletop_pass_may_leave_minutes_blank(self):
        row = GOOD_DRILL.replace(",live,", ",tabletop,").replace(",20,pass", ",,pass")
        self.assertEqual(fs.load_drills(self.write(DRILL_HEAD + "\n" + row + "\n"))[0]["minutes"], None)

    def test_duplicate_drill_id(self):
        self.assertIn("twice", self.bad_drills(GOOD_DRILL + "\n" + GOOD_DRILL))


if __name__ == "__main__":
    unittest.main()
