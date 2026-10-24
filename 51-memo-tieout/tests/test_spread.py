import os
import tempfile
import unittest
from decimal import Decimal

import _bootstrap  # noqa: F401
from memo_tieout import build_spread, read_spread


def row(line="revenue", period="FY2024", end="2024-12-31", value="100", unit="usd_thousands"):
    return {"period": period, "period_end": end, "line": line, "value": value, "unit": unit}


class BuildSpreadTests(unittest.TestCase):
    def test_units_are_converted_to_dollars(self):
        s = build_spread([row(value="47320"), row(line="cogs", value="47.32", unit="usd_millions"), row(line="opex", value="47320000", unit="usd")])
        self.assertEqual([s["values"][(n, "FY2024")] for n in ("revenue", "cogs", "opex")], [Decimal(47320000)] * 3)

    def test_periods_are_ordered_by_end_date_not_by_name(self):
        s = build_spread([row(period="zeta", end="2022-12-31"), row(period="alpha", end="2024-12-31"), row(period="mid", end="2023-12-31")])
        self.assertEqual(s["periods"], ["zeta", "mid", "alpha"])

    def test_bad_rows_raise_one_line_value_errors(self):
        cases = [row(line="Revenue"), row(line="net income"), row(period="FY 2024"), row(end="31/12/2024"), row(end=""),
                 row(unit="eur"), row(unit=""), row(value="1,234"), row(value="abc"), row(value="NaN"), row(value="Infinity"),
                 row(value="1e9"), row(value="9" * 16), row(value="")]
        for bad in cases:
            with self.assertRaises(ValueError, msg=bad) as cm:
                build_spread([bad])
            self.assertNotIn("\n", str(cm.exception))

    def test_duplicate_line_and_period_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "appears twice"):
            build_spread([row(), row()])

    def test_one_period_with_two_end_dates_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "two different period_end"):
            build_spread([row(), row(line="cogs", end="2024-06-30")])

    def test_two_periods_with_one_end_date_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "share one period_end"):
            build_spread([row(), row(period="FY2025")])

    def test_no_rows_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "no rows"):
            build_spread([])

    def test_hostile_line_name_is_not_echoed_raw(self):
        with self.assertRaises(ValueError) as cm:
            build_spread([row(line="a\r::error::x")])
        self.assertNotIn("\r", str(cm.exception))


class ReadSpreadTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, text, mode="w"):
        p = os.path.join(self.dir.name, "s.csv")
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8", "newline": ""})) as fh:
            fh.write(text)
        return p

    def test_reads_a_good_file_with_columns_in_any_order(self):
        s = read_spread(self.write("unit,value,line,period_end,period\nusd,5,cash,2024-12-31,FY2024\n"))
        self.assertEqual(s["values"][("cash", "FY2024")], Decimal(5))

    def test_failures_are_value_errors(self):
        header = "period,period_end,line,value,unit\n"
        for text in ["", "\n\n", header, "period,line\nFY2024,cash\n", header + "FY2024,2024-12-31,cash,5\n",
                     header + "FY2024,2024-12-31,cash,5,usd,extra\n", '{"revenue": 5}', header + "FY2024,2024-12-31,cash,5,usd\nFY20"]:
            with self.assertRaises(ValueError, msg=text):
                read_spread(self.write(text))

    def test_binary_and_missing_and_directory_inputs(self):
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            read_spread(self.write(b"\xff\xfe\x00bad", "wb"))
        with self.assertRaises(ValueError):
            read_spread(os.path.join(self.dir.name, "nope.csv"))
        with self.assertRaises(ValueError):
            read_spread(self.dir.name)


if __name__ == "__main__":
    unittest.main()
