import unittest

import _bootstrap  # noqa: F401
from claims_check import extract_claims

G, Y, R = "\U0001F7E2", "\U0001F7E1", "\U0001F534"


def texts(readme):
    return [(c["line"], c["text"]) for c in extract_claims(readme)]


class ExtractTests(unittest.TestCase):
    def test_only_numbers_after_a_green_circle(self):
        self.assertEqual(texts(f"- 12 before. {G} 40 here {Y} 55 modeled {R} 66 hypothetical"), [(1, "40")])

    def test_green_again_after_another_circle_counts(self):
        self.assertEqual(texts(f"- {G} 11 {Y} 22 {G} 33"), [(1, "11"), (1, "33")])

    def test_ratio_is_one_claim_and_other_numbers_stay_separate(self):
        claims = extract_claims(f"- {G} 25 of 40 blocked, 62.5% of them")
        self.assertEqual([(c["kind"], c["text"]) for c in claims], [("ratio", "25 of 40"), ("number", "62.5")])
        self.assertEqual(claims[0]["key"], ("25", "40"))

    def test_commas_periods_and_trailing_zeros(self):
        c = extract_claims(f"- {G} Loaded 1,240 rows and 3.50 days. Then 27.")
        self.assertEqual([x["key"] for x in c], ["1240", "3.5", "27"])
        self.assertEqual(c[0]["text"], "1,240")

    def test_code_spans_links_and_urls_are_not_claims(self):
        line = f"- {G} 31 cases (`step_04`, `p95`) [log](./logs/run_17.txt) https://example.com/v2/18 and 44"
        self.assertEqual(texts(line), [(1, "31"), (1, "44")])

    def test_fenced_block_is_skipped_even_with_a_green_circle_inside(self):
        readme = f"```text\n{G} 99 inside\n```\n- {G} 12 outside\n"
        self.assertEqual(texts(readme), [(4, "12")])

    def test_wrapped_bullet_is_one_item_and_the_claim_keeps_its_own_line(self):
        readme = f"- {G} First: 25 of 25, and\n  second 40 on the next line\n- {G} Next item: 77\n"
        self.assertEqual(texts(readme), [(1, "25 of 25"), (2, "40"), (3, "77")])

    def test_blank_line_ends_a_paragraph(self):
        readme = f"{G} first 11\n\nsecond paragraph 22\n"
        self.assertEqual(texts(readme), [(1, "11")])

    def test_table_row_is_its_own_item(self):
        readme = f"| {G} a | 12 |\n| b | 34 |\n"
        self.assertEqual(texts(readme), [(1, "12")])

    def test_no_green_circle_means_no_claims(self):
        self.assertEqual(extract_claims(f"- {Y} 12\n- plain 34\n"), [])
        self.assertEqual(extract_claims(""), [])

    def test_non_ascii_digits_are_not_numbers(self):
        self.assertEqual(texts(f"- {G} ٤٢ and ４２"), [])

    def test_carriage_returns_do_not_split_or_leak(self):
        self.assertEqual(texts(f"- {G} 12\r\n- {G} 34\r\n"), [(1, "12"), (2, "34")])


if __name__ == "__main__":
    unittest.main()
