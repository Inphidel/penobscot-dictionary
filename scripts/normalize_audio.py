#!/usr/bin/env python3
"""Normalize dictionary MP3 loudness using FFmpeg EBU R128 loudnorm (two-pass).

Targets perceived loudness (LUFS), not just peak volume — so quiet speech is
brought up without crushing louder moments inside each clip. Originals are
backed up before overwriting.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from common import AUDIO_DIR, DATA_DIR, ensure_dirs, load_json, save_json

BACKUP_DIR = AUDIO_DIR.parent / "audio_original"
LOG_JSON = DATA_DIR / "audio_normalize_log.json"

DEFAULT_TARGET_LUFS = -15.0  # ~50% louder than -18 LUFS; comfortable speech level
DEFAULT_TRUE_PEAK = -1.0
DEFAULT_LRA = 11.0
QUIET_THRESHOLD_LUFS = -26.0  # below this, add gentle compression to reach target


def find_ffmpeg() -> str:
    return "ffmpeg"


def measure_loudnorm(
    path: Path,
    *,
    target_lufs: float = DEFAULT_TARGET_LUFS,
    true_peak: float = DEFAULT_TRUE_PEAK,
    lra: float = DEFAULT_LRA,
) -> dict | None:
    cmd = [
        find_ffmpeg(), "-hide_banner", "-nostats", "-y", "-i", str(path),
        "-af", f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}:print_format=json",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def normalize_file(
    src: Path,
    dst: Path,
    *,
    target_lufs: float,
    true_peak: float,
    lra: float,
) -> dict:
    """Normalize to target LUFS; extra compression for very quiet archive recordings."""
    stats = measure_loudnorm(src, target_lufs=target_lufs, true_peak=true_peak, lra=lra)
    if not stats:
        raise RuntimeError("loudnorm measure failed")

    before_lufs = float(stats["input_i"])
    ln = f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}"
    if before_lufs < QUIET_THRESHOLD_LUFS:
        # Very quiet clips need mild compression to reach target without clipping
        af_apply = (
            "volume=8dB,"
            "acompressor=threshold=-30dB:ratio=3:attack=2:release=50,"
            f"{ln}"
        )
        mode = "quiet+compress"
    else:
        af_apply = ln
        mode = "standard"

    encode_cmd = [
        find_ffmpeg(), "-hide_banner", "-nostats", "-y", "-i", str(src),
        "-af", af_apply,
        "-ar", "44100",
        "-c:a", "libmp3lame", "-q:a", "2",
        str(dst),
    ]
    proc = subprocess.run(encode_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-500:] or "loudnorm encode failed")
    return {
        "before_lufs": before_lufs,
        "before_peak": float(stats["input_tp"]),
        "target_lufs": target_lufs,
        "mode": mode,
    }


def list_mp3s(audio_dir: Path) -> list[Path]:
    return sorted(audio_dir.glob("*.mp3"))


def backup_file(src: Path, backup_dir: Path) -> None:
    dest = backup_dir / src.name
    if dest.exists():
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize MP3 loudness (EBU R128 loudnorm)")
    parser.add_argument("--target", type=float, default=DEFAULT_TARGET_LUFS,
                        help=f"Target integrated loudness in LUFS (default {DEFAULT_TARGET_LUFS})")
    parser.add_argument("--true-peak", type=float, default=DEFAULT_TRUE_PEAK,
                        help=f"Max true peak in dBTP (default {DEFAULT_TRUE_PEAK})")
    parser.add_argument("--lra", type=float, default=DEFAULT_LRA, help="Loudness range (default 11)")
    parser.add_argument("--limit", type=int, default=0, help="Only process N files (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Measure only, do not write files")
    parser.add_argument("--no-backup", action="store_true", help="Skip copying originals to audio_original/")
    parser.add_argument("--force", action="store_true", help="Re-process files already in log")
    args = parser.parse_args()

    ensure_dirs()
    audio_dir = AUDIO_DIR
    if not audio_dir.exists():
        print(f"Audio directory not found: {audio_dir}")
        return 1

    files = list_mp3s(audio_dir)
    if args.limit:
        files = files[: args.limit]

    log = load_json(LOG_JSON, {"done": {}, "errors": {}})
    done: dict = log.get("done", {})

    print(f"Found {len(files)} mp3 files in {audio_dir}")
    print(f"Target: {args.target} LUFS, true peak {args.true_peak} dBTP")
    if args.dry_run:
        print("DRY RUN — measuring only\n")

    ok = 0
    err = 0
    for i, path in enumerate(files, 1):
        if path.name in done and not args.force and not args.dry_run:
            continue
        if args.dry_run:
            stats = measure_loudnorm(
                path, target_lufs=args.target, true_peak=args.true_peak, lra=args.lra,
            )
            if stats:
                print(f"  {path.name}: {float(stats['input_i']):.1f} LUFS")
                ok += 1
            else:
                print(f"  {path.name}: measure failed")
                err += 1
            continue

        try:
            if not args.no_backup:
                backup_file(path, BACKUP_DIR)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            normalize_file(
                path, tmp_path,
                target_lufs=args.target,
                true_peak=args.true_peak,
                lra=args.lra,
            )
            tmp_path.replace(path)
            done[path.name] = {"target_lufs": args.target}
            ok += 1
        except Exception as exc:
            log.setdefault("errors", {})[path.name] = str(exc)
            err += 1
            print(f"  ERROR {path.name}: {exc}")

        if i % 100 == 0 or i == len(files):
            print(f"  Progress: {i}/{len(files)} ({ok} ok, {err} errors)")
            log["done"] = done
            save_json(LOG_JSON, log)

    if not args.dry_run:
        log["done"] = done
        log["meta"] = {
            "target_lufs": args.target,
            "true_peak": args.true_peak,
            "processed": ok,
            "errors": err,
        }
        save_json(LOG_JSON, log)
        print(f"\nFinished: {ok} normalized, {err} errors")
        if not args.no_backup:
            print(f"Originals backed up to {BACKUP_DIR}")
    else:
        print(f"\nMeasured {ok} files")

    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())