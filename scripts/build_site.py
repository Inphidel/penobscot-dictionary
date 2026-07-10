#!/usr/bin/env python3
"""Build a searchable static local website from entries.json."""

from __future__ import annotations

import html
import json
import textwrap
import unicodedata
from pathlib import Path
from urllib.parse import quote

from pos_glossary import build_tooltips_js, pos_html
from common import (
    AFFIX_PATTERNS_JSON,
    AUDIO_DIR,
    BASE_WORDS_JSON,
    ENGLISH_INDEX_JSON,
    ENTRIES_JSON,
    KINSHIP_INDEX_JSON,
    GUESSER_FORMS_JSON,
    LISTEN3_DECKS_JSON,
    SEMANTIC_TAGS_JSON,
    SENTENCE_EXAMPLES_JSON,
    SITE_DIR,
    SITE_MIRROR_URL,
    ensure_dirs,
    fold_ascii,
    load_json,
    save_json,
)
import re

LUNR_LOCAL = "assets/lunr.min.js"

BROWSE_LETTERS = [
    "a", "α", "č", "čč", "e", "ə", "h", "hʷ", "i", "k", "kk", "kkʷ", "kʷ",
    "l", "m", "n", "o", "p", "pp", "s", "ss", "t", "tt", "w", "y", "root",
]


def esc(text: str) -> str:
    return html.escape(text or "")


def audio_paths(entry: dict, rel_prefix: str = "") -> tuple[str, str]:
    """Return (primary, alternate) recording URLs. Alternate is a second speaker, not a different word."""
    primary = alternate = ""
    for a in entry.get("audio", []):
        local = a.get("local_path", "")
        if not local:
            continue
        path = f"{rel_prefix}{local}" if rel_prefix else local
        if a.get("type") == "guide":
            alternate = path
        else:
            primary = path
    return primary, alternate


def sorted_recordings(entry: dict, rel_prefix: str = "") -> list[dict]:
    """All recordings in stable order: primary first, then alternate speaker."""
    items = []
    for a in entry.get("audio", []):
        local = a.get("local_path", "")
        if not local:
            continue
        path = f"{rel_prefix}{local}" if rel_prefix else local
        items.append({
            "url": path,
            "kind": a.get("type", "main"),
            "basename": local.rsplit("/", 1)[-1],
        })
    items.sort(key=lambda x: (1 if x["kind"] == "guide" else 0))
    return items


def safe_download_name(headword: str, index: int, total: int) -> str:
    import re
    base = re.sub(r'[<>:"/\\|?*\n\r]', "", headword).strip() or "penobscot-word"
    if total > 1 and index > 0:
        return f"{base}-{index + 1}.mp3"
    return f"{base}.mp3"


def badge_archive() -> str:
    return '<span class="badge badge-archive">Penobscot Dictionary — official archive</span>'


def badge_lab() -> str:
    return '<span class="badge badge-lab">Experimental Lab — verify with audio &amp; speakers</span>'


def truncate_og(text: str, max_len: int = 280) -> str:
    text = " ".join((text or "").split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def entry_og_description(entry: dict) -> str:
    parts: list[str] = []
    english = (entry.get("english") or "").strip().rstrip(";")
    if english:
        parts.append(english)
    pos_parts = [p for p in [entry.get("part_of_speech"), entry.get("sub_part_of_speech")] if p]
    if pos_parts:
        parts.append(" · ".join(pos_parts))
    if entry.get("audio"):
        parts.append("Audio available")
    return truncate_og(" · ".join(parts) if parts else "Penobscot Dictionary entry")


def build_og_meta(
    *,
    title: str,
    description: str,
    url: str,
    og_type: str = "website",
    image_url: str | None = None,
) -> str:
    desc = truncate_og(description)
    tags = [
        f'<meta name="description" content="{esc(desc)}">',
        f'<link rel="canonical" href="{esc(url)}">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(desc)}">',
        f'<meta property="og:url" content="{esc(url)}">',
        f'<meta property="og:site_name" content="Penobscot Dictionary">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:locale" content="en_US">',
        f'<meta name="twitter:card" content="summary">',
        f'<meta name="twitter:title" content="{esc(title)}">',
        f'<meta name="twitter:description" content="{esc(desc)}">',
    ]
    if image_url:
        tags.extend([
            f'<meta property="og:image" content="{esc(image_url)}">',
            f'<meta name="twitter:image" content="{esc(image_url)}">',
        ])
    return "\n  ".join(tags)


def page_shell(
    title: str,
    body: str,
    active: str = "",
    asset_prefix: str = "",
    extra_scripts: str = "",
    body_class: str = "",
    og_meta: str = "",
) -> str:
    ap = asset_prefix
    nav_home = f"{ap}index.html"
    nav_browse = f"{ap}browse.html"
    nav_lab = f"{ap}lab/index.html"
    nav_about = f"{ap}about.html"
    bc = f' class="{body_class}"' if body_class else ""
    nav = f"""
    <nav class="nav">
      <a href="{nav_home}" class="brand">Penobscot Dictionary</a>
      <a href="{nav_home}" class="{'active' if active == 'home' else ''}">Search</a>
      <a href="{nav_browse}" class="{'active' if active == 'browse' else ''}">Browse</a>
      <a href="{nav_lab}" class="{'active' if active == 'lab' else ''}">Lab</a>
      <a href="{nav_about}" class="{'active' if active == 'about' else ''}">About</a>
    </nav>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} | Penobscot Dictionary</title>
  {f"{og_meta}\n  " if og_meta else ""}<link rel="stylesheet" href="{ap}assets/style.css">
</head>
<body{bc}>
  {nav}
  <main class="container">
    {body}
  </main>
  <footer class="footer">
    <p><strong>Archive</strong> — data from the <a href="https://penobscot-dictionary.appspot.com/entry/" target="_blank" rel="noopener">Penobscot Dictionary</a>
    (Penobscot Indian Nation, University of Maine, American Philosophical Society). Based on the manuscript of Frank T. Siebert.</p>
    <p><strong>Lab tools</strong> are local experiments — pattern guesses only, not official dictionary entries.</p>
  </footer>
  <script src="{ap}assets/pos-tooltips.js"></script>
  {extra_scripts}
</body>
</html>"""


def audio_html(entry: dict, rel_prefix: str = "") -> str:
    recordings = sorted_recordings(entry, rel_prefix)
    if not recordings:
        return '<p class="muted">No audio recording for this entry.</p>'
    hw = entry.get("headword", "")
    total = len(recordings)
    blocks = []
    for i, rec in enumerate(recordings):
        label = f"Recording {i + 1}" if total > 1 else "Audio"
        dl_name = safe_download_name(hw, i, total)
        blocks.append(f"""
        <div class="drill-player" data-audio="{esc(rec['url'])}">
          <span class="audio-label">{esc(label)}</span>
          <div class="drill-controls">
            <button type="button" class="btn-play btn-play-lg" title="Play — tap again instantly to repeat">&#9654; Play</button>
            <button type="button" class="btn-loop" aria-pressed="false" title="Loop — hear it over and over">&#8635; Loop</button>
            <button type="button" class="btn-download" data-audio="{esc(rec['url'])}" data-filename="{esc(dl_name)}" title="Save sound file">&#8681; Save</button>
          </div>
        </div>""")
    return "\n".join(blocks)


SYNONYM_LABELS = {"syn:", "syn.", "syn"}
CONJUGATION_HINTS = ("i...", "we...", "you...", "he...", "she...", "they...", "that it...")


def norm_form(text: str) -> str:
    return unicodedata.normalize("NFC", (text or "").strip())


def lookup_key(form: str) -> str:
    return norm_form(form).rstrip(".,;:!?|-").lower()


def build_headword_index(entries: dict) -> dict[str, str]:
    index: dict[str, str] = {}
    for eid, entry in entries.items():
        hw = entry.get("headword", "")
        if not hw:
            continue
        for variant in (hw, hw.rstrip(".,;|-"), hw.lstrip("-")):
            key = lookup_key(variant)
            if key and key not in index:
                index[key] = eid
    return index


def resolve_entry(form: str, hw_index: dict[str, str], entries: dict) -> dict | None:
    eid = hw_index.get(lookup_key(form))
    return entries.get(eid) if eid else None


def example_kind(ex: dict, headword: str) -> str:
    pos = (ex.get("part_of_speech") or "").strip().lower()
    en = (ex.get("english") or "").strip().lower()
    form = norm_form(ex.get("penobscot", ""))
    if pos in SYNONYM_LABELS:
        return "synonym"
    if en in ("for", "syn.", "syn:"):
        return "synonym"
    if pos in ("pl.", "dl."):
        return "plural"
    if pos == "loc.":
        return "locative"
    if pos in ("c. conj.", "conj."):
        return "conjunct"
    if any(en.startswith(h) for h in CONJUGATION_HINTS):
        return "conjugated"
    if form and form != norm_form(headword):
        return "variant"
    return "note"


def example_label(ex: dict) -> str:
    pos = (ex.get("part_of_speech") or "").strip()
    en = (ex.get("english") or "").strip()
    if pos and en:
        return f"{pos} — {en}"
    return pos or en or "example form"


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    m, n = len(a), len(b)
    if not m:
        return n
    if not n:
        return m
    prev = list(range(n + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[n]


def find_neighbors(entry: dict, by_letter: dict[str, list], limit: int = 6) -> list[tuple[dict, str]]:
    hw = norm_form(entry.get("headword", ""))
    hw_low = hw.lower()
    if len(hw) < 3:
        return []

    seen = {entry["id"]}
    hits: list[tuple[int, dict, str]] = []
    pool: list[dict] = []
    for letter in entry.get("browse_letters", []):
        pool.extend(by_letter.get(letter, []))

    for other in pool:
        oid = other["id"]
        if oid in seen:
            continue
        ohw = norm_form(other.get("headword", ""))
        ohw_low = ohw.lower()
        reason = ""
        score = 99
        if len(ohw) >= 3 and len(hw) >= 3:
            if len(hw) >= 4 and len(ohw) >= 4 and (hw_low in ohw_low or ohw_low in hw_low):
                reason = "shared form"
                score = 1
            else:
                common = 0
                for a, b in zip(hw_low, ohw_low):
                    if a != b:
                        break
                    common += 1
                if common >= 3:
                    reason = "shared opening"
                    score = 2
                else:
                    dist = levenshtein(hw_low, ohw_low)
                    if dist <= 2 and len(hw) >= 5:
                        reason = "similar spelling"
                        score = 3 + dist
        if reason:
            hits.append((score, other, reason))
            seen.add(oid)

    hits.sort(key=lambda item: (item[0], item[1].get("headword", "").lower()))
    return [(item[1], item[2]) for item in hits[:limit]]


# Prefer lemma/meta over broad themes when ranking meaning-related neighbors.
_SPECIFICITY_RANK = {"lemma": 0, "meta": 1, "theme": 2}


def find_semantic_neighbors(
    entry: dict,
    entries: dict,
    semantic_index: dict | None,
    *,
    exclude_ids: set[str] | None = None,
    limit: int = 6,
) -> list[tuple[dict, str]]:
    """Entries sharing semantic tags from English glosses (Lab experimental)."""
    if not semantic_index:
        return []
    by_entry = semantic_index.get("by_entry") or {}
    by_tag = semantic_index.get("by_tag") or {}
    tag_meta = {t["id"]: t for t in (semantic_index.get("tags") or [])}

    my_hits = by_entry.get(entry["id"]) or []
    # Prefer high/medium confidence tags; drop pure broad noise if we have lemmas
    usable = [h for h in my_hits if h.get("confidence") in ("high", "medium", "low")]
    if not usable:
        return []

    lemmas = [h for h in usable if h.get("specificity") == "lemma"]
    meta_tags = [h for h in usable if h.get("specificity") == "meta" and h.get("tag_id") != "species"]
    themes = [h for h in usable if h.get("specificity") == "theme"]
    # species alone is too broad; use with animal/plant lemmas
    primary = lemmas or meta_tags or themes
    if not primary:
        return []

    seen = {entry["id"]}
    if exclude_ids:
        seen |= exclude_ids

    my_pos = (entry.get("part_of_speech") or "").strip()
    scored: dict[str, tuple[int, str, dict]] = {}

    for hit in sorted(primary, key=lambda h: _SPECIFICITY_RANK.get(h.get("specificity"), 9)):
        tid = hit["tag_id"]
        spec = hit.get("specificity") or "theme"
        label = hit.get("label") or tag_meta.get(tid, {}).get("label") or tid
        # Skip ultra-broad themes when we already have lemmas (avoid "water" flooding)
        if lemmas and spec == "theme" and tid in ("water", "people", "food", "plant", "tree"):
            continue
        weight = {"lemma": 100, "meta": 40, "theme": 20}.get(spec, 10)
        for card in by_tag.get(tid) or []:
            oid = card.get("entry_id")
            if not oid or oid in seen:
                continue
            other = entries.get(oid)
            if not other:
                continue
            conf = card.get("confidence") or "medium"
            conf_bonus = {"high": 5, "medium": 2, "low": 0}.get(conf, 0)
            pos_bonus = 3 if my_pos and (other.get("part_of_speech") or "") == my_pos else 0
            score = weight + conf_bonus + pos_bonus
            # Prefer same group specificity stack: more shared tags later
            note = f"same theme: {label}"
            if spec == "lemma":
                note = f"related meaning: {label}"
            elif spec == "meta":
                note = f"same marker: {label}"
            prev = scored.get(oid)
            if not prev or score > prev[0]:
                scored[oid] = (score, note, other)

    # Boost entries that share multiple of our tags
    my_tag_ids = {h["tag_id"] for h in usable}
    for oid, (score, note, other) in list(scored.items()):
        other_tags = {h["tag_id"] for h in (by_entry.get(oid) or [])}
        shared = len(my_tag_ids & other_tags)
        if shared > 1:
            scored[oid] = (score + shared * 8, note + f" (+{shared - 1} more)", other)

    ranked = sorted(scored.values(), key=lambda x: (-x[0], x[2].get("headword", "").lower()))
    return [(other, note) for _score, note, other in ranked[:limit]]


def lab_url(form: str, prefix: str = "../") -> str:
    return f"{prefix}lab/index.html?q={quote(norm_form(form), safe='')}"


def mini_audio_buttons(entry: dict, rel_prefix: str = "../") -> str:
    recs = sorted_recordings(entry, rel_prefix)
    if not recs:
        return ""
    btns = ""
    for i, rec in enumerate(recs[:2]):
        hint = f" recording {i + 1}" if len(recs) > 1 else ""
        btns += (
            f'<button type="button" class="btn-play btn-play-sm" data-audio="{esc(rec["url"])}" '
            f'title="Play{hint}">&#9654;</button>'
        )
    return f'<span class="related-actions">{btns}</span>'


def related_entry_row(target: dict, note: str, rel_prefix: str = "../") -> str:
    eid = target["id"]
    hw = target.get("headword", "")
    en = (target.get("english") or "")[:100]
    return f"""<li class="related-item">
      <a class="related-hw" href="{rel_prefix}entry/{eid}.html">{esc(hw)}</a>
      <span class="related-note">{esc(note)}</span>
      <span class="related-en">{esc(en)}</span>
      {mini_audio_buttons(target, rel_prefix)}
    </li>"""


def build_related_panel(
    entry: dict,
    *,
    hw_index: dict[str, str],
    entries: dict,
    by_letter: dict[str, list],
    semantic_index: dict | None = None,
) -> str:
    hw = entry.get("headword", "")
    sections: list[str] = []
    listed_ids: set[str] = set()

    example_items: list[str] = []
    synonym_items: list[str] = []
    for ex in entry.get("examples", []):
        form = norm_form(ex.get("penobscot", ""))
        kind = example_kind(ex, hw)
        label = example_label(ex)

        if kind == "synonym" and form:
            target = resolve_entry(form, hw_index, entries)
            if target and target["id"] != entry["id"]:
                listed_ids.add(target["id"])
                synonym_items.append(related_entry_row(target, "listed as synonym", "../"))
            else:
                synonym_items.append(f"""<li class="related-item">
                  <span class="related-hw">{esc(form)}</span>
                  <span class="related-note">synonym — not matched to another entry</span>
                  <a class="btn-lab-link" href="{lab_url(form)}">Break down &#8594;</a>
                </li>""")
            continue

        if not form or form == norm_form(hw):
            if label and label != "example form":
                example_items.append(f"""<li class="related-item related-meta">
                  <span class="related-note">{esc(label)}</span>
                </li>""")
            continue

        kind_label = {
            "plural": "plural",
            "locative": "locative",
            "conjunct": "conjunct",
            "conjugated": "conjugated form",
            "variant": "variant",
            "note": "related form",
        }.get(kind, "related form")
        example_items.append(f"""<li class="related-item">
          <span class="related-hw">{esc(form)}</span>
          <span class="related-note">{esc(kind_label)}</span>
          <span class="related-en">{esc(label)}</span>
          <a class="btn-lab-link" href="{lab_url(form)}">Break down &#8594;</a>
        </li>""")

    if example_items:
        sections.append(f"""
      <div class="related-group">
        <h3>Dictionary example forms</h3>
        <p class="related-hint">Conjugations, plurals, and variants from this entry's archive record.</p>
        <ul class="related-list">{"".join(example_items)}</ul>
      </div>""")

    if synonym_items:
        sections.append(f"""
      <div class="related-group">
        <h3>Synonyms &amp; alternates</h3>
        <ul class="related-list">{"".join(synonym_items)}</ul>
      </div>""")

    neighbors = find_neighbors(entry, by_letter)
    if neighbors:
        for other, _reason in neighbors:
            listed_ids.add(other["id"])
        neighbor_items = "".join(
            related_entry_row(other, reason, "../") for other, reason in neighbors
        )
        sections.append(f"""
      <div class="related-group">
        <h3>Similar headwords nearby</h3>
        <p class="related-hint">Same browse section — shared pieces or close spelling.</p>
        <ul class="related-list">{neighbor_items}</ul>
      </div>""")

    meaning_neighbors = find_semantic_neighbors(
        entry, entries, semantic_index, exclude_ids=listed_ids, limit=6
    )
    if meaning_neighbors:
        # Theme chips for this entry
        my_tags = (semantic_index or {}).get("by_entry", {}).get(entry["id"]) or []
        chips = ""
        if my_tags:
            chip_html = []
            seen_t = set()
            for h in my_tags:
                tid = h["tag_id"]
                if tid in seen_t or tid == "species":
                    continue
                seen_t.add(tid)
                chip_html.append(
                    f'<a class="theme-chip" href="../lab/index.html?theme={quote(tid, safe="")}">'
                    f'{esc(h.get("label") or tid)}</a>'
                )
                if len(chip_html) >= 8:
                    break
            if chip_html:
                chips = f'<p class="theme-chips">Themes: {" ".join(chip_html)}</p>'
        meaning_items = "".join(
            related_entry_row(other, reason, "../") for other, reason in meaning_neighbors
        )
        sections.append(f"""
      <div class="related-group related-meaning">
        <h3>Related by meaning <span class="badge badge-lab">Lab</span></h3>
        <p class="related-hint">Shared themes mined from English glosses (animals, objects, body, nature, …) — not official categories. Verify with audio.</p>
        {chips}
        <ul class="related-list">{meaning_items}</ul>
      </div>""")

    if not sections:
        sections.append(f"""
      <p class="related-hint">No extra forms in the archive for this entry. Try analyzing the headword or search English above.</p>
      <p><a class="btn-lab-link" href="{lab_url(hw)}">Break down {esc(hw)} in Lab &#8594;</a></p>""")
    else:
        sections.append(f"""
      <p class="related-footer"><a class="btn-lab-link" href="{lab_url(hw)}">Break down {esc(hw)} in Lab &#8594;</a></p>""")

    return f"""
    <section class="lab-panel entry-lab-panel">
      <p class="badge-row">{badge_lab()}</p>
      <h2>Related forms</h2>
      <p class="lab-hint">Pulled from this entry's examples, nearby headwords, and English-theme tags — verify with audio and speakers.</p>
      {"".join(sections)}
    </section>"""


def build_entry_page(
    entry: dict,
    *,
    hw_index: dict[str, str],
    entries: dict,
    by_letter: dict[str, list],
    semantic_index: dict | None = None,
) -> str:
    hw = entry.get("headword", "")
    pos_parts = [p for p in [entry.get("part_of_speech"), entry.get("sub_part_of_speech")] if p]
    pos = " · ".join(pos_parts)
    pos_block = f'<p class="pos">{pos_html(pos)}</p>' if pos else ""
    examples_rows = ""
    for ex in entry.get("examples", []):
        ex_pos = pos_html(ex.get("part_of_speech") or "")
        examples_rows += f"<tr><td>{esc(ex.get('penobscot'))}</td><td>{esc(ex.get('english'))}</td><td>{ex_pos}</td></tr>"

    examples_section = ""
    if examples_rows:
        examples_section = f"""
        <section class="examples">
          <h2>Examples</h2>
          <table>
            <thead><tr><th>Penobscot</th><th>English</th><th>{pos_html("Part of Speech")}</th></tr></thead>
            <tbody>{examples_rows}</tbody>
          </table>
        </section>"""

    letters = entry.get("browse_letters", [])
    letter_links = " ".join(
        f'<a href="letter/{esc(l)}.html">{esc(l)}</a>' for l in letters[:3]
    )

    body = f"""
    <article class="entry archive-panel">
      <p class="badge-row">{badge_archive()}</p>
      <header class="entry-header">
        <h1 class="headword">{esc(hw)}</h1>
        {pos_block}
        {f'<p class="browse-in">In: {letter_links}</p>' if letter_links else ''}
      </header>
      <section class="definition">
        <h2>English</h2>
        <p class="english">{esc(entry.get('english', ''))}</p>
      </section>
      <section class="audio-section">
        <h2>Audio</h2>
        {audio_html(entry, rel_prefix="../")}
      </section>
      {examples_section}
      <p class="source-link"><a href="{esc(entry.get('source_url', ''))}" target="_blank" rel="noopener">View on penobscot-dictionary.appspot.com</a></p>
    </article>
    {build_related_panel(entry, hw_index=hw_index, entries=entries, by_letter=by_letter, semantic_index=semantic_index)}"""
    scripts = """
    <script src="../assets/audio-player.js"></script>
    <script>PenobscotAudio.initPage();</script>"""
    eid = entry.get("id", "")
    og_meta = build_og_meta(
        title=hw,
        description=entry_og_description(entry),
        url=f"{SITE_MIRROR_URL}/entry/{eid}.html",
        og_type="article",
    )
    return page_shell(
        hw, body, active="browse", asset_prefix="../", extra_scripts=scripts, og_meta=og_meta
    )


def build_letter_page(letter: str, letter_entries: list[dict]) -> str:
    rows = ""
    for e in sorted(letter_entries, key=lambda x: x.get("headword", "").lower()):
        recs = sorted_recordings(e, rel_prefix="../")
        play_btns = ""
        for i, rec in enumerate(recs):
            hint = f" recording {i + 1}" if len(recs) > 1 else ""
            play_btns += f"""<button type="button" class="btn-play btn-play-sm" data-audio="{esc(rec['url'])}" title="Play{hint} — tap again to repeat">&#9654;</button>"""
        rows += f"""<tr class="word-row" data-href="../entry/{e['id']}.html">
          <td class="hw"><a href="../entry/{e['id']}.html">{esc(e.get('headword'))}</a></td>
          <td class="play-cell"><div class="play-group">{play_btns}</div></td>
          <td class="en">{esc((e.get('english') or '')[:120])}</td>
          <td class="pos">{pos_html(e.get('part_of_speech', ''))}</td>
        </tr>"""

    body = f"""
    <h1>Browse: {esc(letter)}</h1>
    <p class="stats">{len(letter_entries)} entries — tap &#9654; to hear; tap again to repeat</p>
    <div class="letter-search">
      <input type="search" id="filter" placeholder="Filter this list..." autocomplete="off">
    </div>
    <table class="word-list" id="word-table">
      <thead><tr><th>Penobscot</th><th></th><th>English</th><th>{pos_html("POS")}</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <script src="../assets/audio-player.js"></script>
    <script>
      PenobscotAudio.initPage();
      document.getElementById('filter').addEventListener('input', function() {{
        const q = this.value.toLowerCase();
        document.querySelectorAll('#word-table .word-row').forEach(row => {{
          row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
        }});
      }});
      document.querySelectorAll('#word-table .word-row').forEach(row => {{
        row.addEventListener('click', e => {{
          if (e.target.closest('.btn-play')) return;
          const href = row.dataset.href;
          if (href) location.href = href;
        }});
      }});
    </script>"""
    return page_shell(f"Browse {letter}", body, active="browse", asset_prefix="../")


def build_index(entries: dict, meta: dict) -> str:
    total = meta.get("total_entries", len(entries))
    with_audio = meta.get("entries_with_audio", 0)

    body = f"""
    <header class="hero">
      <p class="badge-row">{badge_archive()}</p>
      <h1>Penobscot Dictionary</h1>
      <p class="subtitle">Local archive for language learning — {total:,} words, {with_audio:,} with audio</p>
    </header>
    <section class="search-section">
      <label for="q" class="sr-only">Search dictionary</label>
      <input type="search" id="q" placeholder="Search Penobscot or English..." autocomplete="off" autofocus>
      <div class="search-toolbar">
        <p class="search-hint">Search headwords, definitions, and examples. Type a piece of a Penobscot word (e.g. <em>lihoso</em>) for partial matches below. Tap &#9654; to hear — tap again instantly to repeat.</p>
        <div class="search-toolbar-actions">
          <label class="loop-global" title="When on, audio repeats until you stop it">
            <input type="checkbox" id="loop-global"> Loop while studying
          </label>
          <a href="lab/index.html" id="lab-link" class="btn-lab-link" title="Break down a Penobscot form">Break down in Lab &#8594;</a>
        </div>
      </div>
      <div id="results" class="results"></div>
      <p id="status" class="status"></p>
      <div id="partial-results" class="partial-results"></div>
    </section>
    <section class="quick-browse">
      <h2>Browse by sound</h2>
      <div class="letter-grid" id="letter-grid"></div>
    </section>
    <script src="{LUNR_LOCAL}"></script>
    <script src="assets/audio-player.js"></script>
    <script src="assets/search.js"></script>"""
    return page_shell("Search", body, active="home")


def build_browse_page(by_letter: dict) -> str:
    cards = ""
    for letter in BROWSE_LETTERS:
        count = len(by_letter.get(letter, []))
        if count == 0:
            continue
        cards += f'<a class="letter-card" href="letter/{esc(letter)}.html"><span class="letter">{esc(letter)}</span><span class="count">{count}</span></a>'

    for letter, items in sorted(by_letter.items()):
        if letter in BROWSE_LETTERS:
            continue
        cards += f'<a class="letter-card" href="letter/{esc(letter)}.html"><span class="letter">{esc(letter)}</span><span class="count">{len(items)}</span></a>'

    body = f"""
    <p class="badge-row">{badge_archive()}</p>
    <h1>Browse the Dictionary</h1>
    <p class="stats">Select a starting sound or letter grouping.</p>
    <div class="letter-grid">{cards}</div>"""
    return page_shell("Browse", body, active="browse")


def build_about_page(meta: dict) -> str:
    total = meta.get("total_entries", 0)
    with_audio = meta.get("entries_with_audio", 0)
    body = f"""
    <header class="hero">
      <h1>About this site</h1>
      <p class="subtitle">Local study archive — not an official Penobscot Nation publication</p>
    </header>

    <section class="archive-panel about-section">
      <h2>Archive (official text)</h2>
      <p class="badge-row">{badge_archive()}</p>
      <p>The <strong>Search</strong> and <strong>Browse</strong> sections are a local copy of the
      <a href="https://penobscot-dictionary.appspot.com/entry/" target="_blank" rel="noopener">Penobscot Dictionary</a>
      online — {total:,} entries, {with_audio:,} with audio recordings from the Penobscot Indian Nation,
      University of Maine, and American Philosophical Society (Frank T. Siebert manuscript).</p>
      <p>Headwords, definitions, and examples match the official archive. Each entry links back to the official site.</p>
      <p><strong>Audio in this mirror</strong> has been loudness-normalized (~-15 LUFS) so recordings are easier to hear
      on phones and laptops. That is a study convenience only — not a change to the linguistic content.
      Hover part-of-speech labels (AI, INAN, Initial, …) for short explanations.</p>
    </section>

    <section class="lab-panel about-section">
      <h2>Lab (experimental)</h2>
      <p class="badge-row">{badge_lab()}</p>
      <p>The <strong>Lab</strong> is for learners without special keyboard fluency. Everything it shows is labeled
      <strong>system detection</strong> — pattern guesses, not official Penobscot.</p>
      <ul>
        <li><strong>English → possible Penobscot</strong> — type normal English; the Lab matches dictionary definitions and suggests forms (with reasoning).</li>
        <li><strong>Penobscot → possible meaning</strong> — type a form you heard (plain letters OK); shows meaning first, then prefix/stem guesses.</li>
        <li><strong>Themes</strong> — browse words tagged from English glosses (animals, body, objects, nature, food, …). Tags boost related Lab matches.</li>
        <li><strong>Listen-3</strong> — hear a recording, pick the matching English from three choices; choose themes to brush up on.</li>
        <li><strong>Perspective &amp; kinship</strong> — browse by mother, father, child, my/his/her, older/younger, feminine endings, etc., with pattern hints.</li>
      </ul>
      <p>Elsewhere: entry pages have an amber <strong>Related forms</strong> panel (including <strong>Related by meaning</strong> from theme tags);
      <strong>Search</strong> shows amber <strong>partial matches</strong> when you type a fragment of a word.</p>
      <p>Always verify with audio and fluent speakers before trusting a Lab result.</p>
      <p><a href="lab/index.html" class="btn-lab-cta">Open Lab</a></p>
    </section>

    <section class="about-section">
      <h2>How to run locally</h2>
      <p><strong>Windows:</strong> run <code>restart.bat</code> in the project folder, then open http://localhost:8080</p>
      <pre class="code-block">python -m http.server 8080 --directory site
# open http://localhost:8080</pre>
      <p>Audio must be served over http/https — opening HTML files directly will not play recordings.</p>
    </section>

    <section class="about-section">
      <h2>For maintainers — updating the mirror</h2>
      <p>This distribution ships with <strong>normalized audio already applied</strong>. Most users only need
      <code>git pull</code> (or copy the <code>site/</code> folder) and serve it.</p>
      <p>The official online dictionary appears stable and may not receive frequent updates. Re-crawling is
      <em>optional</em> and mainly for operators who want to check for new entries.</p>
      <p><strong>Important:</strong> re-downloading from the official site replaces MP3s with the original quiet
      recordings. If you run a refresh, also re-apply loudness normalization:</p>
      <pre class="code-block">pip install -r requirements.txt
python scripts/spider.py          # optional — re-crawl official site
python scripts/finish.py          # rebuild data + site (overwrites quiet audio)
python scripts/normalize_audio.py # restore comfortable listening level
python scripts/build_site.py      # if you changed scripts only</pre>
      <p>Rebuild Lab pattern indexes only (no crawl):</p>
      <pre class="code-block">python scripts/mine_affixes.py
python scripts/mine_semantic_tags.py
python scripts/mine_kinship.py
python scripts/build_site.py</pre>
      <p>Originals before normalization are kept in <code>audio_original/</code> (local backup, not required for serving).</p>
    </section>"""
    return page_shell("About", body, active="about")


def short_english_for_game(en: str, max_len: int = 110) -> str:
    """First sense / clause for multiple-choice labels."""
    text = (en or "").strip()
    if not text:
        return ""
    if re.match(r"^\s*1\)", text):
        text = re.split(r"\s*2\)\s*", text, maxsplit=1)[0]
        text = re.sub(r"^\s*1\)\s*", "", text)
    if ";" in text:
        text = text.split(";", 1)[0]
    text = text.strip(" ,;")
    # strip sciname markup noise for choices
    text = re.sub(r"⟨/?sciname⟩", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        cut = text[: max_len - 1]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        text = cut + "…"
    return text


def build_listen3_decks(entries: dict, semantic_index: dict) -> dict:
    """Slim decks: theme tag → playable cards with audio."""
    by_tag = semantic_index.get("by_tag") or {}
    tag_meta = {t["id"]: t for t in (semantic_index.get("tags") or [])}
    groups = semantic_index.get("groups") or []
    decks: dict[str, list] = {}
    tag_list: list[dict] = []

    for tid, cards in by_tag.items():
        playable = []
        seen: set[str] = set()
        for card in cards:
            eid = card.get("entry_id")
            if not eid or eid in seen:
                continue
            entry = entries.get(eid) or {}
            audio = card.get("audio_main") or ""
            if not audio:
                for a in entry.get("audio") or []:
                    if a.get("type") != "guide" and a.get("local_path"):
                        audio = a["local_path"]
                        break
            if not audio:
                continue
            en = card.get("english") or entry.get("english") or ""
            short = short_english_for_game(en)
            if len(short) < 3:
                continue
            seen.add(eid)
            alt = card.get("audio_alt") or ""
            playable.append({
                "entry_id": eid,
                "headword": card.get("headword") or entry.get("headword") or "",
                "english": en,
                "english_short": short,
                "audio": audio,
                "audio_alt": alt,
            })
        if len(playable) < 3:
            continue
        playable.sort(key=lambda x: (x.get("headword") or "").lower())
        decks[tid] = playable
        meta = tag_meta.get(tid) or {}
        tag_list.append({
            "id": tid,
            "label": meta.get("label") or tid,
            "group": meta.get("group") or "other",
            "description": meta.get("description") or "",
            "count": len(playable),
        })

    tag_list.sort(key=lambda t: (-t["count"], t["label"]))
    total = len({c["entry_id"] for items in decks.values() for c in items})
    return {
        "meta": {
            "min_deck": 3,
            "playable_tags": len(tag_list),
            "playable_entries": total,
            "source": "semantic_tags + entries audio",
        },
        "groups": groups,
        "tags": tag_list,
        "decks": decks,
    }


def build_listen3_page() -> str:
    body = f"""
    <header class="hero lab-hero">
      <p class="badge-row">{badge_lab()}</p>
      <h1>Listen-3</h1>
      <p class="subtitle">Hear a recording — choose the matching English (1 of 3)</p>
    </header>

    <section id="listen3-setup" class="lab-panel listen3-panel">
      <p class="lab-hint">Pick one or more <strong>themes</strong> to brush up on. Only words with audio are included.
      Wrong answers usually come from the same theme. Study tool — not a fluency test.</p>
      <div class="listen3-toolbar">
        <label class="listen3-size-label">Round size
          <select id="listen3-size">
            <option value="10" selected>10</option>
            <option value="20">20</option>
            <option value="30">30</option>
            <option value="0">All in deck</option>
          </select>
        </label>
        <button type="button" id="listen3-clear" class="btn-secondary">Clear themes</button>
        <button type="button" id="listen3-start" class="btn-analyze" disabled>Start</button>
      </div>
      <p id="listen3-deck-info" class="muted listen3-deck-info"></p>
      <div id="listen3-tags" class="kinship-cats"></div>
    </section>

    <section id="listen3-play" class="lab-panel listen3-panel" hidden>
      <div class="listen3-status-bar">
        <span id="listen3-progress" class="listen3-progress">1 / 10</span>
        <span id="listen3-score" class="listen3-score">0 correct</span>
      </div>
      <div class="listen3-audio-block">
        <p class="breakdown-label">Listen</p>
        <button type="button" id="listen3-play-btn" class="btn-play listen3-big-play" title="Play recording">&#9654; Play</button>
        <p class="muted listen3-replay-hint">Tap again to replay</p>
      </div>
      <p class="breakdown-label">Which English matches?</p>
      <div id="listen3-choices" class="listen3-choices"></div>
      <div id="listen3-feedback" class="listen3-feedback" hidden></div>
      <button type="button" id="listen3-next" class="btn-analyze listen3-next" hidden>Next</button>
    </section>

    <section id="listen3-done" class="lab-panel listen3-panel" hidden>
      <h2>Session done</h2>
      <div id="listen3-summary"></div>
      <div class="listen3-done-actions">
        <button type="button" id="listen3-again" class="btn-analyze">Play again</button>
        <button type="button" id="listen3-change" class="btn-secondary">Change themes</button>
        <a class="btn-lab-link" href="index.html">Back to Lab &#8594;</a>
      </div>
    </section>

    <section class="archive-panel about-section">
      <p><a href="index.html">Lab tools</a> · <a href="../index.html">Search archive</a></p>
    </section>
    <script src="../assets/audio-player.js"></script>
    <script src="../assets/listen3.js"></script>"""
    return page_shell("Listen-3", body, active="lab", asset_prefix="../", body_class="lab-page")


def build_lab_page() -> str:
    body = f"""
    <header class="hero lab-hero">
      <p class="badge-row">{badge_lab()}</p>
      <h1>Lab</h1>
      <p class="subtitle">Type English for possible Penobscot — or type a form you heard (plain letters OK)</p>
      <p class="lab-game-cta"><a class="btn-lab-cta" href="listen3.html">Play Listen-3 &#8594;</a>
        <span class="muted"> Hear a word, pick the English (by theme)</span></p>
    </header>

    <section class="lab-panel">
      <form id="guesser-form" class="guesser-form">
        <label for="guesser-q">English or Penobscot</label>
        <input type="text" id="guesser-q" placeholder="e.g. I am unable to control myself — or netacelihosi" autocomplete="off" autofocus>
        <button type="submit" class="btn-analyze">Detect</button>
      </form>
      <p id="guesser-mode" class="lab-mode muted"></p>
      <p class="lab-hint">The Lab guesses Penobscot from dictionary words and observed patterns. Results are <strong>not official</strong> — use Search/Browse for archive definitions, and verify with audio.</p>
      <div id="breakdown-results" class="breakdown-results"></div>
      <div id="guesser-status" class="status"></div>
      <h3 id="guesser-subhead" class="lab-subhead">More possible matches</h3>
      <div id="guesser-results" class="guesser-results"></div>
    </section>

    <section class="lab-panel themes-panel">
      <h2>Themes (from English glosses)</h2>
      <p class="muted">Experimental tags mined from dictionary English — animals, body, objects, nature, food, motion, and more.
      Not speaker categories. Use to browse related words; always verify with audio.</p>
      <div id="theme-cats" class="kinship-cats"></div>
      <div id="theme-results" class="kinship-results"></div>
    </section>

    <section class="lab-panel kinship-panel">
      <h2>Perspective &amp; kinship</h2>
      <p class="muted">Browse by relationship, possession (my/his/her), age (older/younger), or word endings. Each entry shows <strong>pattern hints</strong> — guesses about which parts of the word may carry that meaning.</p>
      <div id="kinship-cats" class="kinship-cats"></div>
      <div id="kinship-results" class="kinship-results"></div>
    </section>

    <section class="lab-panel lab-affixes">
      <h2>Common prefix patterns (mined from examples)</h2>
      <p class="muted">Observed in the archive — not a complete grammar.</p>
      <div id="affix-table-wrap"></div>
    </section>

    <section class="archive-panel about-section">
      <h2>Looking for the official definition?</h2>
      <p>Use <a href="../index.html">Search</a> or <a href="../browse.html">Browse</a> — green-tagged archive pages.</p>
    </section>
    <script src="../assets/audio-player.js"></script>
    <script src="../assets/lab-guesser.js"></script>
    <script src="../assets/semantic-tags.js"></script>
    <script src="../assets/kinship.js"></script>"""
    return page_shell("Lab", body, active="lab", asset_prefix="../", body_class="lab-page")


def build_search_index(entries: dict) -> list[dict]:
    docs = []
    for eid, entry in entries.items():
        example_text = " ".join(
            f"{ex.get('penobscot', '')} {ex.get('english', '')}"
            for ex in entry.get("examples", [])
        )
        main_audio, alt_audio = audio_paths(entry)
        docs.append({
            "id": eid,
            "headword": entry.get("headword", ""),
            "english": entry.get("english", ""),
            "part_of_speech": entry.get("part_of_speech", ""),
            "examples": example_text,
            "has_audio": bool(main_audio),
            "audio_main": main_audio,
            "audio_alt": alt_audio,
            "browse_letters": entry.get("browse_letters", []),
        })
    return docs


def build_partial_search_index(entries: dict) -> list[dict]:
    """Flat Penobscot forms for substring and fuzzy search (Lab partial matching)."""
    items: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def add(eid: str, entry: dict, form: str, kind: str) -> None:
        form = norm_form(form)
        if len(form) < 2:
            return
        key = (eid, form, kind)
        if key in seen:
            return
        seen.add(key)
        main, alt = audio_paths(entry)
        items.append({
            "id": eid,
            "form": form,
            "form_ascii": fold_ascii(form),
            "hw": entry.get("headword", ""),
            "en": (entry.get("english") or "")[:100],
            "kind": kind,
            "audio_main": main,
            "audio_alt": alt,
        })

    for eid, entry in entries.items():
        add(eid, entry, entry.get("headword", ""), "headword")
        for ex in entry.get("examples", []):
            add(eid, entry, ex.get("penobscot", ""), "example")

    return items


SEARCH_JS = textwrap.dedent("""\
    let idx = null;
    let docs = [];
    let partialItems = [];

    function norm(s) {
      return (s || '').normalize('NFC').trim();
    }

    function foldAscii(s) {
      const MAP = { č: 'c', Č: 'c', ə: 'e', Ə: 'e', α: 'a', Α: 'a', 'ʷ': 'w', '́': '', '̀': '', 'ˊ': '', 'ˋ': '', '‑': '-', '→': '' };
      let t = norm(s);
      for (const [k, v] of Object.entries(MAP)) t = t.split(k).join(v);
      t = t.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
      return t.toLowerCase().replace(/[^a-z0-9-]+/g, '');
    }

    function lev(a, b) {
      a = foldAscii(a); b = foldAscii(b);
      if (a === b) return 0;
      const m = a.length, n = b.length;
      if (!m) return n;
      if (!n) return m;
      const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
      for (let i = 0; i <= m; i++) dp[i][0] = i;
      for (let j = 0; j <= n; j++) dp[0][j] = j;
      for (let i = 1; i <= m; i++) {
        for (let j = 1; j <= n; j++) {
          const cost = a[i - 1] === b[j - 1] ? 0 : 1;
          dp[i][j] = Math.min(dp[i-1][j] + 1, dp[i][j-1] + 1, dp[i-1][j-1] + cost);
        }
      }
      return dp[m][n];
    }

    function looksPenobscot(query) {
      return /[čəαʷ́̀]|kʷ|hʷ|nə/i.test(query) || !/^[a-zA-Z\\s.,;!?'"()-]+$/.test(query);
    }

    async function init() {
      const [searchResp, partialResp] = await Promise.all([
        fetch('assets/search-index.json'),
        fetch('assets/partial-search.json'),
      ]);
      const data = await searchResp.json();
      docs = data.docs;
      const partialData = await partialResp.json();
      partialItems = partialData.items || [];

      idx = lunr(function() {
        this.ref('id');
        this.field('headword', { boost: 10 });
        this.field('english', { boost: 5 });
        this.field('examples', { boost: 2 });
        this.field('part_of_speech');
        docs.forEach(doc => this.add(doc));
      });

      const grid = document.getElementById('letter-grid');
      if (grid) {
        const counts = {};
        docs.forEach(d => (d.browse_letters || []).forEach(l => { counts[l] = (counts[l]||0)+1; }));
        Object.entries(counts).sort((a,b) => a[0].localeCompare(b[0])).forEach(([l, n]) => {
          const a = document.createElement('a');
          a.className = 'letter-card';
          a.href = `letter/${encodeURIComponent(l)}.html`;
          a.innerHTML = `<span class="letter">${l}</span><span class="count">${n}</span>`;
          grid.appendChild(a);
        });
      }

      const loopGlobal = document.getElementById('loop-global');
      if (loopGlobal) {
        loopGlobal.addEventListener('change', () => PenobscotAudio.setLoop(loopGlobal.checked));
      }

      const q = document.getElementById('q');
      const labLink = document.getElementById('lab-link');
      if (!q) return;
      let timer;
      const syncLabLink = () => {
        if (!labLink) return;
        const v = q.value.trim();
        labLink.href = v ? `lab/index.html?q=${encodeURIComponent(v)}` : 'lab/index.html';
      };
      q.addEventListener('input', () => {
        clearTimeout(timer);
        syncLabLink();
        timer = setTimeout(() => search(q.value.trim()), 150);
      });
      syncLabLink();
      if (q.value) search(q.value.trim());
    }

    function partialMatches(query, excludeIds) {
      const q = foldAscii(query);
      if (q.length < 3) return [];

      const hits = [];
      const seen = new Set();

      for (const item of partialItems) {
        if (excludeIds.has(item.id)) continue;
        const formLow = item.form_ascii || foldAscii(item.form);
        const dedupe = item.id + '|' + formLow;
        if (seen.has(dedupe)) continue;

        let matchType = '';
        let rank = 99;

        if (formLow === q) continue;

        if (formLow.includes(q)) {
          matchType = 'contains';
          rank = 10 + (q.length / formLow.length);
        } else if (q.includes(formLow) && formLow.length >= 3) {
          matchType = 'fragment';
          rank = 8 + (formLow.length / q.length);
        } else if (item.kind === 'headword') {
          const d = lev(q, formLow);
          if (d > 0 && d <= 2 && q.length >= 4) {
            matchType = 'similar';
            rank = 5 - d;
          }
        }

        if (!matchType) continue;
        seen.add(dedupe);
        hits.push({ ...item, matchType, rank });
      }

      hits.sort((a, b) => b.rank - a.rank || a.form.localeCompare(b.form));
      return hits.slice(0, 20);
    }

    function shouldShowPartial(query, archiveCount, partialHits) {
      if (!partialHits.length || norm(query).length < 3) return false;
      if (archiveCount < 5) return true;
      if (looksPenobscot(query)) return true;
      return false;
    }

    function renderArchiveCard(d, id) {
      const recUrls = [d.audio_main, d.audio_alt].filter(Boolean);
      let actions = '';
      recUrls.forEach((url, i) => {
        const n = recUrls.length > 1 ? ` recording ${i + 1}` : '';
        const fname = safeDownloadName(d.headword, i, recUrls.length);
        actions += `<button type="button" class="btn-play btn-play-sm" data-audio="${escapeAttr(url)}" title="Play${n} — tap again to repeat">&#9654;</button>`;
        actions += `<button type="button" class="btn-download btn-download-sm" data-audio="${escapeAttr(url)}" data-filename="${escapeAttr(fname)}" title="Save${n}">&#8681;</button>`;
      });
      return `<div class="result-card">
        <a class="result-link" href="entry/${id}.html">
          <span class="result-hw">${escapeHtml(d.headword)}</span>
          <span class="result-en">${escapeHtml(d.english)}</span>
          <span class="result-pos">${escapeHtml(d.part_of_speech)}</span>
        </a>
        ${actions ? `<div class="result-actions">${actions}</div>` : ''}
      </div>`;
    }

    function renderPartialSection(query, partialHits) {
      const matchLabel = { contains: 'contains', fragment: 'part of', similar: 'similar spelling' };
      const cards = partialHits.map(h => {
        const recUrls = [h.audio_main, h.audio_alt].filter(Boolean);
        let actions = '';
        recUrls.forEach((url, i) => {
          const n = recUrls.length > 1 ? ` recording ${i + 1}` : '';
          actions += `<button type="button" class="btn-play btn-play-sm" data-audio="${escapeAttr(url)}" title="Play${n}">&#9654;</button>`;
        });
        const kind = h.kind === 'headword' ? 'headword' : 'example';
        return `<div class="partial-card">
          <div class="partial-card-head">
            <span class="badge badge-lab">${escapeHtml(matchLabel[h.matchType] || h.matchType)}</span>
            <span class="partial-kind">${escapeHtml(kind)}</span>
          </div>
          <p class="partial-form">${escapeHtml(h.form)}</p>
          <a class="partial-entry" href="entry/${h.id}.html">
            <span class="partial-hw">${escapeHtml(h.hw)}</span>
            <span class="partial-en">${escapeHtml(h.en)}</span>
          </a>
          <div class="partial-card-foot">
            <a class="btn-lab-link" href="lab/index.html?q=${encodeURIComponent(h.form)}">Break down &#8594;</a>
            ${actions ? `<div class="result-actions">${actions}</div>` : ''}
          </div>
        </div>`;
      }).join('');

      return `<section class="lab-panel partial-panel">
        <p class="badge-row"><span class="badge badge-lab">Partial match — Lab</span></p>
        <h2 class="partial-title">Penobscot fragment matches</h2>
        <p class="lab-hint">Forms containing <strong>${escapeHtml(query)}</strong> — verify with audio. For official definitions, see archive results above.</p>
        <div class="partial-cards">${cards}</div>
      </section>`;
    }

    function search(query) {
      const results = document.getElementById('results');
      const partialEl = document.getElementById('partial-results');
      const status = document.getElementById('status');
      if (!query) {
        results.innerHTML = '';
        if (partialEl) partialEl.innerHTML = '';
        status.textContent = '';
        return;
      }
      let hits;
      try {
        hits = idx.search(query);
        if (hits.length === 0) {
          hits = idx.query(q => {
            query.toLowerCase().split(/\\s+/).filter(Boolean).forEach(term => {
              q.term(term, { wildcard: lunr.Query.wildcard.TRAILING });
            });
          });
        }
      } catch (e) {
        hits = [];
      }
      const byId = Object.fromEntries(docs.map(d => [d.id, d]));
      const archiveIds = new Set(hits.slice(0, 100).map(h => h.ref));
      const partialHits = partialMatches(query, archiveIds);

      let statusParts = [`${hits.length} archive result${hits.length === 1 ? '' : 's'}`];
      if (partialHits.length) statusParts.push(`${partialHits.length} partial`);
      status.textContent = statusParts.join(' · ');

      results.innerHTML = hits.slice(0, 100).map(h => {
        const d = byId[h.ref];
        if (!d) return '';
        return renderArchiveCard(d, h.ref);
      }).join('');

      if (partialEl) {
        partialEl.innerHTML = shouldShowPartial(query, hits.length, partialHits)
          ? renderPartialSection(query, partialHits)
          : '';
      }

      PenobscotAudio.bindPlayButtons(results);
      PenobscotAudio.bindDownloadButtons(results);
      if (partialEl) PenobscotAudio.bindPlayButtons(partialEl);
    }

    function safeDownloadName(headword, index, total) {
      const base = (headword || 'penobscot-word').replace(/[<>:"/\\\\|?*]/g, '').trim() || 'penobscot-word';
      if (total > 1 && index > 0) return `${base}-${index + 1}.mp3`;
      return `${base}.mp3`;
    }

    function escapeHtml(s) {
      return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    function escapeAttr(s) {
      return (s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;');
    }

    init();
""")


AUDIO_PLAYER_JS = textwrap.dedent("""\
    /**
     * Cached audio player for language drilling.
     * Fetches each clip once into memory; replay is instant with no re-buffering.
     */
    const PenobscotAudio = (function() {
      const cache = new Map();
      let globalLoop = false;
      let activeAudio = null;
      let activeBtn = null;

      function stopActive() {
        if (activeAudio) {
          activeAudio.pause();
          activeAudio.currentTime = 0;
          activeAudio = null;
        }
        if (activeBtn) {
          activeBtn.classList.remove('playing', 'loading');
          activeBtn = null;
        }
      }

      async function load(url) {
        if (cache.has(url)) return cache.get(url);
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('Audio not found');
        const blob = await resp.blob();
        const blobUrl = URL.createObjectURL(blob);
        const audio = new Audio(blobUrl);
        await new Promise((resolve, reject) => {
          audio.addEventListener('canplaythrough', resolve, { once: true });
          audio.addEventListener('error', reject, { once: true });
          audio.load();
        });
        const entry = { audio, blobUrl, url };
        cache.set(url, entry);
        return entry;
      }

      async function play(url, btn, loopOverride) {
        if (!url) return;
        let entry = cache.get(url);
        const isCached = !!entry;

        if (!isCached && btn) btn.classList.add('loading');

        try {
          if (!entry) entry = await load(url);
        } catch (e) {
          if (btn) btn.classList.remove('loading');
          return;
        }

        const shouldLoop = loopOverride !== undefined ? loopOverride : globalLoop;
        const sameTrack = activeAudio === entry.audio;

        if (!sameTrack) stopActive();

        entry.audio.loop = shouldLoop;
        entry.audio.currentTime = 0;
        activeAudio = entry.audio;
        activeBtn = btn || null;

        if (btn) {
          btn.classList.remove('loading');
          btn.classList.add('playing');
        }

        entry.audio.onended = () => {
          if (!entry.audio.loop && btn) btn.classList.remove('playing');
        };

        try {
          await entry.audio.play();
        } catch (e) {
          if (btn) btn.classList.remove('playing');
        }
      }

      function setLoop(on) {
        globalLoop = on;
        if (activeAudio) activeAudio.loop = on;
        document.querySelectorAll('.btn-loop[aria-pressed]').forEach(btn => {
          btn.setAttribute('aria-pressed', on ? 'true' : 'false');
          btn.classList.toggle('active', on);
        });
        const global = document.getElementById('loop-global');
        if (global) global.checked = on;
      }

      function toggleLoop(btn) {
        const on = btn.getAttribute('aria-pressed') !== 'true';
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        btn.classList.toggle('active', on);
        if (activeAudio) activeAudio.loop = on;
        return on;
      }

      function bindPlayButtons(root) {
        (root || document).querySelectorAll('.btn-play[data-audio]').forEach(btn => {
          if (btn.dataset.bound) return;
          btn.dataset.bound = '1';
          btn.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();
            play(btn.dataset.audio, btn);
          });
        });
      }

      function initDrillPlayers() {
        document.querySelectorAll('.drill-player[data-audio]').forEach(block => {
          const url = block.dataset.audio;
          load(url).catch(() => {});
          const playBtn = block.querySelector('.btn-play');
          const loopBtn = block.querySelector('.btn-loop');
          if (playBtn && !playBtn.dataset.bound) {
            playBtn.dataset.bound = '1';
            playBtn.addEventListener('click', () => {
              const loop = loopBtn && loopBtn.getAttribute('aria-pressed') === 'true';
              play(url, playBtn, loop);
            });
          }
          if (loopBtn && !loopBtn.dataset.bound) {
            loopBtn.dataset.bound = '1';
            loopBtn.addEventListener('click', () => toggleLoop(loopBtn));
          }
        });
      }

      async function download(url, filename) {
        if (!url) return;
        try {
          const entry = cache.has(url) ? cache.get(url) : await load(url);
          const a = document.createElement('a');
          a.href = entry.blobUrl;
          a.download = filename || url.split('/').pop();
          document.body.appendChild(a);
          a.click();
          a.remove();
        } catch (e) { /* ignore */ }
      }

      function bindDownloadButtons(root) {
        (root || document).querySelectorAll('.btn-download[data-audio]').forEach(btn => {
          if (btn.dataset.bound) return;
          btn.dataset.bound = '1';
          btn.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();
            download(btn.dataset.audio, btn.dataset.filename);
          });
        });
      }

      function initPage() {
        bindPlayButtons(document);
        bindDownloadButtons(document);
        initDrillPlayers();
      }

      return { play, load, download, setLoop, toggleLoop, bindPlayButtons, bindDownloadButtons, initDrillPlayers, initPage };
    })();
""")


LAB_GUESSER_JS = (Path(__file__).parent / "lab_guesser.js").read_text(encoding="utf-8")
KINSHIP_JS = (Path(__file__).parent / "kinship.js").read_text(encoding="utf-8")
SEMANTIC_TAGS_JS = (Path(__file__).parent / "semantic_tags.js").read_text(encoding="utf-8")
LISTEN3_JS = (Path(__file__).parent / "listen3.js").read_text(encoding="utf-8")

STYLE_CSS = textwrap.dedent("""\
    :root {
      --bg: #f7f4ef;
      --surface: #ffffff;
      --text: #1a1a1a;
      --muted: #5c5c5c;
      --accent: #2d5a3d;
      --accent-light: #e8f0ea;
      --lab-accent: #9a6b1a;
      --lab-bg: #fdf6e8;
      --lab-border: #e8d4a8;
      --border: #ddd5c8;
      --radius: 10px;
      --font: "Segoe UI", system-ui, -apple-system, sans-serif;
      --font-word: "Segoe UI", "Arial Unicode MS", sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.6; min-height: 100vh; display: flex; flex-direction: column; }
    .nav { display: flex; align-items: center; gap: 1.5rem; padding: 1rem 2rem; background: var(--accent); color: #fff; }
    .nav a { color: #fff; text-decoration: none; opacity: 0.85; }
    .nav a:hover, .nav a.active { opacity: 1; text-decoration: underline; }
    .nav .brand { font-weight: 700; font-size: 1.1rem; opacity: 1; margin-right: auto; }
    .container { flex: 1; max-width: 900px; width: 100%; margin: 0 auto; padding: 2rem 1.5rem; }
    .footer { text-align: center; padding: 1.5rem; font-size: 0.85rem; color: var(--muted); border-top: 1px solid var(--border); }
    .footer a { color: var(--accent); }
    .hero { text-align: center; margin-bottom: 2rem; }
    .hero h1 { font-size: 2.2rem; color: var(--accent); margin-bottom: 0.5rem; }
    .subtitle { color: var(--muted); }
    .search-section { margin-bottom: 2.5rem; }
    #q { width: 100%; padding: 1rem 1.25rem; font-size: 1.15rem; border: 2px solid var(--border); border-radius: var(--radius); background: var(--surface); }
    #q:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-light); }
    .search-hint { font-size: 0.9rem; color: var(--muted); margin-top: 0.5rem; }
    .status { color: var(--muted); margin-top: 0.75rem; font-size: 0.9rem; }
    .badge-row { margin-bottom: 0.75rem; }
    .badge { display: inline-block; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.03em; text-transform: uppercase; padding: 0.35rem 0.65rem; border-radius: 6px; }
    .badge-archive { background: var(--accent-light); color: var(--accent); border: 1px solid #b8d4be; }
    .badge-lab { background: var(--lab-bg); color: var(--lab-accent); border: 1px solid var(--lab-border); }
    .archive-panel { border-left: 4px solid var(--accent); padding-left: 1rem; }
    .lab-panel { background: var(--lab-bg); border: 1px solid var(--lab-border); border-radius: var(--radius); padding: 1.25rem; margin-bottom: 1.5rem; }
    .lab-page { --accent: var(--lab-accent); }
    .lab-hero h1 { color: var(--lab-accent); }
    .search-toolbar { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: 0.75rem; margin-top: 0.5rem; }
    .search-toolbar-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 1rem; }
    .btn-lab-link { font-size: 0.9rem; color: var(--lab-accent); font-weight: 600; text-decoration: none; white-space: nowrap; }
    .btn-lab-link:hover { text-decoration: underline; }
    .btn-lab-cta { display: inline-block; margin-top: 0.5rem; padding: 0.65rem 1.25rem; background: var(--lab-accent); color: #fff; border-radius: var(--radius); text-decoration: none; font-weight: 600; }
    .btn-lab-cta:hover { opacity: 0.9; }
    .about-section { margin-bottom: 2rem; }
    .about-section h2 { color: var(--accent); margin-bottom: 0.75rem; font-size: 1.15rem; }
    .about-section ul { margin: 0.5rem 0 0.75rem 1.25rem; line-height: 1.55; }
    .about-section li { margin-bottom: 0.35rem; }
    .lab-panel.about-section h2 { color: var(--lab-accent); }
    .code-block { background: #2d2d2d; color: #f0f0f0; padding: 1rem; border-radius: var(--radius); overflow-x: auto; font-size: 0.85rem; }
    .guesser-form { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: flex-end; margin-bottom: 1rem; }
    .guesser-form label { width: 100%; font-weight: 600; color: var(--lab-accent); }
    .guesser-form input { flex: 1; min-width: 200px; padding: 0.85rem 1rem; font-size: 1.1rem; border: 2px solid var(--lab-border); border-radius: var(--radius); font-family: var(--font-word); }
    .btn-analyze { padding: 0.85rem 1.5rem; background: var(--lab-accent); color: #fff; border: none; border-radius: var(--radius); font-size: 1rem; font-weight: 600; cursor: pointer; }
    .btn-analyze:hover { opacity: 0.92; }
    .btn-analyze:disabled { opacity: 0.45; cursor: not-allowed; }
    .btn-secondary {
      padding: 0.65rem 1rem; background: var(--surface); color: var(--text);
      border: 1px solid var(--lab-border); border-radius: var(--radius); font-size: 0.95rem; cursor: pointer;
    }
    .btn-secondary:hover { border-color: var(--lab-accent); color: var(--lab-accent); }
    .lab-game-cta { margin-top: 1rem; display: flex; flex-wrap: wrap; align-items: center; gap: 0.65rem; }
    .lab-game-cta .btn-lab-cta { margin-top: 0; }
    .listen3-panel { max-width: 40rem; }
    .listen3-toolbar { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; margin: 1rem 0; }
    .listen3-size-label { font-size: 0.9rem; color: var(--muted); display: flex; align-items: center; gap: 0.4rem; }
    .listen3-size-label select { padding: 0.35rem 0.5rem; border-radius: 6px; border: 1px solid var(--border); }
    .listen3-deck-info { margin-bottom: 1rem; }
    .listen3-status-bar { display: flex; justify-content: space-between; margin-bottom: 1rem; font-size: 0.95rem; color: var(--muted); }
    .listen3-audio-block { text-align: center; margin: 1.25rem 0 1.5rem; padding: 1.25rem; background: #fff; border: 1px solid var(--lab-border); border-radius: var(--radius); }
    .listen3-big-play {
      font-size: 1.15rem; padding: 0.85rem 1.75rem; min-width: 8rem;
      border-radius: 999px; border: 2px solid var(--lab-accent); background: var(--lab-bg);
      color: var(--lab-accent); cursor: pointer; font-weight: 700;
    }
    .listen3-big-play.playing { background: var(--lab-accent); color: #fff; }
    .listen3-big-play.loading { opacity: 0.6; }
    .listen3-replay-hint { margin-top: 0.5rem; font-size: 0.85rem; }
    .listen3-choices { display: flex; flex-direction: column; gap: 0.65rem; margin: 0.75rem 0 1rem; }
    .listen3-choice {
      text-align: left; padding: 0.85rem 1rem; border-radius: var(--radius);
      border: 1px solid var(--lab-border); background: var(--surface); cursor: pointer;
      font-size: 1rem; line-height: 1.35; color: var(--text);
    }
    .listen3-choice:hover:not(:disabled) { border-color: var(--lab-accent); background: var(--lab-bg); }
    .listen3-choice:disabled { cursor: default; }
    .listen3-choice.is-correct { border-color: var(--accent); background: var(--accent-light); }
    .listen3-choice.is-wrong { border-color: #b54a4a; background: #fceeed; }
    .listen3-feedback { margin: 1rem 0; padding: 0.9rem 1rem; border-radius: var(--radius); border: 1px solid var(--lab-border); background: #fff; }
    .listen3-feedback.ok { border-left: 4px solid var(--accent); }
    .listen3-feedback.bad { border-left: 4px solid #b54a4a; }
    .listen3-fb-title { font-weight: 700; margin: 0 0 0.35rem; }
    .listen3-fb-hw { font-family: var(--font-word); font-size: 1.25rem; font-weight: 600; color: var(--lab-accent); margin: 0.25rem 0; }
    .listen3-fb-en { margin: 0.35rem 0; }
    .listen3-fb-links { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.65rem; }
    .listen3-next { width: 100%; margin-top: 0.5rem; }
    .listen3-done-actions { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; margin-top: 1rem; }
    .listen3-summary-score { font-size: 1.35rem; font-weight: 700; color: var(--lab-accent); }
    .lab-hint { font-size: 0.9rem; color: var(--muted); margin-bottom: 1rem; }
    .lab-mode { font-size: 0.88rem; margin: -0.5rem 0 0.75rem; font-style: italic; }
    .lab-subhead { color: var(--lab-accent); font-size: 0.95rem; margin: 1.5rem 0 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; }
    .detection-banner { font-size: 0.9rem; background: var(--lab-bg); border: 1px solid var(--lab-border); border-radius: var(--radius); padding: 0.65rem 0.85rem; margin-bottom: 0.85rem; }
    .breakdown-results { margin-bottom: 1rem; display: flex; flex-direction: column; gap: 0.85rem; }
    .breakdown-meaning { margin-bottom: 1rem; padding: 0.85rem; background: var(--lab-bg); border-radius: var(--radius); }
    .breakdown-meaning-text { font-size: 1.2rem; line-height: 1.45; margin: 0.25rem 0 0; }
    .breakdown-pb-result { font-family: var(--font-word); font-size: 1.45rem; font-weight: 700; color: var(--lab-accent); margin: 0.35rem 0 0.75rem; }
    .breakdown-reasoning { margin: 0.75rem 0; }
    .breakdown-reasons { margin: 0.35rem 0 0 1.1rem; font-size: 0.92rem; line-height: 1.5; }
    .breakdown-reasons code { font-family: var(--font-word); background: #fff; padding: 0.1rem 0.3rem; border-radius: 3px; }
    .breakdown-reasons a { color: var(--accent); font-weight: 600; }
    .breakdown-typed { font-size: 0.88rem; color: var(--muted); margin-bottom: 0.75rem; }
    .breakdown-typed code { font-family: var(--font-word); background: #fff; padding: 0.1rem 0.3rem; border-radius: 3px; }
    .sentence-hit { padding: 0.75rem 0; border-top: 1px solid var(--lab-border); }
    .sentence-hit:first-of-type { border-top: none; padding-top: 0; }
    .kinship-panel { margin-top: 1.5rem; }
    .kinship-cats { display: flex; flex-direction: column; gap: 1rem; margin-bottom: 1rem; }
    .kinship-group-title { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 0.5rem; }
    .kinship-btns { display: flex; flex-wrap: wrap; gap: 0.5rem; }
    .kinship-btn { padding: 0.45rem 0.85rem; border: 1px solid var(--lab-border); background: var(--surface); border-radius: 999px; font-size: 0.9rem; cursor: pointer; color: var(--text); transition: all 0.12s; }
    .kinship-btn:hover, .kinship-btn.active { background: var(--lab-bg); border-color: var(--lab-accent); color: var(--lab-accent); }
    .kinship-count { font-size: 0.8rem; color: var(--muted); margin-left: 0.15rem; }
    .kinship-btn.active .kinship-count { color: var(--lab-accent); }
    .kinship-results { margin-top: 1rem; }
    .kinship-results-head { margin-bottom: 1rem; }
    .kinship-results-head h3 { color: var(--lab-accent); margin-bottom: 0.35rem; }
    .kinship-hints ul, .kinship-morph ul { margin: 0.35rem 0 0 1.1rem; font-size: 0.9rem; color: var(--muted); }
    .kinship-hints code, .kinship-morph code { font-family: var(--font-word); background: #fff; padding: 0.1rem 0.3rem; border-radius: 3px; }
    .kinship-cards { display: flex; flex-direction: column; gap: 0.75rem; }
    .kinship-card { background: var(--surface); border: 1px solid var(--lab-border); border-left: 4px solid var(--lab-accent); border-radius: var(--radius); padding: 0.9rem 1rem; }
    .kinship-hw { font-family: var(--font-word); font-size: 1.2rem; font-weight: 600; margin: 0 0 0.35rem; }
    .kinship-hw a { color: var(--accent); }
    .kinship-en { margin: 0 0 0.35rem; }
    .kinship-pos { font-size: 0.85rem; color: var(--muted); font-style: italic; }
    .kinship-morph { margin-top: 0.5rem; }
    .kinship-card-foot { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin-top: 0.65rem; padding-top: 0.65rem; border-top: 1px solid var(--lab-border); }
    .themes-panel { margin-top: 1.5rem; }
    .theme-chips { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.5rem 0 0.75rem; align-items: center; }
    .theme-chip {
      display: inline-block; padding: 0.2rem 0.65rem; border-radius: 999px; font-size: 0.8rem;
      background: var(--lab-bg); border: 1px solid var(--lab-border); color: var(--lab-accent);
      text-decoration: none;
    }
    .theme-chip:hover { border-color: var(--lab-accent); background: #faf0d8; }
    .related-meaning .badge-lab { font-size: 0.7rem; vertical-align: middle; }
    .tag-chips { margin: 0.35rem 0 0; display: flex; flex-wrap: wrap; gap: 0.35rem; }
    .tag-chip {
      font-size: 0.75rem; padding: 0.12rem 0.5rem; border-radius: 999px;
      background: var(--lab-bg); border: 1px solid var(--lab-border); color: var(--muted);
    }
    .breakdown-card { background: var(--surface); border: 1px solid var(--lab-border); border-left: 4px solid var(--lab-accent); border-radius: var(--radius); padding: 1.1rem 1.25rem; }
    .breakdown-title { color: var(--lab-accent); font-size: 1.05rem; margin-bottom: 0.5rem; }
    .breakdown-query { font-family: var(--font-word); font-size: 1.35rem; font-weight: 600; color: var(--lab-accent); margin-bottom: 0.75rem; }
    .breakdown-visual { display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; margin-bottom: 1rem; padding: 0.75rem; background: var(--lab-bg); border-radius: var(--radius); font-family: var(--font-word); font-size: 1.1rem; }
    .bd-seg { padding: 0.2rem 0.45rem; border-radius: 4px; }
    .bd-prefix { background: #fff; border: 1px solid var(--lab-border); color: var(--lab-accent); font-weight: 600; }
    .bd-stem { background: #fff; border: 1px solid #b8d4be; color: var(--accent); font-weight: 600; }
    .bd-whole { font-weight: 600; }
    .bd-plus { color: var(--muted); font-weight: 700; }
    .breakdown-parts { display: flex; flex-direction: column; gap: 0.65rem; margin-bottom: 1rem; }
    .breakdown-piece, .breakdown-stem-match, .breakdown-unknown { margin-bottom: 0.75rem; }
    .breakdown-label { display: block; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 0.25rem; }
    .breakdown-code { font-family: var(--font-word); font-size: 1.05rem; background: #fff; padding: 0.15rem 0.4rem; border-radius: 4px; }
    .breakdown-hint, .breakdown-sample, .breakdown-meta { display: block; font-size: 0.88rem; color: var(--muted); margin-top: 0.2rem; }
    .breakdown-sample { font-family: var(--font-word); font-size: 0.85rem; }
    .breakdown-entry a { font-family: var(--font-word); font-weight: 600; color: var(--accent); }
    .breakdown-en { display: block; margin-top: 0.2rem; }
    .breakdown-unknowns { margin: 0.35rem 0 0 1.1rem; font-size: 0.9rem; color: var(--muted); }
    .breakdown-foot { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.5rem; margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--lab-border); }
    .breakdown-note { margin-bottom: 0.5rem; }
    .breakdown-banner { font-size: 0.9rem; background: #fff; border: 1px solid var(--lab-border); border-radius: var(--radius); padding: 0.5rem 0.75rem; margin-bottom: 0.75rem; }
    .breakdown-banner a { color: var(--accent); font-weight: 600; }
    .guesser-results { display: flex; flex-direction: column; gap: 0.75rem; }
    .guesser-card { background: var(--surface); border: 1px solid var(--lab-border); border-radius: var(--radius); padding: 1rem; }
    .guesser-card.confidence-high { border-left: 4px solid var(--lab-accent); }
    .guesser-card.confidence-medium { border-left: 4px solid #c9a84c; }
    .guesser-card.confidence-low { border-left: 4px solid var(--border); }
    .guesser-card-head { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; margin-bottom: 0.5rem; }
    .guesser-type { font-size: 0.8rem; color: var(--muted); text-transform: capitalize; }
    .guesser-matched { font-family: var(--font-word); font-size: 1.25rem; font-weight: 600; color: var(--lab-accent); margin: 0.25rem 0; }
    .guesser-note { font-size: 0.9rem; color: var(--muted); margin-bottom: 0.5rem; }
    .guesser-entry a { font-family: var(--font-word); font-weight: 600; color: var(--accent); }
    .guesser-en { display: block; margin-top: 0.2rem; }
    .guesser-card-foot { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.5rem; margin-top: 0.75rem; }
    .btn-archive-link { font-size: 0.9rem; color: var(--accent); font-weight: 600; }
    .affix-table { font-size: 0.9rem; }
    .affix-table code { font-family: var(--font-word); background: #fff; padding: 0.1rem 0.35rem; border-radius: 4px; }
    .affix-table .sample { font-family: var(--font-word); font-size: 0.85rem; color: var(--muted); }
    .loop-global { display: flex; align-items: center; gap: 0.4rem; font-size: 0.9rem; color: var(--muted); cursor: pointer; user-select: none; }
    .loop-global input { accent-color: var(--accent); width: 1rem; height: 1rem; }
    .results { display: flex; flex-direction: column; gap: 0.5rem; margin-top: 1rem; }
    .partial-results { margin-top: 1.25rem; }
    .partial-panel { margin-top: 0.5rem; }
    .partial-title { color: var(--lab-accent); font-size: 1.05rem; margin-bottom: 0.5rem; text-transform: none; letter-spacing: 0; }
    .partial-cards { display: flex; flex-direction: column; gap: 0.6rem; margin-top: 0.75rem; }
    .partial-card { background: var(--surface); border: 1px solid var(--lab-border); border-left: 4px solid var(--lab-accent); border-radius: var(--radius); padding: 0.85rem 1rem; }
    .partial-card-head { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; margin-bottom: 0.35rem; }
    .partial-kind { font-size: 0.8rem; color: var(--muted); text-transform: capitalize; }
    .partial-form { font-family: var(--font-word); font-size: 1.15rem; font-weight: 600; color: var(--lab-accent); margin-bottom: 0.35rem; }
    .partial-entry { text-decoration: none; color: inherit; display: block; margin-bottom: 0.5rem; }
    .partial-hw { font-family: var(--font-word); font-weight: 600; color: var(--accent); display: block; }
    .partial-en { font-size: 0.9rem; color: var(--muted); display: block; }
    .partial-card-foot { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.5rem; }
    .result-card { display: flex; align-items: center; gap: 0.75rem; padding: 0.85rem 1rem; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); transition: border-color 0.15s, box-shadow 0.15s; }
    .result-card:hover { border-color: var(--accent); box-shadow: 0 2px 8px rgba(45,90,61,0.12); }
    .result-link { flex: 1; min-width: 0; text-decoration: none; color: inherit; }
    .result-actions { display: flex; gap: 0.35rem; flex-shrink: 0; }
    .result-hw { font-family: var(--font-word); font-size: 1.2rem; font-weight: 600; color: var(--accent); display: block; }
    .result-en { display: block; color: var(--text); margin-top: 0.2rem; }
    .result-pos { display: block; font-size: 0.85rem; color: var(--muted); margin-top: 0.15rem; }
    .btn-play { display: inline-flex; align-items: center; justify-content: center; border: 2px solid var(--accent); background: var(--accent-light); color: var(--accent); border-radius: 50%; cursor: pointer; font-family: var(--font); line-height: 1; transition: background 0.12s, transform 0.1s; flex-shrink: 0; }
    .btn-play:hover { background: #d4e8d9; }
    .btn-play:active { transform: scale(0.94); }
    .btn-play-sm { width: 2.5rem; height: 2.5rem; font-size: 0.95rem; }
    .btn-play-lg { width: auto; height: auto; border-radius: var(--radius); padding: 0.65rem 1.25rem; font-size: 1rem; font-weight: 600; gap: 0.35rem; }
    .btn-play.playing { background: var(--accent); color: #fff; }
    .btn-download { display: inline-flex; align-items: center; justify-content: center; border: 2px solid var(--border); background: var(--surface); color: var(--muted); border-radius: 50%; cursor: pointer; font-family: var(--font); line-height: 1; transition: all 0.12s; flex-shrink: 0; }
    .btn-download:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-light); }
    .btn-download-sm { width: 2.5rem; height: 2.5rem; font-size: 1rem; }
    .btn-download.btn-play-lg, .drill-controls .btn-download { width: auto; height: auto; border-radius: var(--radius); padding: 0.65rem 1rem; font-size: 0.9rem; gap: 0.25rem; }
    .play-group { display: flex; gap: 0.3rem; justify-content: center; flex-wrap: wrap; }
    .play-cell { width: auto; min-width: 3rem; text-align: center; }
    .btn-play.loading { opacity: 0.55; cursor: wait; }
    .btn-loop { display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.65rem 1rem; border: 2px solid var(--border); background: var(--surface); color: var(--muted); border-radius: var(--radius); cursor: pointer; font-size: 0.95rem; transition: all 0.12s; }
    .btn-loop:hover { border-color: var(--accent); color: var(--accent); }
    .btn-loop.active, .btn-loop[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: #fff; }
    .drill-controls { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }

    .letter-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 0.75rem; }
    .letter-card { display: flex; flex-direction: column; align-items: center; padding: 1rem 0.5rem; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); text-decoration: none; color: var(--text); transition: all 0.15s; }
    .letter-card:hover { border-color: var(--accent); background: var(--accent-light); }
    .letter-card .letter { font-family: var(--font-word); font-size: 1.4rem; font-weight: 700; color: var(--accent); }
    .letter-card .count { font-size: 0.8rem; color: var(--muted); margin-top: 0.25rem; }
    .quick-browse h2, h1 { color: var(--accent); margin-bottom: 1rem; }
    .stats { color: var(--muted); margin-bottom: 1.5rem; }
    .headword { font-family: var(--font-word); font-size: 2.5rem; color: var(--accent); line-height: 1.2; }
    .entry-header { margin-bottom: 2rem; }
    .pos { color: var(--muted); font-style: italic; margin-top: 0.5rem; }
    .pos-abbr { cursor: help; text-decoration: underline dotted; text-decoration-color: var(--border); text-underline-offset: 2px; }
    .pos-abbr:hover { text-decoration-color: var(--accent); color: var(--text); }
    th .pos-abbr, th .pos-plain { font-style: normal; font-weight: 600; }
    .browse-in { font-size: 0.9rem; margin-top: 0.5rem; }
    .browse-in a { color: var(--accent); }
    .definition, .audio-section, .examples { margin-bottom: 2rem; }
    section h2 { font-size: 1rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 0.75rem; }
    .english { font-size: 1.15rem; }
    .drill-player { margin-bottom: 1.25rem; padding: 1rem; background: var(--accent-light); border-radius: var(--radius); border: 1px solid var(--border); }
    .audio-label { display: block; font-size: 0.85rem; color: var(--muted); margin-bottom: 0.6rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
    .muted { color: var(--muted); font-style: italic; }
    table { width: 100%; border-collapse: collapse; background: var(--surface); border-radius: var(--radius); overflow: hidden; }
    th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border); }
    th { background: var(--accent-light); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--accent); }
    .word-list .word-row { cursor: pointer; }
    .word-list .word-row:hover { background: var(--accent-light); }
    .word-list .hw a { font-family: var(--font-word); font-weight: 600; color: var(--accent); text-decoration: none; }
    .word-list .en { color: var(--muted); font-size: 0.95rem; }
    .letter-search { margin-bottom: 1rem; }
    .letter-search input { width: 100%; padding: 0.75rem 1rem; border: 1px solid var(--border); border-radius: var(--radius); font-size: 1rem; }
    .source-link { margin-top: 2rem; font-size: 0.9rem; }
    .source-link a { color: var(--muted); }
    .entry-lab-panel { margin-top: 2rem; }
    .entry-lab-panel h2 { color: var(--lab-accent); font-size: 1.15rem; text-transform: none; letter-spacing: 0; margin-bottom: 0.5rem; }
    .entry-lab-panel h3 { color: var(--lab-accent); font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.04em; margin: 1.25rem 0 0.5rem; }
    .related-hint { font-size: 0.88rem; color: var(--muted); margin-bottom: 0.65rem; }
    .related-list { list-style: none; display: flex; flex-direction: column; gap: 0.55rem; }
    .related-item { display: grid; grid-template-columns: 1fr auto; gap: 0.2rem 0.75rem; align-items: center; padding: 0.65rem 0.85rem; background: var(--surface); border: 1px solid var(--lab-border); border-radius: var(--radius); }
    .related-item.related-meta { grid-template-columns: 1fr; }
    .related-hw { font-family: var(--font-word); font-weight: 600; color: var(--lab-accent); grid-column: 1; }
    a.related-hw { text-decoration: none; color: var(--accent); }
    a.related-hw:hover { text-decoration: underline; }
    .related-note { font-size: 0.8rem; color: var(--muted); text-transform: capitalize; grid-column: 1; }
    .related-en { font-size: 0.9rem; color: var(--text); grid-column: 1; }
    .related-item .btn-lab-link { grid-column: 2; grid-row: 1 / span 3; align-self: center; white-space: nowrap; }
    .related-actions { grid-column: 2; grid-row: 1 / span 3; display: flex; gap: 0.3rem; align-self: center; }
    .related-footer { margin-top: 1rem; }
    .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); }
    @media (max-width: 600px) {
      .headword { font-size: 1.8rem; }
      .nav { padding: 0.75rem 1rem; gap: 1rem; }
      .container { padding: 1.25rem 1rem; }
    }
""")


def ensure_audio_link() -> None:
    """Link site/audio -> ../audio so the local server can play files."""
    link = SITE_DIR / "audio"
    if link.exists():
        return
    try:
        link.symlink_to(AUDIO_DIR, target_is_directory=True)
    except OSError:
        import subprocess
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(AUDIO_DIR)],
            check=False,
            capture_output=True,
        )


def ensure_lunr(assets: Path) -> None:
    dest = assets / "lunr.min.js"
    if dest.exists() and dest.stat().st_size > 0:
        return
    import urllib.request
    url = "https://cdn.jsdelivr.net/npm/lunr@2.3.9/lunr.min.js"
    print(f"Downloading {url} ...")
    urllib.request.urlretrieve(url, dest)


def main() -> int:
    ensure_dirs()
    catalog = load_json(ENTRIES_JSON, {"entries": {}, "meta": {}})
    entries: dict = catalog.get("entries", {})
    meta: dict = catalog.get("meta", {})
    if not entries:
        print("No entries. Run spider.py first.")
        return 1

    import subprocess
    import sys

    scripts_dir = Path(__file__).parent
    print("Mining Lab affix patterns...")
    subprocess.run([sys.executable, str(scripts_dir / "mine_affixes.py")], check=True)
    print("Mining semantic theme tags...")
    subprocess.run([sys.executable, str(scripts_dir / "mine_semantic_tags.py")], check=True)
    print("Mining kinship/perspective index...")
    subprocess.run([sys.executable, str(scripts_dir / "mine_kinship.py")], check=True)

    assets = SITE_DIR / "assets"
    entry_dir = SITE_DIR / "entry"
    letter_dir = SITE_DIR / "letter"
    lab_dir = SITE_DIR / "lab"
    for d in (assets, entry_dir, letter_dir, lab_dir):
        d.mkdir(parents=True, exist_ok=True)
    ensure_lunr(assets)
    ensure_audio_link()

    lab_assets = [
        (GUESSER_FORMS_JSON, "guesser-forms.json"),
        (AFFIX_PATTERNS_JSON, "affix-patterns.json"),
        (BASE_WORDS_JSON, "base-words.json"),
        (SENTENCE_EXAMPLES_JSON, "sentence-examples.json"),
        (ENGLISH_INDEX_JSON, "english-index.json"),
        (KINSHIP_INDEX_JSON, "kinship-index.json"),
        (SEMANTIC_TAGS_JSON, "semantic-tags.json"),
    ]
    for src, name in lab_assets:
        if src.exists():
            save_json(assets / name, load_json(src))

    semantic_index = load_json(SEMANTIC_TAGS_JSON, {}) if SEMANTIC_TAGS_JSON.exists() else {}

    print("Building Listen-3 decks...")
    listen3 = build_listen3_decks(entries, semantic_index)
    save_json(LISTEN3_DECKS_JSON, listen3)
    save_json(assets / "listen3-decks.json", listen3)
    print(
        f"Listen-3: {listen3['meta']['playable_tags']} theme decks, "
        f"{listen3['meta']['playable_entries']} unique words with audio"
    )

    by_letter: dict[str, list] = {}
    for entry in entries.values():
        for letter in entry.get("browse_letters") or ["uncategorized"]:
            by_letter.setdefault(letter, []).append(entry)

    hw_index = build_headword_index(entries)

    print("Building entry pages...")
    for eid, entry in entries.items():
        (entry_dir / f"{eid}.html").write_text(
            build_entry_page(
                entry,
                hw_index=hw_index,
                entries=entries,
                by_letter=by_letter,
                semantic_index=semantic_index,
            ),
            encoding="utf-8",
        )

    print("Building letter pages...")
    for letter, letter_entries in by_letter.items():
        safe = letter.replace("/", "_")
        (letter_dir / f"{safe}.html").write_text(build_letter_page(letter, letter_entries), encoding="utf-8")

    (SITE_DIR / "index.html").write_text(build_index(entries, meta), encoding="utf-8")
    (SITE_DIR / "browse.html").write_text(build_browse_page(by_letter), encoding="utf-8")
    (SITE_DIR / "about.html").write_text(build_about_page(meta), encoding="utf-8")
    (lab_dir / "index.html").write_text(build_lab_page(), encoding="utf-8")
    (lab_dir / "listen3.html").write_text(build_listen3_page(), encoding="utf-8")
    (assets / "style.css").write_text(STYLE_CSS, encoding="utf-8")
    (assets / "search.js").write_text(SEARCH_JS, encoding="utf-8")
    (assets / "audio-player.js").write_text(AUDIO_PLAYER_JS, encoding="utf-8")
    (assets / "lab-guesser.js").write_text(LAB_GUESSER_JS, encoding="utf-8")
    (assets / "kinship.js").write_text(KINSHIP_JS, encoding="utf-8")
    (assets / "semantic-tags.js").write_text(SEMANTIC_TAGS_JS, encoding="utf-8")
    (assets / "listen3.js").write_text(LISTEN3_JS, encoding="utf-8")
    (assets / "pos-tooltips.js").write_text(build_tooltips_js(), encoding="utf-8")

    search_docs = build_search_index(entries)
    save_json(assets / "search-index.json", {"docs": search_docs, "total": len(search_docs)})

    partial_items = build_partial_search_index(entries)
    save_json(assets / "partial-search.json", {"items": partial_items, "total": len(partial_items)})
    print(f"Partial search index: {len(partial_items)} forms")

    print(f"Site built: {len(entries)} entries -> {SITE_DIR / 'index.html'}")
    print("Open site/index.html in your browser. For audio, run: python -m http.server 8080 --directory site")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())