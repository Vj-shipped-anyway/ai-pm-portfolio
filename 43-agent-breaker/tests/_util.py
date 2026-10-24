import contextlib
import csv
import io
import os

import _bootstrap  # noqa: F401
import agent_breaker as ab

EVENT_HEADER = list(ab.EVENT_COLS)


def write_csv(folder, name, header, rows):
    path = os.path.join(folder, name)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ab.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


def feed(fleet, agent, outcomes, start=0, step=1, kind="tool_error"):
    """Send a list of 'ok'/'fail' outcomes, one call every `step` minutes. Returns the routing records."""
    return [fleet.handle(start + i * step, agent, f"c{start}-{i}", o, kind if o == "fail" else None) for i, o in enumerate(outcomes)]


def policy(**kw):
    p = ab.default_policy()
    p.update(kw)
    return p
