"""Run the command line in-process and capture what it prints."""
import contextlib
import io

import kyb_packet_check as kpc


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = kpc.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()
