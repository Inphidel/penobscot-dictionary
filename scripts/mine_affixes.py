#!/usr/bin/env python3
"""Mine affix and example-label patterns from the dictionary archive."""

from __future__ import annotations

import argparse
import re
import unicodedata
from collections import Counter, defaultdict

from common import (
    AFFIX_PATTERNS_JSON,
    BASE_WORDS_JSON,
    ENGLISH_INDEX_JSON,
    ENTRIES_JSON,
    GUESSER_FORMS_JSON,
    SENTENCE_EXAMPLES_JSON,
    ensure_dirs,
    fold_ascii,
    load_json,
    save_json,
)

# Longest first — used when stripping prefixes during guessing
KNOWN_PREFIX_SEEDS = [
    "nəta", "nətα", "nət", "nə", "kilə", "el", "α", "k", "m", "w", "p", "t",
]

ENGLISH_PERSON_HINTS = {
    "i...": "first person singular",
    "we...": "first person plural",
    "you...": "second person",
    "he...": "third person animate",
    "she...": "third person animate",
    "they...": "third person plural",
    "that it...": "obviative / conjunct",
    "c. conj.": "conjunct form",
}


def norm(text: str) -> str:
    return unicodedata.normalize("NFC", text.strip())


def mine_prefix_counts(entries: dict) -> list[dict]:
    counts: Counter = Counter()
    samples: dict[tuple, str] = {}

    for entry in entries.values():
        hw = norm(entry.get("headword", ""))
        if not hw or hw.startswith("|-") or hw.endswith("-"):
            continue
        for ex in entry.get("examples", []):
            form = norm(ex.get("penobscot", ""))
            if not form or form == hw:
                continue
            en = (ex.get("english") or "").strip().lower()
            pos = ex.get("part_of_speech", "")
            for prefix in sorted(KNOWN_PREFIX_SEEDS, key=len, reverse=True):
                if form.startswith(prefix) and len(form) > len(prefix) + 2:
                    hint = ENGLISH_PERSON_HINTS.get(en, en[:40] if en else pos or "example form")
                    key = (prefix, hint)
                    counts[key] += 1
                    if key not in samples:
                        samples[key] = f"{hw} → {form}"
                    break
            if hw in form:
                idx = form.index(hw)
                if idx > 0:
                    prefix = form[:idx]
                    if len(prefix) >= 2:
                        hint = ENGLISH_PERSON_HINTS.get(en, en[:40] if en else "contains headword")
                        key = (prefix, hint)
                        counts[key] += 1
                        if key not in samples:
                            samples[key] = f"{hw} → {form}"

    rows = []
    for (prefix, hint), count in counts.most_common(80):
        if count < 3:
            continue
        rows.append({
            "prefix": prefix,
            "prefix_ascii": fold_ascii(prefix),
            "hint": hint,
            "count": count,
            "sample": samples.get((prefix, hint), ""),
        })
    return rows


def mine_example_labels(entries: dict) -> list[dict]:
    label_counts: Counter = Counter()
    label_samples: dict[str, str] = {}

    for entry in entries.values():
        hw = entry.get("headword", "")
        for ex in entry.get("examples", []):
            pos = (ex.get("part_of_speech") or "").strip()
            if not pos:
                continue
            label_counts[pos] += 1
            if pos not in label_samples:
                form = ex.get("penobscot", "")
                label_samples[pos] = f"{hw}: {form}"

    return [
        {"label": label, "count": count, "sample": label_samples.get(label, "")}
        for label, count in label_counts.most_common(40)
        if count >= 5
    ]


def build_guesser_forms(entries: dict) -> list[dict]:
    """Flat index of headwords and example forms for the Lab guesser."""
    forms: list[dict] = []
    seen: set[tuple] = set()

    def add(form: str, entry: dict, kind: str, english: str = "", pos: str = "", ex_pos: str = ""):
        form = norm(form)
        if not form:
            return
        key = (form, entry["id"], kind)
        if key in seen:
            return
        seen.add(key)
        main, alt = "", ""
        for a in entry.get("audio", []):
            lp = a.get("local_path", "")
            if a.get("type") == "guide":
                alt = lp
            else:
                main = lp
        forms.append({
            "form": form,
            "form_ascii": fold_ascii(form),
            "entry_id": entry["id"],
            "headword": entry.get("headword", ""),
            "kind": kind,
            "english": english or entry.get("english", ""),
            "part_of_speech": pos or entry.get("part_of_speech", ""),
            "example_pos": ex_pos,
            "audio_main": main,
            "audio_alt": alt,
        })

    for entry in entries.values():
        add(entry.get("headword", ""), entry, "headword")
        for ex in entry.get("examples", []):
            add(
                ex.get("penobscot", ""),
                entry,
                "example",
                english=ex.get("english", ""),
                ex_pos=ex.get("part_of_speech", ""),
            )

    return forms


def build_base_words(entries: dict) -> list[dict]:
    """Headwords only — building blocks for sentence composition."""
    words: list[dict] = []
    seen: set[str] = set()

    for entry in entries.values():
        hw = norm(entry.get("headword", ""))
        if not hw or hw.startswith("|-") or hw.endswith("-"):
            continue
        folded = fold_ascii(hw)
        if len(folded) < 2 or folded in seen:
            continue
        seen.add(folded)
        main, alt = "", ""
        for a in entry.get("audio", []):
            lp = a.get("local_path", "")
            if a.get("type") == "guide":
                alt = lp
            else:
                main = lp
        words.append({
            "entry_id": entry["id"],
            "headword": hw,
            "fold": folded,
            "english": (entry.get("english") or "").strip(),
            "part_of_speech": entry.get("part_of_speech", ""),
            "audio_main": main,
            "audio_alt": alt,
        })

    words.sort(key=lambda w: len(w["fold"]), reverse=True)
    return words


def _is_sentence_example(form: str, english: str, pos: str) -> bool:
    en = (english or "").strip()
    if not form or not en or len(en) < 8:
        return False
    bare = form.lstrip("→").strip()
    if en.endswith("...") or en.endswith("...,"):
        return False
    if pos in ("pl.", "sing.", "c. conj.") and len(en) < 18:
        return False
    if " " in bare:
        return True
    return len(en) >= 14 and (en.endswith(".") or en.endswith("?") or " " in en)


def build_english_index(entries: dict) -> list[dict]:
    """English definitions tokenized for Lab reverse lookup."""
    items: list[dict] = []
    for entry in entries.values():
        en = (entry.get("english") or "").strip()
        if len(en) < 4:
            continue
        tokens = sorted({
            t for t in re.findall(r"[a-z']{3,}", en.lower())
            if t not in {"the", "and", "for", "are", "was", "with", "that", "this", "from", "has", "have"}
        })
        if not tokens:
            continue
        items.append({
            "entry_id": entry["id"],
            "headword": entry.get("headword", ""),
            "english": en,
            "tokens": tokens,
            "part_of_speech": entry.get("part_of_speech", ""),
        })
    return items


def build_sentence_examples(entries: dict) -> list[dict]:
    """Multi-word archive examples with full English readings."""
    sentences: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for entry in entries.values():
        hw = entry.get("headword", "")
        for ex in entry.get("examples", []):
            form = norm(ex.get("penobscot", ""))
            en = (ex.get("english") or "").strip()
            pos = (ex.get("part_of_speech") or "").strip()
            if not _is_sentence_example(form, en, pos):
                continue
            key = (form, en)
            if key in seen:
                continue
            seen.add(key)
            sentences.append({
                "form": form,
                "form_ascii": fold_ascii(form),
                "english": en,
                "entry_id": entry["id"],
                "headword": hw,
                "example_pos": pos,
            })

    sentences.sort(key=lambda s: len(s["form_ascii"]), reverse=True)
    return sentences


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine affix patterns for Lab tools")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    ensure_dirs()
    catalog = load_json(ENTRIES_JSON, {"entries": {}})
    entries = catalog.get("entries", {})
    if not entries:
        print("No entries. Run spider.py first.")
        return 1

    prefixes = mine_prefix_counts(entries)
    labels = mine_example_labels(entries)
    forms = build_guesser_forms(entries)
    base_words = build_base_words(entries)
    sentences = build_sentence_examples(entries)
    english_index = build_english_index(entries)

    data = {
        "meta": {
            "source": "entries.json",
            "prefix_rules": len(prefixes),
            "example_labels": len(labels),
            "indexed_forms": len(forms),
            "base_words": len(base_words),
            "sentence_examples": len(sentences),
            "english_index": len(english_index),
        },
        "prefixes": prefixes,
        "example_labels": labels,
    }
    save_json(AFFIX_PATTERNS_JSON, data)
    save_json(GUESSER_FORMS_JSON, {"forms": forms, "total": len(forms)})
    save_json(BASE_WORDS_JSON, {"words": base_words, "total": len(base_words)})
    save_json(SENTENCE_EXAMPLES_JSON, {"sentences": sentences, "total": len(sentences)})
    save_json(ENGLISH_INDEX_JSON, {"entries": english_index, "total": len(english_index)})

    print(f"Mined {len(prefixes)} prefix patterns, {len(labels)} example labels")
    print(f"Indexed {len(forms)} forms -> {GUESSER_FORMS_JSON}")
    print(f"Indexed {len(base_words)} base words, {len(sentences)} sentence examples, {len(english_index)} english entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())