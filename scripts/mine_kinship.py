#!/usr/bin/env python3
"""Mine kinship, perspective, and possession patterns from the dictionary."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict

from common import ENTRIES_JSON, LAB_DATA_DIR, ensure_dirs, fold_ascii, load_json, save_json

KINSHIP_INDEX_JSON = LAB_DATA_DIR / "kinship_index.json"

# Curated categories — each has match rules and optional morph hints shown in UI.
CATEGORIES: list[dict] = [
    {
        "id": "mother",
        "label": "Mother",
        "group": "Family role",
        "description": "Words about mothers or mother-like roles",
        "english_patterns": [
            r"\bshe is a mother\b",
            r"\bfrom my mother\b",
            r"\bmother's place\b",
            r"\bbehaves like a mother\b",
        ],
        "headword_patterns": [r"wikawəss"],
        "morph_hints": [
            ("wikawəss", "Root seen in mother-related words (wikáwəsso = she is a mother)"),
            ("-əssəwamto", "Suffix pattern: act/behave like… (-amto = act like)"),
        ],
    },
    {
        "id": "father",
        "label": "Father",
        "group": "Family role",
        "description": "Words about fathers, stepfathers, or father-like roles",
        "english_patterns": [
            r"\bhe has a father\b",
            r"\bbehaves like a father\b",
            r"\bstepfather\b",
        ],
        "headword_patterns": [r"mihtαkʷ", r"mihtakw", r"\|mihtαkws"],
        "morph_hints": [
            ("mihtαkʷ", "Root seen in father-related words (míhtαkʷso = he has a father)"),
            ("-əwamto", "Suffix: act/behave like a father"),
        ],
    },
    {
        "id": "daughter",
        "label": "Daughter",
        "group": "Family role",
        "description": "Words about daughters",
        "english_patterns": [
            r"\bshe is his daughter\b",
            r"\bmake her my daughter\b",
            r"\bdaughter-in-law\b",
            r"\bdaughter\b",
        ],
        "headword_patterns": [r"wətos", r"wetos"],
        "morph_hints": [
            ("wətos", "Root for daughter (|wətos-| in dictionary)"),
            ("-in", "Ending on wətosin: she is his daughter"),
        ],
    },
    {
        "id": "son",
        "label": "Son",
        "group": "Family role",
        "description": "Words about sons, adoption, or son-in-law",
        "english_patterns": [
            r"\badopt him as my son\b",
            r"\bson-in-law\b",
            r"\bmake him my son\b",
        ],
        "headword_patterns": [r"nonəmαnk", r"alohsəwe"],
        "morph_hints": [
            ("nə…αnk", "Prefix nə- (I) + …αnk pattern in adoption/son-making verbs"),
        ],
    },
    {
        "id": "brother",
        "label": "Brother",
        "group": "Family role",
        "description": "Words about brothers; older/younger sibling order",
        "english_patterns": [
            r"\bhe is a brother\b",
            r"\boldest brother\b",
            r"\byoungest brother\b",
            r"\bbrother of\b",
        ],
        "headword_patterns": [r"wičəy", r"petαk"],
        "morph_hints": [
            ("wičəyetto", "He is a brother"),
            ("kči-", "Prefix kči- often marks big/elder (kči-pétαki = Big Thunderer, oldest brother)"),
        ],
    },
    {
        "id": "sister",
        "label": "Sister",
        "group": "Family role",
        "description": "Words about sisters",
        "english_patterns": [r"\bshe is a sister\b", r"\bsister\b(?!\s+of\s+the)"],
        "headword_patterns": [],
        "morph_hints": [],
    },
    {
        "id": "wife",
        "label": "Wife",
        "group": "Family role",
        "description": "Words about wives or female spouses",
        "english_patterns": [
            r"\bwife of\b",
            r"\bchief's wife\b",
            r"\babandon my wife\b",
            r"\btwo mates/spouses, wives\b",
            r"\bwife\b(?! locale)",
        ],
        "headword_patterns": [r"sάkəmαskʷe"],
        "morph_hints": [
            ("-skʷe / -kʷe", "Feminine ending seen on many female role words"),
        ],
    },
    {
        "id": "husband",
        "label": "Husband",
        "group": "Family role",
        "description": "Words about husbands or male spouses",
        "english_patterns": [
            r"\babandon my wife or husband\b",
            r"\bwidower\b",
            r"\bhe is a widower\b",
        ],
        "headword_patterns": [r"sikʷαpe", r"sikəwito"],
        "morph_hints": [],
    },
    {
        "id": "spouse",
        "label": "Spouse / partner",
        "group": "Family role",
        "description": "Marriage, separation, or having a spouse",
        "english_patterns": [
            r"\bspouse\b",
            r"\bseparates from his, her spouse\b",
            r"\bhas two mates\b",
            r"\bdivorce my spouse\b",
            r"\bmarried\b",
        ],
        "headword_patterns": [r"čəčap", r"čačep", r"čəpahk"],
        "morph_hints": [],
    },
    {
        "id": "child",
        "label": "Child",
        "group": "Family role",
        "description": "Words about children (young people)",
        "english_patterns": [
            r"\bchild\b",
            r"\bchildren\b",
            r"\bawαssis\b",
        ],
        "headword_patterns": [r"awαssis", r"awassis"],
        "morph_hints": [
            ("awαssis", "Common word for child (about 1–6 years)"),
            ("-sis", "Diminutive/younger ending seen on child-related forms"),
        ],
    },
    {
        "id": "in_law",
        "label": "In-law",
        "group": "Family role",
        "description": "Son-in-law, daughter-in-law, bride's parents",
        "english_patterns": [
            r"\bin-law\b",
            r"\bbride's parents\b",
            r"\bnewly married son-in-law\b",
            r"\bnewly married daughter-in-law\b",
        ],
        "headword_patterns": [r"alohsəwe"],
        "morph_hints": [
            ("alohsəwe", "Newly married son-in-law / bridegroom"),
            ("-skʷe", "Feminine form: alohsəweskʷe = daughter-in-law"),
        ],
    },
    {
        "id": "widow_widower",
        "label": "Widow / widower",
        "group": "Family role",
        "description": "Words for widow or widower",
        "english_patterns": [r"\bwidow\b", r"\bwidower\b"],
        "headword_patterns": [r"sikosk", r"sikʷαpe", r"sikəwito"],
        "morph_hints": [
            ("sikóskʷe", "Widow"),
            ("sikəwito / síkʷαpe", "Widower forms"),
        ],
    },
    {
        "id": "relative",
        "label": "Relative / kin",
        "group": "Family role",
        "description": "Having relatives, kinship respect",
        "english_patterns": [
            r"\bhave .+ for a relative\b",
            r"\bmany relatives\b",
            r"\bmany kin\b",
            r"\brespect for him as a parent or relative\b",
        ],
        "headword_patterns": [r"αkom", r"mselα"],
        "morph_hints": [
            ("-αkom", "Suffix pattern in relative/kinship verbs (…αkomα = I have him for a relative)"),
        ],
    },
    {
        "id": "older_age",
        "label": "Older than",
        "group": "Age & perspective",
        "description": "Being older, elder, exceeding in years",
        "english_patterns": [
            r"\bolder than\b",
            r"\belder, old person\b",
            r"\bexceed him in years\b",
            r"\bgetting old, older\b",
        ],
        "headword_patterns": [r"kčay", r"nəpehəmi", r"kαtənehtaw"],
        "morph_hints": [
            ("kčay", "Elder, old person"),
            ("nəpehəmi-", "Compound: I am older/younger than… (compare age)"),
            ("-kči", "kči- prefix often marks 'big/elder'"),
        ],
    },
    {
        "id": "younger_age",
        "label": "Younger than",
        "group": "Age & perspective",
        "description": "Being younger than someone",
        "english_patterns": [r"\byounger than\b"],
        "headword_patterns": [r"nəpehəmi-awάssis", r"awαssisəwi"],
        "morph_hints": [
            ("awαssisəwi", "Contains awαssis (child) — younger by comparison"),
            ("nəpehəmi-", "Age-comparison compound (paired with older-than forms)"),
        ],
    },
    {
        "id": "possession_my",
        "label": "My (possession)",
        "group": "Whose perspective",
        "description": "First-person possession — my, from my…",
        "english_patterns": [
            r"^my\b",
            r"\bfrom my mother\b",
            r"\bmake him my son\b",
            r"\bmake her my daughter\b",
            r"\bdivorce my spouse\b",
            r"\babandon my wife\b",
        ],
        "headword_patterns": [],
        "morph_hints": [
            ("nə-", "Prefix nə- / nəta- often marks first person I (seen in nəta…, nə… forms)"),
            ("ni-", "Initial ni- sometimes marks my / from me"),
        ],
    },
    {
        "id": "possession_his",
        "label": "His (possession)",
        "group": "Whose perspective",
        "description": "Third-person masculine possession",
        "english_patterns": [
            r"\bhis daughter\b",
            r"\bhis son\b",
            r"\bhis wife\b",
            r"\bhis or her\b",
        ],
        "headword_patterns": [],
        "morph_hints": [
            ("wə-", "Prefix wə- appears in his/her forms (e.g. wətosin = she is his daughter)"),
        ],
    },
    {
        "id": "possession_her",
        "label": "Her (possession)",
        "group": "Whose perspective",
        "description": "Third-person feminine possession",
        "english_patterns": [
            r"\bher husband\b",
            r"\bher son\b",
            r"\bher spouse\b",
            r"\bfrom his, her\b",
        ],
        "headword_patterns": [],
        "morph_hints": [
            ("wə-", "wə- prefix in some his/her possessed forms"),
        ],
    },
    {
        "id": "feminine_ending",
        "label": "Feminine ending (-kʷe / -skʷe)",
        "group": "Word parts",
        "description": "Headwords ending in -kʷe or -skʷe — often feminine nouns or female people",
        "english_patterns": [],
        "headword_patterns": [r"skʷe$", r"kʷe$", r"skwe$", r"kwe$"],
        "morph_hints": [
            ("-skʷe / -kʷe", "Feminine ending — common on words for women and feminine roles"),
            ("wəskʷe", "Female person marker in ethnic/tribal words (…wəskʷe = woman)"),
        ],
    },
    {
        "id": "female_person",
        "label": "Female person words",
        "group": "Grammatical gender",
        "description": "Dictionary entries explicitly about women, wives, mothers, daughters, widows",
        "english_patterns": [
            r"\bshe is a (mother|widow|wife|daughter|woman)\b",
            r"\bwoman\b",
            r"\bwomen\b",
            r"\bwidow\b",
            r"\bdaughter\b",
            r"\bmother\b",
        ],
        "headword_patterns": [],
        "morph_hints": [
            ("-skʷe / -kʷe", "Check for feminine ending on the Penobscot word"),
        ],
    },
    {
        "id": "male_person",
        "label": "Male person words",
        "group": "Grammatical gender",
        "description": "Dictionary entries explicitly about men, fathers, brothers, husbands, widowers",
        "english_patterns": [
            r"\bhe is a (father|brother|widower|husband|man)\b",
            r"\bhe has a father\b",
            r"\bwidower\b",
            r"\bman\b",
        ],
        "headword_patterns": [],
        "morph_hints": [
            ("-ehso / -αso", "Many he/it verb forms end in -ehso or -αso (not always 'man')"),
        ],
    },
]


def entry_matches(entry: dict, cat: dict) -> tuple[bool, list[str]]:
    """Return whether entry matches category and which rules fired."""
    reasons: list[str] = []
    en = (entry.get("english") or "").lower()
    hw = entry.get("headword", "")

    for pat in cat.get("english_patterns", []):
        if re.search(pat, en, re.I):
            reasons.append(f"English matches: {pat}")
            return True, reasons

    for pat in cat.get("headword_patterns", []):
        if re.search(pat, hw, re.I) or re.search(pat, fold_ascii(hw), re.I):
            reasons.append(f"Headword pattern: {pat}")
            return True, reasons

    return False, reasons


def find_morph_notes(headword: str, cat: dict) -> list[dict]:
    """Find which morphological hints apply to this headword."""
    hw_fold = fold_ascii(headword)
    notes = []
    for fragment, explanation in cat.get("morph_hints", []):
        frag_fold = fold_ascii(fragment.replace("-", ""))
        if frag_fold and frag_fold in hw_fold:
            notes.append({"fragment": fragment, "note": explanation})
        elif fragment in headword:
            notes.append({"fragment": fragment, "note": explanation})
    return notes


def build_index(entries: dict) -> dict:
    by_category: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()

    for entry in entries.values():
        eid = entry["id"]
        for cat in CATEGORIES:
            matched, reasons = entry_matches(entry, cat)
            if not matched:
                continue
            key = (cat["id"], eid)
            if key in seen:
                continue
            seen.add(key)

            main, alt = "", ""
            for a in entry.get("audio", []):
                lp = a.get("local_path", "")
                if a.get("type") == "guide":
                    alt = lp
                else:
                    main = lp

            morph = find_morph_notes(entry.get("headword", ""), cat)
            by_category[cat["id"]].append({
                "entry_id": eid,
                "headword": entry.get("headword", ""),
                "english": entry.get("english", ""),
                "part_of_speech": entry.get("part_of_speech", ""),
                "match_reasons": reasons,
                "morph_notes": morph,
                "audio_main": main,
                "audio_alt": alt,
            })

    for cat_id in by_category:
        by_category[cat_id].sort(key=lambda x: x["headword"].lower())

    return {
        "meta": {
            "categories": len(CATEGORIES),
            "tagged_entries": sum(len(v) for v in by_category.values()),
        },
        "categories": CATEGORIES,
        "by_category": dict(by_category),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine kinship/perspective index for Lab")
    args = parser.parse_args()

    ensure_dirs()
    catalog = load_json(ENTRIES_JSON, {"entries": {}})
    entries = catalog.get("entries", {})
    if not entries:
        print("No entries.")
        return 1

    data = build_index(entries)
    save_json(KINSHIP_INDEX_JSON, data)
    print(f"Kinship index: {data['meta']['categories']} categories, {data['meta']['tagged_entries']} tagged hits")
    for cat in CATEGORIES:
        n = len(data["by_category"].get(cat["id"], []))
        if n:
            print(f"  {cat['label']}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())