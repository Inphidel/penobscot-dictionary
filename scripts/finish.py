#!/usr/bin/env python3
"""After spider completes: download remaining audio, build markdown + site."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from common import ENTRIES_JSON, load_json

SCRIPTS = Path(__file__).parent


def run(script: str, *args: str) -> int:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.call(cmd)


def main() -> int:
    catalog = load_json(ENTRIES_JSON, {"entries": {}})
    n = len(catalog.get("entries", {}))
    if n == 0:
        print("No entries yet. Wait for spider.py to finish, then run this again.")
        return 1
    print(f"Building archive from {n} entries...")
    steps = [
        ("download_audio.py", "--workers", "8"),
        ("build_markdown.py",),
        ("build_site.py",),
    ]
    for step in steps:
        rc = run(step[0], *step[1:])
        if rc != 0:
            return rc
    print("\nReady! Open http://localhost:8080")
    print("  python -m http.server 8080 --directory site")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())