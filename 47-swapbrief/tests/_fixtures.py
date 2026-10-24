"""Small paired result sets for the tests. System names are `old` and `new`; slices are `a` and `b`."""
import csv

COLUMNS = ["item_id", "slice", "system", "correct", "input_tokens", "output_tokens", "latency_ms"]


def make_rows(n=120, out_mult=1.0, lat_mult=1.0, drop_slice=None, slice_a="a"):
    """The old system is right on 80% of items. The new one matches it unless told otherwise:
    out_mult stretches its answers, lat_mult stretches its latency, drop_slice makes it wrong on
    every even-numbered item it used to get right in that slice."""
    rows = []
    for k in range(n):
        sl = slice_a if k < n // 2 else "b"
        ok = 0 if k % 5 == 0 else 1
        tin, tout, lat = 500 + k, 100 + (k % 7) * 5, 1000 + (k * 37) % 400
        new_ok = 0 if (drop_slice == sl and ok and k % 2 == 0) else ok
        for system, c, o, ms in (("old", ok, tout, lat), ("new", new_ok, int(tout * out_mult), int(lat * lat_mult))):
            rows.append({"item_id": "I%04d" % k, "slice": sl, "system": system, "correct": str(c),
                         "input_tokens": str(tin), "output_tokens": str(o), "latency_ms": str(ms)})
    return rows


def write_results(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def write_prices(path, new_in=0.003, new_out=0.015):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write("system,input_usd_per_1k,output_usd_per_1k\nold,0.003,0.015\nnew,%s,%s\n" % (new_in, new_out))
