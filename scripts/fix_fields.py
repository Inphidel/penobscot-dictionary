#!/usr/bin/env python3
"""Fix field mapping in existing entries.json without re-crawling."""

from __future__ import annotations

from common import ENTRIES_JSON, load_json, save_json


def normalize_fields(entry: dict) -> dict:
    fields = entry.get("fields", {})
    normalized = {}
    for key, value in fields.items():
        nk = key.strip("_").lower()
        normalized[nk] = value
    entry["fields"] = normalized
    entry["part_of_speech"] = normalized.get("part_of_speech", entry.get("part_of_speech", ""))
    entry["sub_part_of_speech"] = normalized.get("sub_part_of_speech", entry.get("sub_part_of_speech", ""))
    entry["english"] = normalized.get("english_translation", entry.get("english", ""))
    return entry


def main() -> int:
    catalog = load_json(ENTRIES_JSON, {"entries": {}, "meta": {}})
    entries = catalog.get("entries", {})
    for eid in entries:
        entries[eid] = normalize_fields(entries[eid])
    catalog["entries"] = entries
    with_english = sum(1 for e in entries.values() if e.get("english"))
    catalog["meta"]["entries_with_english"] = with_english
    save_json(ENTRIES_JSON, catalog)
    print(f"Fixed {len(entries)} entries ({with_english} with English definitions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())