"""Fetch the BPI Challenge 2012 event log into data/real/raw/ and check it against the published MD5.

Standard library only, Python 3.9 or newer. Run from anywhere:

    python3 fetch_bpi2012.py

The log is not committed to this repo. It is a 3.3 MB public file from 4TU.ResearchData:

    van Dongen, B.F. (2012): BPI Challenge 2012. Version 1. 4TU.ResearchData. dataset.
    DOI 10.4121/uuid:3926db30-f712-4394-aebc-75976070e91f

The 4TU file server returns 502 at times; the script retries and, if it still fails, says so and exits 1.
"""

from __future__ import annotations

import hashlib
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = ("https://data.4tu.nl/file/533f66a4-8911-4ac7-8612-1235d65d1f37/"
       "3276db7f-8bee-4f2b-88ee-92dbffb5a893")
NAME = "BPI_Challenge_2012.xes.gz"
SIZE = 3342406
MD5 = "74c7ba9aba85bfcb181a22c9d565e5b5"
DEST = Path(__file__).resolve().parent / "raw" / NAME
TRIES = 8
PAUSE_S = 20


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if DEST.exists() and md5_of(DEST) == MD5:
        print("Already on disk and the MD5 matches: %s" % DEST)
        return 0
    DEST.parent.mkdir(parents=True, exist_ok=True)
    part = DEST.with_suffix(DEST.suffix + ".part")
    for attempt in range(1, TRIES + 1):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "ai-pm-portfolio-fetch/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(part, "wb") as out:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
        except (urllib.error.URLError, OSError) as e:
            print("try %d of %d: %s" % (attempt, TRIES, e))
            if attempt < TRIES:
                time.sleep(PAUSE_S)
            continue
        got = md5_of(part)
        if got != MD5:
            print("try %d of %d: MD5 %s, expected %s" % (attempt, TRIES, got, MD5))
            part.unlink()
            if attempt < TRIES:
                time.sleep(PAUSE_S)
            continue
        part.replace(DEST)
        print("Saved %s (%s bytes, expected %s); MD5 matches." % (DEST, format(DEST.stat().st_size, ","), format(SIZE, ",")))
        return 0
    print("Could not fetch the log. Download %s from the dataset page and place it at %s" % (NAME, DEST))
    return 1


if __name__ == "__main__":
    sys.exit(main())
