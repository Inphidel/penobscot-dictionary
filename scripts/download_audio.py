#!/usr/bin/env python3
"""Download all audio files referenced in entries.json."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from tqdm import tqdm

from common import AUDIO_DIR, AUDIO_LOG_JSON, ENTRIES_JSON, ensure_dirs, load_json, save_json

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "PenobscotDictionaryArchive/1.0 (language revitalization)"


def collect_audio_urls(entries: dict) -> list[dict]:
    seen: set[str] = set()
    items: list[dict] = []
    for entry in entries.values():
        for audio in entry.get("audio", []):
            url = audio.get("remote_url", "")
            filename = audio.get("filename", "")
            if url and filename and url not in seen:
                seen.add(url)
                items.append({"url": url, "filename": filename, "entry_id": entry["id"]})
    return items


def download_one(item: dict) -> dict:
    dest = AUDIO_DIR / item["filename"]
    result = {"filename": item["filename"], "url": item["url"], "entry_id": item["entry_id"]}

    if dest.exists() and dest.stat().st_size > 0:
        result.update({"status": "skipped", "size": dest.stat().st_size})
        return result

    try:
        resp = SESSION.get(item["url"], timeout=60, stream=True)
        if resp.status_code == 404:
            result.update({"status": "missing", "http_code": 404})
            return result
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        result.update({"status": "ok", "size": dest.stat().st_size})
    except requests.RequestException as exc:
        result.update({"status": "error", "error": str(exc)})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Penobscot Dictionary audio")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    ensure_dirs()
    catalog = load_json(ENTRIES_JSON, {"entries": {}})
    entries = catalog.get("entries", {})
    if not entries:
        print("No entries found. Run spider.py first.")
        return 1

    items = collect_audio_urls(entries)
    print(f"Downloading {len(items)} audio files...")

    log = load_json(AUDIO_LOG_JSON, {"files": {}})
    ok = skipped = missing = errors = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download_one, item): item for item in items}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Audio", unit="file"):
            result = future.result()
            log["files"][result["filename"]] = result
            status = result.get("status")
            if status == "ok":
                ok += 1
            elif status == "skipped":
                skipped += 1
            elif status == "missing":
                missing += 1
            else:
                errors += 1

    log["summary"] = {"ok": ok, "skipped": skipped, "missing": missing, "errors": errors, "total": len(items)}
    save_json(AUDIO_LOG_JSON, log)

    for entry in entries.values():
        for audio in entry.get("audio", []):
            fn = audio.get("filename", "")
            local = AUDIO_DIR / fn
            audio["downloaded"] = local.exists() and local.stat().st_size > 0

    catalog["entries"] = entries
    catalog["meta"]["audio_downloaded"] = ok + skipped
    save_json(ENTRIES_JSON, catalog)

    print(f"Done: {ok} downloaded, {skipped} skipped, {missing} missing, {errors} errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())