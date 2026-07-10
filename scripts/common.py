"""Shared utilities for the Penobscot Dictionary archive."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

BASE_URL = "https://penobscot-dictionary.appspot.com"
# Public URL for Open Graph / Discord embeds (override with PENOBSCOT_SITE_URL).
SITE_MIRROR_URL = os.environ.get(
    "PENOBSCOT_SITE_URL", "https://penobscot.brokengameplay.com"
).rstrip("/")
AUDIO_BUCKET = "https://storage.googleapis.com/penobscot_dictionary_audiofile_storage"

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ENTRIES_DIR = ROOT / "entries"
AUDIO_DIR = ROOT / "audio"
SITE_DIR = ROOT / "site"

ENTRIES_JSON = DATA_DIR / "entries.json"
CRAWL_STATE_JSON = DATA_DIR / "crawl_state.json"
LETTERS_JSON = DATA_DIR / "letters.json"
AUDIO_LOG_JSON = DATA_DIR / "audio_log.json"
LAB_DATA_DIR = DATA_DIR / "lab"
AFFIX_PATTERNS_JSON = LAB_DATA_DIR / "affix_patterns.json"
GUESSER_FORMS_JSON = LAB_DATA_DIR / "guesser_forms.json"
BASE_WORDS_JSON = LAB_DATA_DIR / "base_words.json"
SENTENCE_EXAMPLES_JSON = LAB_DATA_DIR / "sentence_examples.json"
ENGLISH_INDEX_JSON = LAB_DATA_DIR / "english_index.json"
KINSHIP_INDEX_JSON = LAB_DATA_DIR / "kinship_index.json"
SEMANTIC_TAGS_JSON = LAB_DATA_DIR / "semantic_tags.json"
LISTEN3_DECKS_JSON = LAB_DATA_DIR / "listen3_decks.json"

_FOLD_TRANSLATE = str.maketrans({
    "č": "c", "Č": "c",
    "ə": "e", "Ə": "e",
    "α": "a", "Α": "a",
    "ʷ": "w",
    "́": "", "̀": "", "ˊ": "", "ˋ": "",
    "‑": "-",
    "→": "",
})


def ensure_dirs() -> None:
    for d in (DATA_DIR, ENTRIES_DIR, AUDIO_DIR, SITE_DIR, LAB_DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default=None):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else {}


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def slugify(headword: str, entry_id: str) -> str:
    """Create a filesystem-safe slug from headword + short id."""
    base = headword.strip()
    base = re.sub(r"[|]", "", base)
    base = re.sub(r"[^\w\-]", "-", base, flags=re.UNICODE)
    base = re.sub(r"-+", "-", base).strip("-")
    if not base:
        base = "entry"
    suffix = entry_id[-8:]
    return f"{base}-{suffix}"


def normalize_search(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower().strip()


def fold_ascii(text: str) -> str:
    """Fold Penobscot orthography to plain ASCII for normal-keyboard matching."""
    if not text:
        return ""
    folded = unicodedata.normalize("NFC", text.strip()).translate(_FOLD_TRANSLATE)
    folded = unicodedata.normalize("NFD", folded)
    folded = "".join(c for c in folded if unicodedata.category(c) != "Mn")
    folded = unicodedata.normalize("NFC", folded).lower()
    return re.sub(r"[^a-z0-9\-]+", "", folded)


def entry_url(entry_id: str) -> str:
    return f"{BASE_URL}/entry/{entry_id}/"