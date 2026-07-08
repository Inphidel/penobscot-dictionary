#!/usr/bin/env python3
"""Generate per-entry Markdown files from entries.json."""

from __future__ import annotations

import argparse
import textwrap

from common import ENTRIES_DIR, ENTRIES_JSON, ensure_dirs, load_json, slugify


def yaml_escape(value: str) -> str:
    if not value:
        return '""'
    if any(c in value for c in ':"\n#[]{}'):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def build_entry_md(entry: dict) -> str:
    lines = ["---"]
    lines.append(f'id: "{entry["id"]}"')
    lines.append(f"headword: {yaml_escape(entry.get('headword', ''))}")
    if entry.get("part_of_speech"):
        lines.append(f"part_of_speech: {yaml_escape(entry['part_of_speech'])}")
    if entry.get("sub_part_of_speech"):
        lines.append(f"sub_part_of_speech: {yaml_escape(entry['sub_part_of_speech'])}")
    if entry.get("english"):
        lines.append(f"english: {yaml_escape(entry['english'])}")
    if entry.get("browse_letters"):
        lines.append(f"browse_letters: {entry['browse_letters']}")
    if entry.get("audio"):
        lines.append("audio:")
        for a in entry["audio"]:
            lines.append(f"  - type: {a.get('type', 'main')}")
            lines.append(f"    file: {a.get('local_path', '')}")
            lines.append(f"    remote: {a.get('remote_url', '')}")
    lines.append(f"source_url: {entry.get('source_url', '')}")
    lines.append("---")
    lines.append("")

    hw = entry.get("headword", "")
    lines.append(f"# {hw}")
    lines.append("")

    pos_parts = [p for p in [entry.get("part_of_speech"), entry.get("sub_part_of_speech")] if p]
    if pos_parts:
        lines.append(f"**Part of speech:** {' · '.join(pos_parts)}")
        lines.append("")

    if entry.get("english"):
        lines.append(f"**English:** {entry['english']}")
        lines.append("")

    if entry.get("audio"):
        lines.append("## Audio")
        lines.append("")
        for a in entry["audio"]:
            label = "Guide pronunciation" if a.get("type") == "guide" else "Main pronunciation"
            path = a.get("local_path", "")
            lines.append(f"- [{label}](../{path})")
        lines.append("")

    if entry.get("examples"):
        lines.append("## Examples")
        lines.append("")
        lines.append("| Penobscot | English | POS |")
        lines.append("|-----------|---------|-----|")
        for ex in entry["examples"]:
            p = ex.get("penobscot", "").replace("|", "\\|")
            e = ex.get("english", "").replace("|", "\\|")
            pos = ex.get("part_of_speech", "").replace("|", "\\|")
            lines.append(f"| {p} | {e} | {pos} |")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Markdown from entries.json")
    parser.add_argument("--letter", type=str, help="Build only one letter section")
    args = parser.parse_args()

    ensure_dirs()
    catalog = load_json(ENTRIES_JSON, {"entries": {}})
    entries: dict = catalog.get("entries", {})
    if not entries:
        print("No entries. Run spider.py first.")
        return 1

    by_letter: dict[str, list] = {}
    for entry in entries.values():
        letters = entry.get("browse_letters") or ["uncategorized"]
        if args.letter and args.letter not in letters:
            continue
        primary = letters[0]
        by_letter.setdefault(primary, []).append(entry)

    for letter, letter_entries in sorted(by_letter.items()):
        letter_dir = ENTRIES_DIR / letter
        letter_dir.mkdir(parents=True, exist_ok=True)
        letter_entries.sort(key=lambda e: e.get("headword", "").lower())

        index_lines = [f"# Browse: {letter}", "", f"*{len(letter_entries)} entries*", "", "| Word | English |", "|------|---------|"]
        for entry in letter_entries:
            slug = slugify(entry["headword"], entry["id"])
            md_path = letter_dir / f"{slug}.md"
            md_path.write_text(build_entry_md(entry), encoding="utf-8")
            hw = entry.get("headword", "").replace("|", "\\|")
            en = (entry.get("english") or "")[:80].replace("|", "\\|")
            index_lines.append(f"| [{hw}]({slug}.md) | {en} |")
        (letter_dir / "_index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    readme = textwrap.dedent(f"""\
        # Penobscot Dictionary — Local Archive

        {len(entries)} entries archived from [penobscot-dictionary.appspot.com](https://penobscot-dictionary.appspot.com/entry/).

        ## Browse by letter

    """)
    for letter in sorted(by_letter):
        count = len(by_letter[letter])
        readme += f"- [{letter}]({letter}/_index.md) — {count} entries\n"

    (ENTRIES_DIR / "README.md").write_text(readme, encoding="utf-8")
    print(f"Built {len(entries)} markdown files in {ENTRIES_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())