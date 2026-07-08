#!/usr/bin/env python3
"""Sample integrated loudness (LUFS) of dictionary MP3s."""

from __future__ import annotations

import json
import random
import re
import subprocess
import sys
from pathlib import Path

from common import AUDIO_DIR, ROOT


def measure_file(path: Path) -> dict | None:
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-af", "loudnorm=print_format=json", "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stderr = proc.stderr
    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def main() -> int:
    audio = AUDIO_DIR
    if not audio.exists():
        audio = ROOT / "site" / "audio"
    files = sorted(f for f in audio.glob("*.mp3") if "-gp" not in f.name)
    if not files:
        print("No mp3 files found.")
        return 1

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    sample = random.sample(files, min(n, len(files)))

    loudness = []
    print(f"Measuring {len(sample)} files from {audio}...\n")
    for f in sample:
        data = measure_file(f)
        if not data:
            print(f"  {f.name}: failed")
            continue
        lufs = float(data.get("input_i", 0))
        peak = float(data.get("input_tp", 0))
        loudness.append(lufs)
        print(f"  {f.name}: {lufs:6.1f} LUFS  (true peak {peak:5.1f} dBTP)")

    if loudness:
        loudness.sort()
        mid = len(loudness) // 2
        print(f"\nRange: {min(loudness):.1f} to {max(loudness):.1f} LUFS")
        print(f"Median: {loudness[mid]:.1f} LUFS")
        print(f"\nSpeech-friendly target is often -18 to -16 LUFS (comfortable, not crushed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())