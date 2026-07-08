"""Part-of-speech and linguistic abbreviation glossary for Penobscot Dictionary UI."""

from __future__ import annotations

import html
import re

# Keys are matched case-insensitively when explaining; stored in canonical form.
POS_GLOSSARY: dict[str, str] = {
    # Column / general
    "POS": "Part of speech — the word's grammatical category in this dictionary (noun type, verb type, etc.)",
    "Part of Speech": "Extra label on an example form — often plural, conjunct, locative, etc.",

    # Noun classes
    "AN": "Animate noun — a person, animal, or other noun treated as grammatically animate",
    "INAN": "Inanimate noun — a thing, place, or idea treated as grammatically inanimate",
    "AN/INAN": "Animate or inanimate noun — can be used either way depending on context",

    # Verb classes (Algonquian transitivity)
    "AI": "Animate intransitive verb — verb with an animate subject (person/animal), no object",
    "II": "Inanimate intransitive verb — verb with an inanimate subject (thing), no object",
    "TA": "Transitive animate verb — verb whose object is animate (a person or animal)",
    "TI": "Transitive inanimate verb — verb whose object is inanimate (a thing)",
    "OTI": "Objective transitive inanimate — specialized transitive-inanimate verb form",
    "AI/II": "Animate or inanimate intransitive — can take either kind of subject",
    "SAI": "Secondary animate intransitive — derived or secondary AI verb form",
    "SII": "Secondary inanimate intransitive — derived or secondary II verb form",

    # Stem / morphology
    "Initial": "Verb initial — a root meaning element at the start of a verb stem (not a stand-alone word)",
    "inl.": "Ininitial — variant used inside a word stem rather than at the beginning",
    "ext. rt.": "Extended root — root element with an added extension",
    "redupl.": "Reduplication — part of the word is repeated for grammatical or expressive meaning",
    "prev.": "Prevocalic — form used before a vowel",
    "pren.": "Prenominal — form used before a noun",
    "prev. redupl.": "Prevocalic reduplication — repeated prevocalic element",
    "pren. and prev.": "Both prenominal and prevocalic forms exist",
    "prev., pren.": "Both prevocalic and prenominal forms",
    "pren., prev.": "Both prenominal and prevocalic forms",
    "prev. and pren.": "Both prevocalic and prenominal forms",

    # Particles and small words
    "pc.": "Particle — a small grammatical word that is not a full noun or verb",
    "emp. pc.": "Emphatic particle — adds emphasis",
    "deictic pc.": "Deictic particle — points to something (here, there, this, that)",
    "neg. pc.": "Negative particle — marks negation",
    "interog. pc.": "Interrogative particle — marks a question",
    "cpd. pc.": "Compound particle — particle made from combined elements",
    "part.": "Partitive — part-of-whole meaning (some of…)",
    "interj.": "Interjection — exclamation or call (not a full sentence)",
    "interj. vulg.": "Vulgar interjection — coarse or strong exclamation",
    "pron.": "Pronoun",
    "deictic": "Deictic — pointing word (here/there/this/that)",

    # Inflection / grammar labels on examples
    "pl.": "Plural — more than one",
    "sg.": "Singular — one",
    "dl.": "Dual — exactly two",
    "pl. excl.": "Plural exclusive — 'we' but not including the listener",
    "no pl.": "No plural — this word has no plural form listed",
    "c. conj.": "Conjunct order — verb form in dependent clauses (when, if, that…)",
    "conj.": "Conjunct — dependent-clause verb form",
    "subj.": "Subjunctive / subject-related form (depends on context in entry)",
    "imper.": "Imperative — command form",
    "obv.": "Obviative — alternate third person when two third persons are in play",
    "obv. sg.": "Obviative singular",
    "pass.": "Passive — action done to the subject",
    "dim.": "Diminutive — small, young, or affectionate form",
    "loc.": "Locative — form about location (at, on, in, to)",
    "distrib. loc.": "Distributive locative — spread across many places",
    "emp.": "Emphatic — stressed or emphasized form",
    "reflex.": "Reflexive — action directed back on the subject",
    "lit.": "Literally — literal or word-for-word sense",
    "lit": "Literally — literal or word-for-word sense",
    "arch.": "Archaic — older form, not in common use",
    "amb.": "Ambiguous — more than one analysis possible",
    "vulg.": "Vulgar — coarse or strong language",
    "coast.": "Coastal — coastal dialect variant",
    "prior.": "Prior — earlier or preceding form/context",
    "int. poss.": "Intimate possession — close kinship/possession form",

    # Relations between entries
    "Syn:": "Synonym — another entry with similar meaning",
    "Syn.": "Synonym — another entry with similar meaning",
    "syn:": "Synonym — another entry with similar meaning",
    "syn.": "Synonym — another entry with similar meaning",
    "ant.": "Antonym — opposite meaning",
    "Ant": "Antonym — opposite meaning",

    # Other headword tags
    "CARDINAL NUMERAL": "Cardinal numeral — counting number (one, two, three…)",
    "pers. N.": "Personal name",
    "Pers. N.": "Personal name",
    "b.t.w.": "By the way — editor's aside in the source manuscript",
    "† AN": "Animate noun (marked obsolete in the source)",
    "AN part.": "Animate participle — verb-like form from an animate verb",
    "_PN_": "Place name",
}

_LOOKUP: dict[str, str] = {k.lower(): v for k, v in POS_GLOSSARY.items()}

_SPLIT_RE = re.compile(r"\s*[·,;/]\s*|\s+and\s+")


def explain_pos(label: str) -> str:
    """Return a plain-text tooltip for a POS label (may combine several abbreviations)."""
    if not label or not label.strip():
        return ""
    raw = label.strip()
    if raw in POS_GLOSSARY:
        return POS_GLOSSARY[raw]
    low = raw.lower()
    if low in _LOOKUP:
        return _LOOKUP[low]

    parts = [p.strip() for p in _SPLIT_RE.split(raw) if p.strip()]
    if len(parts) > 1:
        chunks: list[str] = []
        for part in parts:
            tip = POS_GLOSSARY.get(part) or _LOOKUP.get(part.lower())
            if tip:
                chunks.append(f"{part}: {tip}")
            else:
                chunks.append(part)
        if any(POS_GLOSSARY.get(p) or _LOOKUP.get(p.lower()) for p in parts):
            return " — ".join(chunks)

    return ""


def pos_html(label: str, *, css_class: str = "pos-abbr") -> str:
    """Render a POS label with an HTML title tooltip when a glossary entry exists."""
    if not label or not str(label).strip():
        return ""
    text = str(label).strip()
    tip = explain_pos(text)
    safe_text = html.escape(text)
    if tip:
        safe_tip = html.escape(tip, quote=True)
        return f'<abbr class="{css_class}" title="{safe_tip}">{safe_text}</abbr>'
    return f'<span class="pos-plain">{safe_text}</span>'


def build_tooltips_js() -> str:
    """Client-side enhancer for dynamically rendered POS labels (search results, etc.)."""
    import json

    glossary_json = json.dumps(POS_GLOSSARY, ensure_ascii=False)
    return f"""/* Auto-generated — POS abbreviation tooltips */
(function() {{
  const GLOSSARY = {glossary_json};
  const LOOKUP = Object.fromEntries(Object.entries(GLOSSARY).map(([k, v]) => [k.toLowerCase(), v]));
  const SPLIT = /\\s*[·,;/]\\s*|\\s+and\\s+/;

  function explain(label) {{
    if (!label || !label.trim()) return '';
    const raw = label.trim();
    if (GLOSSARY[raw]) return GLOSSARY[raw];
    const low = raw.toLowerCase();
    if (LOOKUP[low]) return LOOKUP[low];
    const parts = raw.split(SPLIT).map(p => p.trim()).filter(Boolean);
    if (parts.length > 1) {{
      const chunks = parts.map(part => {{
        const tip = GLOSSARY[part] || LOOKUP[part.toLowerCase()];
        return tip ? part + ': ' + tip : part;
      }});
      if (parts.some(p => GLOSSARY[p] || LOOKUP[p.toLowerCase()])) return chunks.join(' — ');
    }}
    return '';
  }}

  function wrapAbbr(el, text, tip) {{
    if (el.querySelector('abbr.pos-abbr')) return;
    const abbr = document.createElement('abbr');
    abbr.className = 'pos-abbr';
    abbr.title = tip;
    abbr.textContent = text;
    el.textContent = '';
    el.appendChild(abbr);
    el.dataset.posEnhanced = '1';
  }}

  function enhanceEl(el) {{
    if (!el || el.dataset.posEnhanced) return;
    const text = (el.textContent || '').trim();
    if (!text) return;
    const tip = explain(text);
    if (!tip) {{
      el.dataset.posEnhanced = '1';
      return;
    }}
    if (el.tagName === 'ABBR' && el.classList.contains('pos-abbr')) {{
      el.title = tip;
      el.dataset.posEnhanced = '1';
      return;
    }}
    wrapAbbr(el, text, tip);
  }}

  function enhanceRoot(root) {{
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('.pos, .result-pos, td.pos, .guesser-pos, .example-pos').forEach(enhanceEl);
    root.querySelectorAll('.examples table tbody td:nth-child(3)').forEach(td => {{
      if ((td.textContent || '').trim()) enhanceEl(td);
    }});
  }}

  function init() {{
    enhanceRoot(document);
    const obs = new MutationObserver(muts => {{
      for (const m of muts) {{
        m.addedNodes.forEach(n => {{
          if (n.nodeType === 1) enhanceRoot(n);
        }});
      }}
    }});
    obs.observe(document.body, {{ childList: true, subtree: true }});
  }}

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
}})();
"""