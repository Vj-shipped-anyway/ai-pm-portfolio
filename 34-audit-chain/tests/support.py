"""Helpers shared by the tests: build well-formed events by hand, and run the command line in process."""
import contextlib
import io
import json
import os
import tempfile

import _bootstrap  # noqa: F401
import audit_chain as ac


def event(seq, prev, kind="decision", **over):
    """A well-formed event with a correct hash; keyword arguments replace fields before the hash is computed."""
    core = {"seq": seq, "case_id": "C1", "step": "S01", "kind": kind, "actor": "agent", "detail": {"decided": "continue"}}
    core.update(over)
    ev = dict(core)
    ev["prev"] = prev
    ev["hash"] = ac.digest(prev, core)
    return ev


def chain(n=5):
    evs, prev = [], ac.GENESIS
    for i in range(1, n + 1):
        evs.append(event(i, prev))
        prev = evs[-1]["hash"]
    return evs


def lines(evs):
    return [ac.dumps_event(e) for e in evs]


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ac.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class TempDir:
    """Mixin: self.dir is a fresh directory; self.write(name, text_or_bytes) puts a file in it and self.read(path) returns bytes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def write(self, name, content):
        p = os.path.join(self.dir, name)
        with open(p, "wb") as fh:
            fh.write(content if isinstance(content, bytes) else content.encode("utf-8"))
        return p

    def read(self, path):
        with open(path, "rb") as fh:
            return fh.read()

    def write_log(self, evs, name="log.jsonl"):
        return self.write(name, "".join(x + "\n" for x in lines(evs)))

    def write_json(self, name, obj):
        return self.write(name, json.dumps(obj))
