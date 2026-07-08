#!/usr/bin/env python3
"""Run the full archive pipeline: spider -> audio -> markdown -> site."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent


def run(script: str, *args: str) -> int:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    print(f"\n{'='*60}\n>>> {' '.join(cmd)}\n{'='*60}")
    return subprocess.call(cmd)


def main() -> int:
    steps = [
        ("spider.py",),
        ("download_audio.py",),
        ("build_markdown.py",),
        ("build_site.py",),
    ]
    for step in steps:
        rc = run(*step)
        if rc != 0:
            print(f"Step failed: {step[0]} (exit {rc})", file=sys.stderr)
            return rc
    print("\nPipeline complete. Start the local server:")
    print("  python -m http.server 8080 --directory site")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())