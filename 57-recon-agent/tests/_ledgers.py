"""Helpers that write small ledgers to a temporary folder and load them through the real loader."""
import csv
import os
import tempfile

import _bootstrap  # noqa: F401
import recon_agent as ra

A_HEAD = list(ra.SIDE_COLUMNS["A"])
B_HEAD = list(ra.SIDE_COLUMNS["B"])


def a_line(ident, day, amount, name="Brindle Foods Ltd", ref="", ccy="USD", narrative="CREDIT TRANSFER"):
    return [ident, day, amount, ccy, name, narrative, ref]


def b_line(ident, day, amount, name="Brindle Foods Limited", ref="", batch="", ccy="USD", memo="Receipt"):
    return [ident, day, amount, ccy, name, ref, batch, memo]


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


class Workspace:
    """A temporary folder with helpers to write ledgers and load rows."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def close(self):
        self._tmp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)

    def ledgers(self, a_rows, b_rows):
        write_csv(self.path("a.csv"), A_HEAD, a_rows)
        write_csv(self.path("b.csv"), B_HEAD, b_rows)
        return self.path("a.csv"), self.path("b.csv")

    def rows(self, a_rows, b_rows):
        pa, pb = self.ledgers(a_rows, b_rows)
        return ra.load_ledger(pa, "A"), ra.load_ledger(pb, "B")
