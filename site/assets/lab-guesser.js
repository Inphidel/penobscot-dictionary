let forms = [];
let prefixes = [];
let baseWords = [];
let sentences = [];
let englishIndex = [];
/** @type {{tags?: Array, keywordToTags?: Map}} */
let semanticCatalog = { tags: [], keywordToTags: new Map() };

const STOP_WORDS = new Set([
  'the', 'and', 'for', 'are', 'was', 'were', 'with', 'that', 'this', 'from', 'has', 'have',
  'been', 'being', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'not', 'but',
  'or', 'if', 'then', 'than', 'into', 'onto', 'upon', 'about', 'after', 'before', 'while',
  'when', 'where', 'what', 'which', 'who', 'whom', 'whose', 'there', 'here', 'also', 'very',
  'just', 'only', 'even', 'still', 'such', 'some', 'any', 'all', 'each', 'every', 'both',
  'too', 'so', 'as', 'at', 'by', 'in', 'on', 'of', 'to', 'an', 'a', 'is', 'am', 'be', 'do',
  'does', 'did', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'me', 'him', 'them', 'us',
]);

const PERSON_PATTERNS = [
  { re: /\b(i'm|i am)\b/i, label: 'first person singular', enHint: 'i', prefixes: ['nəta', 'nət', 'nə'] },
  { re: /\b(i)\b/i, label: 'first person singular', enHint: 'i', prefixes: ['nəta', 'nət', 'nə'] },
  { re: /\b(we're|we are|we)\b/i, label: 'first person plural', enHint: 'we', prefixes: ['kilə', 'nə'] },
  { re: /\b(you're|you are|you)\b/i, label: 'second person', enHint: 'you', prefixes: ['k', 'el'] },
  { re: /\b(they're|they are|they)\b/i, label: 'third person plural', enHint: 'they', prefixes: ['m', 'w'] },
  { re: /\b(he's|he is|he)\b/i, label: 'third person (he)', enHint: 'he', prefixes: [] },
  { re: /\b(she's|she is|she)\b/i, label: 'third person (she)', enHint: 'she', prefixes: [] },
  { re: /\b(it's|it is|it)\b/i, label: 'third person / obviative', enHint: 'that it', prefixes: [] },
];

function norm(s) {
  return (s || '').normalize('NFC').trim();
}

function foldAscii(s) {
  const MAP = { č: 'c', Č: 'c', ə: 'e', Ə: 'e', α: 'a', Α: 'a', 'ʷ': 'w', '́': '', '̀': '', 'ˊ': '', 'ˋ': '', '‑': '-', '→': '' };
  let t = norm(s);
  for (const [k, v] of Object.entries(MAP)) t = t.split(k).join(v);
  t = t.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  return t.toLowerCase().replace(/[^a-z0-9\-]+/g, '');
}

function lev(a, b) {
  a = foldAscii(a);
  b = foldAscii(b);
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
      dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost);
    }
  }
  return dp[m][n];
}

function escapeHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function audioButtons(main, alt) {
  let h = '';
  if (main) h += `<button type="button" class="btn-play btn-play-sm" data-audio="../${main}" title="Play recording 1">&#9654;</button>`;
  if (alt) h += `<button type="button" class="btn-play btn-play-sm" data-audio="../${alt}" title="Play recording 2">&#9654;</button>`;
  return h ? `<div class="result-actions">${h}</div>` : '';
}

function detectionBanner() {
  return `<p class="detection-banner"><span class="badge badge-lab">System detection</span> These are guesses from dictionary patterns — not official Penobscot. Verify with audio and speakers.</p>`;
}

function looksEnglish(query) {
  const q = norm(query);
  if (!q) return false;
  if (/[čəαʷ́̀ˊ]|kʷ|hʷ/i.test(q)) return false;
  const lower = q.toLowerCase();
  if (PERSON_PATTERNS.some(p => p.re.test(lower))) return true;
  const words = lower.split(/\s+/).filter(w => w.length > 1);
  if (words.length >= 2 && /^[a-zA-Z\s.,!?'"()-]+$/.test(q)) {
    const content = words.filter(w => !STOP_WORDS.has(w.replace(/[^a-z']/g, '')));
    return content.length >= 1;
  }
  return false;
}

function tokenizeEnglish(query) {
  return [...new Set(
    query.toLowerCase()
      .replace(/[^a-z'\s]/g, ' ')
      .split(/\s+/)
      .map(w => w.replace(/^'|'$/g, ''))
      .filter(w => w.length >= 3 && !STOP_WORDS.has(w))
  )];
}

function detectPerson(query) {
  const lower = query.toLowerCase();
  for (const p of PERSON_PATTERNS) {
    if (p.re.test(lower)) return p;
  }
  return null;
}

function prefixRuleFor(pfx) {
  return prefixes.find(x => foldAscii(x.prefix) === foldAscii(pfx) || x.prefix === pfx);
}

function entryForms(entryId) {
  return forms.filter(f => f.entry_id === entryId);
}

function exampleMatchesPerson(ex, person) {
  if (!person) return false;
  const en = (ex.english || '').toLowerCase().trim();
  const hint = person.enHint;
  if (hint && (en.startsWith(hint) || en.startsWith(hint + '...'))) return true;
  if (person.prefixes && person.prefixes.length) {
    const fold = ex.form_ascii || foldAscii(ex.form);
    return person.prefixes.some(p => fold.startsWith(foldAscii(p)));
  }
  return false;
}

function pickConjugatedForm(entryId, person) {
  const candidates = entryForms(entryId).filter(f => f.kind === 'example');
  if (person) {
    const matched = candidates.filter(ex => exampleMatchesPerson(ex, person));
    if (matched.length) {
      matched.sort((a, b) => {
        const af = a.form_ascii || foldAscii(a.form);
        const bf = b.form_ascii || foldAscii(b.form);
        if (person.prefixes && person.prefixes.length) {
          const aP = person.prefixes.findIndex(p => af.startsWith(foldAscii(p)));
          const bP = person.prefixes.findIndex(p => bf.startsWith(foldAscii(p)));
          return (aP < 0 ? 99 : aP) - (bP < 0 ? 99 : bP);
        }
        return 0;
      });
      return { form: matched[0], source: 'archive_example', confidence: 'medium' };
    }
  }
  const head = entryForms(entryId).find(f => f.kind === 'headword');
  if (head) return { form: head, source: 'headword_fallback', confidence: 'low' };
  return null;
}

function buildPrefixReasoning(formRec, person) {
  const steps = [];
  if (!formRec || !person) return steps;
  const fold = formRec.form_ascii || foldAscii(formRec.form);
  for (const p of (person.prefixes || []).sort((a, b) => b.length - a.length)) {
    if (fold.startsWith(foldAscii(p))) {
      const rule = prefixRuleFor(p);
      steps.push(`Archive example starts with <code>${escapeHtml(rule?.prefix || p)}</code> — ${escapeHtml(rule?.hint || 'observed prefix')} (seen ${rule?.count || '?'}× in examples)`);
      break;
    }
  }
  if (formRec.english) {
    steps.push(`Example English label in archive: “${escapeHtml(formRec.english)}”`);
  }
  return steps;
}

function buildKeywordTagMap(tags) {
  const map = new Map();
  for (const t of tags || []) {
    for (const kw of (t.keywords || [])) {
      const k = kw.toLowerCase();
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(t);
    }
  }
  return map;
}

/** Infer theme tags from an English query via keyword map. */
function tagsFromQuery(query, tokens) {
  const found = new Map(); // tag_id -> tag meta
  const words = new Set(tokens.map(t => t.toLowerCase()));
  // also split full query for short keywords
  for (const w of query.toLowerCase().replace(/[^a-z'\s]/g, ' ').split(/\s+/)) {
    if (w.length >= 3) words.add(w);
  }
  for (const w of words) {
    const hits = semanticCatalog.keywordToTags.get(w) || [];
    for (const t of hits) {
      if (!found.has(t.id)) found.set(t.id, t);
    }
  }
  return [...found.values()];
}

function tagBonus(queryTags, entryTags, entryTagMeta) {
  if (!queryTags.length || !entryTags || !entryTags.length) return { bonus: 0, shared: [] };
  const entrySet = new Set(entryTags);
  const metaById = {};
  for (const m of (entryTagMeta || [])) metaById[m.id] = m;

  let bonus = 0;
  const shared = [];
  for (const qt of queryTags) {
    if (!entrySet.has(qt.id)) continue;
    const spec = qt.specificity || (metaById[qt.id] && metaById[qt.id].specificity) || 'theme';
    if (spec === 'lemma') bonus += 4;
    else if (spec === 'meta') bonus += 2;
    else bonus += 2;
    shared.push(qt);
  }
  // Same group without exact tag: small nudge
  if (!shared.length && queryTags.length) {
    const entryGroups = new Set((entryTagMeta || []).map(m => m.group));
    for (const qt of queryTags) {
      if (entryGroups.has(qt.group)) {
        bonus += 1;
        break;
      }
    }
  }
  return { bonus: Math.min(bonus, 12), shared };
}

function scoreEnglishEntry(entry, tokens, queryTags) {
  let score = 0;
  const matched = [];
  const enLow = entry.english.toLowerCase();
  for (const t of tokens) {
    if (entry.tokens.includes(t)) {
      score += 3;
      matched.push(t);
    } else if (enLow.includes(t)) {
      score += 1;
      matched.push(t);
    }
  }
  const { bonus, shared } = tagBonus(queryTags || [], entry.tags || [], entry.tag_meta || []);
  score += bonus;
  // Allow pure tag matches when tokens miss (e.g. query "moose" tags lemma)
  if (!matched.length && !bonus) return null;
  if (!matched.length && bonus && !score) score = bonus;
  const coverage = matched.length / Math.max(tokens.length, 1);
  return { entry, score, matched, coverage, tagBonus: bonus, sharedTags: shared };
}

function matchArchiveSentences(query, tokens) {
  const hits = [];
  for (const s of sentences) {
    const sTokens = tokenizeEnglish(s.english);
    const overlap = tokens.filter(t => sTokens.includes(t));
    if (overlap.length < 2 && tokens.length >= 2) continue;
    if (overlap.length < 1) continue;
    const score = overlap.length * 3 + (s.english.toLowerCase().includes(query.toLowerCase().slice(0, 12)) ? 5 : 0);
    hits.push({ ...s, overlap, score });
  }
  hits.sort((a, b) => b.score - a.score);
  return hits.slice(0, 5);
}

function detectFromEnglish(query) {
  const tokens = tokenizeEnglish(query);
  const person = detectPerson(query);
  const queryTags = tagsFromQuery(query, tokens);
  if (!tokens.length && !person && !queryTags.length) {
    return { query, suggestions: [], sentenceHits: [], person, tokens, queryTags: [] };
  }

  const scored = [];
  for (const entry of englishIndex) {
    const hit = scoreEnglishEntry(entry, tokens, queryTags);
    if (hit) scored.push(hit);
  }
  scored.sort((a, b) => b.score - a.score || (b.tagBonus || 0) - (a.tagBonus || 0) || b.coverage - a.coverage);

  const suggestions = [];
  const seen = new Set();
  for (const { entry, score, matched, coverage, tagBonus: tb, sharedTags } of scored.slice(0, 12)) {
    if (seen.has(entry.entry_id)) continue;
    seen.add(entry.entry_id);
    const picked = pickConjugatedForm(entry.entry_id, person);
    if (!picked) continue;

    const reasoning = [];
    const wordPart = matched.length
      ? `your words: ${matched.map(escapeHtml).join(', ')}`
      : 'theme tags only';
    reasoning.push(`Matched dictionary entry <a href="../entry/${entry.entry_id}.html">${escapeHtml(entry.headword)}</a> — “${escapeHtml(entry.english)}” (${wordPart})`);
    if (sharedTags && sharedTags.length) {
      reasoning.push(`Shared themes: ${sharedTags.map(t => escapeHtml(t.label || t.id)).join(', ')} (+${tb} score from tags)`);
    }
    if (person) {
      reasoning.push(`You wrote “${escapeHtml(person.label)}” — searching archive examples for that person`);
      reasoning.push(...buildPrefixReasoning(picked.form, person));
    } else {
      reasoning.push('No “I / he / she / we” detected — showing dictionary headword form');
    }
    if (picked.source === 'headword_fallback') {
      reasoning.push('No matching conjugated example found — using base headword only');
    }

    const conf = picked.confidence === 'medium' && coverage >= 0.4 ? 'medium' : 'low';
    suggestions.push({
      penobscot: picked.form.form,
      entry_id: entry.entry_id,
      headword: entry.headword,
      archiveEnglish: entry.english,
      matchedWords: matched,
      sharedTags: sharedTags || [],
      person,
      reasoning,
      confidence: conf,
      audio_main: picked.form.audio_main,
      audio_alt: picked.form.audio_alt,
      score,
    });
  }

  const sentenceHits = matchArchiveSentences(query, tokens);
  return { query, tokens, person, suggestions, sentenceHits, queryTags };
}

function findStemMatch(stem) {
  const s = foldAscii(stem);
  if (!s || s.length < 2) return null;
  let best = null;

  function consider(f, match, score, extra) {
    if (!best || score > best.score) {
      best = {
        entry_id: f.entry_id,
        headword: f.headword,
        english: f.english,
        part_of_speech: f.part_of_speech,
        audio_main: f.audio_main,
        audio_alt: f.audio_alt,
        archiveForm: f.form,
        match,
        score,
        ...(extra || {}),
      };
    }
  }

  for (const f of forms) {
    if (f.kind !== 'headword') continue;
    const hw = f.form_ascii || foldAscii(f.headword);
    if (hw === s) consider(f, 'exact', 100);
    if (hw.startsWith('a') && hw.length > 3) {
      const bare = hw.slice(1);
      if (bare === s) consider(f, 'theme_a', 92, { themeNote: 'Headword adds initial a-' });
      else if (bare.length >= 4 && s.length >= 4) {
        const d = lev(s, bare);
        if (d <= 2) consider(f, 'theme_a_fuzzy', 80 - d * 5, {
          themeNote: 'Close to headword without initial a-',
          endingNote: endingDiff(s, bare),
        });
      }
    }
    if (hw.includes(s) && s.length >= 4) consider(f, 'contains', 65);
    if (s.includes(hw) && hw.length >= 4) consider(f, 'inside', 60);
    const d = lev(s, hw);
    if (d > 0 && d <= 2 && s.length >= 4) {
      consider(f, 'fuzzy', 50 - d * 5, { endingNote: endingDiff(s, hw) });
    }
  }
  return best;
}

function endingDiff(a, b) {
  const x = foldAscii(a);
  const y = foldAscii(b);
  let i = 0;
  while (i < x.length && i < y.length && x[i] === y[i]) i++;
  const tailA = x.slice(i);
  const tailB = y.slice(i);
  if (!tailA && !tailB) return '';
  if (tailA && tailB) return `Differs at end: …${tailA} vs …${tailB}`;
  if (tailA) return `Extra ending on form: …${tailA}`;
  return `Missing ending vs headword: …${tailB}`;
}

function findPrefixForQuery(qFold) {
  const list = [...prefixes].sort((a, b) => (b.prefix_ascii || foldAscii(b.prefix)).length - (a.prefix_ascii || foldAscii(a.prefix)).length);
  for (const rule of list) {
    const p = rule.prefix_ascii || foldAscii(rule.prefix);
    if (p && qFold.startsWith(p) && qFold.length > p.length + 1) {
      return { rule, len: p.length };
    }
  }
  return null;
}

function breakdown(query) {
  const display = norm(query);
  const qFold = foldAscii(display);
  if (!qFold || qFold.length < 2) return null;

  const exactForms = forms.filter(f => (f.form_ascii || foldAscii(f.form)) === qFold || norm(f.form) === display);
  let bestParse = null;

  const prefixHit = findPrefixForQuery(qFold);
  if (prefixHit) {
    const stemFold = qFold.slice(prefixHit.len);
    const stemMatch = findStemMatch(stemFold);
    const pDisp = prefixHit.rule.prefix;
    const stemPart = display.startsWith(pDisp)
      ? display.slice(pDisp.length)
      : (stemMatch?.archiveForm || stemFold);
    const score = (stemMatch ? stemMatch.score : 10) + prefixHit.len * 3;
    bestParse = { prefix: prefixHit.rule, stemPart, stemFold, stemMatch, score };
  }

  if (!bestParse || (bestParse.score < 50 && !bestParse.stemMatch)) {
    const whole = findStemMatch(qFold);
    if (whole && (!bestParse || whole.score + 5 >= bestParse.score)) {
      bestParse = { prefix: null, stemPart: display, stemFold: qFold, stemMatch: whole, score: whole.score };
    }
  }

  const archiveForm = exactForms[0]?.form || (bestParse?.stemMatch?.archiveForm) || null;
  return { query: display, qFold, exactForms, bestParse, archiveForm };
}

function cleanEnglish(s) {
  return (s || '').replace(/\.{3,}/g, '').replace(/[,;]+$/g, '').trim();
}

function composeMeaning(bd) {
  const parse = bd.bestParse;
  if (!parse) return null;
  const sm = parse.stemMatch;
  if (sm) return { text: cleanEnglish(sm.english), source: 'archive_entry', confidence: sm.match === 'exact' ? 'high' : 'medium' };
  return null;
}

function renderEnglishDetection(det) {
  const el = document.getElementById('breakdown-results');
  if (!el) return;

  if (!det.suggestions.length && !det.sentenceHits.length) {
    el.innerHTML = `
      <div class="breakdown-card breakdown-empty">
        ${detectionBanner()}
        <h3 class="breakdown-title">No Penobscot detected</h3>
        <p class="breakdown-query">${escapeHtml(det.query)}</p>
        <p class="muted">The system could not match your English to dictionary entries. Try fewer words, use Search for official definitions, or type a Penobscot form you heard (plain letters OK).</p>
      </div>`;
    return;
  }

  let html = detectionBanner();

  if (det.sentenceHits.length) {
    html += `<div class="breakdown-card"><h3 class="breakdown-title">Archive sentences that look similar</h3>
      <p class="muted">Full examples from the dictionary — closest English overlap with what you typed.</p>`;
    for (const s of det.sentenceHits.slice(0, 3)) {
      html += `<div class="sentence-hit">
        <p class="breakdown-meaning-text">${escapeHtml(s.english)}</p>
        <p class="breakdown-pb-result">${escapeHtml(s.form.replace(/^→/, ''))}</p>
        <p class="breakdown-meta">From entry <a href="../entry/${s.entry_id}.html">${escapeHtml(s.headword)}</a> — matched words: ${s.overlap.map(escapeHtml).join(', ')}</p>
      </div>`;
    }
    html += '</div>';
  }

  if (det.queryTags && det.queryTags.length) {
    html += `<p class="tag-chips"><span class="muted">Detected themes:</span> ${
      det.queryTags.map(t => `<span class="tag-chip">${escapeHtml(t.label || t.id)}</span>`).join('')
    }</p>`;
  }

  for (const sug of det.suggestions.slice(0, 4)) {
    const tagChips = (sug.sharedTags && sug.sharedTags.length)
      ? `<p class="tag-chips">${sug.sharedTags.map(t => `<span class="tag-chip">${escapeHtml(t.label || t.id)}</span>`).join('')}</p>`
      : '';
    html += `
      <div class="breakdown-card confidence-${sug.confidence}">
        <h3 class="breakdown-title">Possible Penobscot</h3>
        <p class="breakdown-pb-result">${escapeHtml(sug.penobscot)}</p>
        <div class="breakdown-meaning">
          <span class="breakdown-label">What we think you meant</span>
          <p class="breakdown-meaning-text">${escapeHtml(det.query)}</p>
          <p class="breakdown-meta">Built from archive entry: “${escapeHtml(sug.archiveEnglish)}”</p>
          ${tagChips}
        </div>
        <div class="breakdown-reasoning">
          <span class="breakdown-label">Why the system chose this</span>
          <ul class="breakdown-reasons">${sug.reasoning.map(r => `<li>${r}</li>`).join('')}</ul>
        </div>
        <div class="breakdown-foot">
          <a class="btn-archive-link" href="../entry/${sug.entry_id}.html">Official archive entry &#8594;</a>
          ${audioButtons(sug.audio_main, sug.audio_alt)}
        </div>
      </div>`;
  }

  el.innerHTML = html;
  PenobscotAudio.bindPlayButtons(el);
}

function renderPenobscotBreakdown(bd) {
  const el = document.getElementById('breakdown-results');
  if (!el) return;
  if (!bd) {
    el.innerHTML = '';
    return;
  }

  const typedNote = bd.qFold !== foldAscii(bd.query)
    ? `<p class="breakdown-typed">You typed plain letters — matched as <code>${escapeHtml(bd.qFold)}</code>${bd.archiveForm ? ` → archive form <code>${escapeHtml(bd.archiveForm)}</code>` : ''}</p>`
    : '';

  const exact = bd.exactForms || [];
  const exactHead = exact.find(f => f.kind === 'headword');
  if (exactHead) {
    el.innerHTML = `
      <div class="breakdown-card">
        ${detectionBanner()}
        <div class="breakdown-meaning">
          <span class="breakdown-label">What this might mean</span>
          <p class="breakdown-meaning-text">${escapeHtml(cleanEnglish(exactHead.english))}</p>
        </div>
        ${typedNote}
        <p class="breakdown-meta">Dictionary headword (official archive form)</p>
        <p class="breakdown-pb-result">${escapeHtml(exactHead.headword)}</p>
        <div class="breakdown-foot">
          <a class="btn-archive-link" href="../entry/${exactHead.entry_id}.html">View in archive &#8594;</a>
          ${audioButtons(exactHead.audio_main, exactHead.audio_alt)}
        </div>
      </div>`;
    PenobscotAudio.bindPlayButtons(el);
    return;
  }

  const parse = bd.bestParse;
  if (!parse) {
    el.innerHTML = `
      <div class="breakdown-card breakdown-empty">
        ${detectionBanner()}
        <h3 class="breakdown-title">Could not detect a meaning</h3>
        <p class="breakdown-query">${escapeHtml(bd.query)}</p>
        ${typedNote}
        <p class="muted">No prefix pattern or dictionary stem matched. Try English words instead, a shorter piece, or Search.</p>
      </div>`;
    return;
  }

  const meaning = composeMeaning(bd);
  const sm = parse.stemMatch;
  const unknowns = [];
  const parts = [];
  let visual = `<span class="bd-seg bd-whole">${escapeHtml(bd.archiveForm || bd.query)}</span>`;

  if (parse.prefix) {
    const pDisp = parse.prefix.prefix;
    visual = `<span class="bd-seg bd-prefix">${escapeHtml(pDisp)}</span><span class="bd-plus">+</span><span class="bd-seg bd-stem">${escapeHtml(parse.stemPart)}</span>`;
    parts.push(`<div class="breakdown-piece">
      <span class="breakdown-label">Prefix (observed in archive)</span>
      <code class="breakdown-code">${escapeHtml(pDisp)}</code>
      <span class="breakdown-hint">Might mean: ${escapeHtml(parse.prefix.hint)} — seen ${parse.prefix.count}× in examples</span>
      ${parse.prefix.sample ? `<span class="breakdown-sample">Sample: ${escapeHtml(parse.prefix.sample)}</span>` : ''}
    </div>`);
  }

  if (sm) {
    parts.push(`<div class="breakdown-piece">
      <span class="breakdown-label">Stem — from dictionary</span>
      <code class="breakdown-code">${escapeHtml(sm.headword)}</code>
      <span class="breakdown-hint">Archive meaning: ${escapeHtml(cleanEnglish(sm.english))}</span>
      ${sm.themeNote ? `<span class="breakdown-meta">${escapeHtml(sm.themeNote)}</span>` : ''}
      ${sm.endingNote ? `<span class="breakdown-meta">${escapeHtml(sm.endingNote)}</span>` : ''}
    </div>`);
  } else {
    parts.push(`<div class="breakdown-piece">
      <span class="breakdown-label">Stem</span>
      <code class="breakdown-code">${escapeHtml(parse.stemPart)}</code>
      <span class="breakdown-hint muted">No dictionary headword matched for this piece</span>
    </div>`);
    unknowns.push('Which dictionary word this stem comes from');
  }

  if (!meaning) unknowns.push('Overall English meaning');

  const meaningBlock = meaning
    ? `<div class="breakdown-meaning">
        <span class="breakdown-label">What this might mean</span>
        <p class="breakdown-meaning-text">${escapeHtml(meaning.text)}</p>
        <p class="breakdown-meta">Guessed from dictionary stem${parse.prefix ? ' + prefix pattern' : ''} — not a full translation</p>
      </div>`
    : `<div class="breakdown-meaning"><p class="muted">Could not guess an English meaning for this form.</p></div>`;

  el.innerHTML = `
    <div class="breakdown-card">
      ${detectionBanner()}
      ${meaningBlock}
      ${typedNote}
      <div class="breakdown-visual">${visual}</div>
      <div class="breakdown-parts">${parts.join('')}</div>
      ${unknowns.length ? `<div class="breakdown-unknown"><span class="breakdown-label">What we don&apos;t know</span><ul class="breakdown-unknowns">${unknowns.map(u => `<li>${escapeHtml(u)}</li>`).join('')}</ul></div>` : ''}
      ${sm ? `<div class="breakdown-foot"><a class="btn-archive-link" href="../entry/${sm.entry_id}.html">Official archive entry &#8594;</a>${audioButtons(sm.audio_main, sm.audio_alt)}</div>` : ''}
    </div>`;
  PenobscotAudio.bindPlayButtons(el);
}

function analyzePenobscot(query) {
  const q = norm(query);
  const qFold = foldAscii(q);
  if (!qFold || qFold.length < 2) return [];
  const hits = [];
  const seen = new Set();

  function push(item) {
    const key = item.entry_id + '|' + item.match_type + '|' + item.matched_form;
    if (seen.has(key)) return;
    seen.add(key);
    hits.push(item);
  }

  for (const f of forms) {
    const ff = f.form_ascii || foldAscii(f.form);
    if (ff === qFold || norm(f.form) === q) {
      push({
        match_type: f.kind === 'headword' ? 'exact_headword' : 'exact_example',
        confidence: 'high',
        matched_form: f.form,
        entry_id: f.entry_id,
        headword: f.headword,
        english: f.english,
        part_of_speech: f.part_of_speech,
        example_pos: f.example_pos,
        note: f.kind === 'example' ? 'Exact match in dictionary examples' : 'Exact headword match',
        audio_main: f.audio_main,
        audio_alt: f.audio_alt,
      });
    }
  }

  const prefixList = prefixes.map(p => p.prefix).sort((a, b) => b.length - a.length);
  for (const p of prefixList) {
    const pf = foldAscii(p);
    if (qFold.startsWith(pf) && qFold.length > pf.length + 2) {
      const stem = qFold.slice(pf.length);
      for (const f of forms) {
        if (f.kind !== 'headword') continue;
        const hw = f.form_ascii || foldAscii(f.headword);
        if (hw === stem || hw.includes(stem) || stem.includes(hw)) {
          const rule = prefixes.find(x => x.prefix === p);
          push({
            match_type: 'prefix_stripped',
            confidence: 'medium',
            matched_form: q,
            entry_id: f.entry_id,
            headword: f.headword,
            english: f.english,
            part_of_speech: f.part_of_speech,
            example_pos: '',
            note: `Removed prefix "${p}"${rule && rule.hint ? ' (' + rule.hint + ')' : ''}`,
            audio_main: f.audio_main,
            audio_alt: f.audio_alt,
          });
        }
      }
    }
  }

  for (const f of forms) {
    const form = f.form_ascii || foldAscii(f.form);
    if (form.length < 3) continue;
    if (form.includes(qFold) || qFold.includes(form)) {
      if (form === qFold) continue;
      push({
        match_type: 'substring',
        confidence: 'medium',
        matched_form: f.form,
        entry_id: f.entry_id,
        headword: f.headword,
        english: f.english,
        part_of_speech: f.part_of_speech,
        example_pos: f.example_pos,
        note: 'Partial form overlap',
        audio_main: f.audio_main,
        audio_alt: f.audio_alt,
      });
    }
  }

  for (const f of forms) {
    if (f.kind !== 'headword') continue;
    const d = lev(qFold, f.form_ascii || foldAscii(f.headword));
    if (d > 0 && d <= 2 && qFold.length >= 4) {
      push({
        match_type: 'similar_spelling',
        confidence: 'low',
        matched_form: f.headword,
        entry_id: f.entry_id,
        headword: f.headword,
        english: f.english,
        part_of_speech: f.part_of_speech,
        example_pos: '',
        note: `Similar spelling (edit distance ${d})`,
        audio_main: f.audio_main,
        audio_alt: f.audio_alt,
      });
    }
  }

  const order = { high: 0, medium: 1, low: 2 };
  hits.sort((a, b) => (order[a.confidence] - order[b.confidence]) || a.headword.localeCompare(b.headword));
  return hits.slice(0, 25);
}

function renderMoreMatches(hits, mode) {
  const el = document.getElementById('guesser-results');
  const sub = document.getElementById('guesser-subhead');
  if (sub) {
    sub.textContent = mode === 'english' ? 'Other dictionary words your English matched' : 'More possible matches';
  }
  if (!hits.length) {
    el.innerHTML = `<p class="muted">${mode === 'english' ? 'No other word matches.' : 'No matches. Try English words, or a shorter Penobscot piece.'}</p>`;
    return;
  }
  el.innerHTML = hits.map(h => `
    <div class="guesser-card confidence-${h.confidence}">
      <div class="guesser-card-head">
        <span class="badge badge-lab">${escapeHtml(h.confidence)} confidence</span>
        <span class="guesser-type">${escapeHtml((h.match_type || 'word_match').replace(/_/g, ' '))}</span>
      </div>
      ${h.matched_form ? `<p class="guesser-matched">${escapeHtml(h.matched_form)}</p>` : ''}
      ${h.penobscot ? `<p class="guesser-matched">${escapeHtml(h.penobscot)}</p>` : ''}
      ${h.note ? `<p class="guesser-note">${escapeHtml(h.note)}</p>` : ''}
      <p class="guesser-entry">
        <a href="../entry/${h.entry_id}.html">${escapeHtml(h.headword)}</a>
        <span class="guesser-en">${escapeHtml(h.english)}</span>
      </p>
      <div class="guesser-card-foot">
        <a class="btn-archive-link" href="../entry/${h.entry_id}.html">Official archive entry &#8594;</a>
        ${audioButtons(h.audio_main, h.audio_alt)}
      </div>
    </div>
  `).join('');
  PenobscotAudio.bindPlayButtons(el);
}

function renderAffixTable() {
  const wrap = document.getElementById('affix-table-wrap');
  if (!wrap || !prefixes.length) return;
  wrap.innerHTML = `<table class="affix-table">
    <thead><tr><th>Prefix</th><th>Hint</th><th>Seen</th><th>Sample</th></tr></thead>
    <tbody>${prefixes.slice(0, 20).map(p => `
      <tr><td><code>${escapeHtml(p.prefix)}</code></td><td>${escapeHtml(p.hint)}</td><td>${p.count}</td><td class="sample">${escapeHtml(p.sample)}</td></tr>
    `).join('')}</tbody>
  </table>`;
}

function setModeLabel(mode) {
  const label = document.getElementById('guesser-mode');
  if (label) {
    label.textContent = mode === 'english'
      ? 'Detected: English → possible Penobscot'
      : 'Detected: Penobscot form → possible meaning';
  }
}

async function init() {
  const [formsResp, affixResp, baseResp, sentResp, enResp, tagsResp] = await Promise.all([
    fetch('../assets/guesser-forms.json'),
    fetch('../assets/affix-patterns.json'),
    fetch('../assets/base-words.json'),
    fetch('../assets/sentence-examples.json'),
    fetch('../assets/english-index.json'),
    fetch('../assets/semantic-tags.json').catch(() => null),
  ]);
  forms = (await formsResp.json()).forms || [];
  prefixes = (await affixResp.json()).prefixes || [];
  baseWords = (await baseResp.json()).words || [];
  sentences = (await sentResp.json()).sentences || [];
  englishIndex = (await enResp.json()).entries || [];
  if (tagsResp && tagsResp.ok) {
    try {
      const tagData = await tagsResp.json();
      semanticCatalog.tags = tagData.tags || [];
      semanticCatalog.keywordToTags = buildKeywordTagMap(semanticCatalog.tags);
    } catch (_) { /* optional */ }
  }

  const form = document.getElementById('guesser-form');
  const input = document.getElementById('guesser-q');
  const status = document.getElementById('guesser-status');

  renderAffixTable();

  const run = (q) => {
    const trimmed = norm(q);
    if (trimmed.length < 2) {
      document.getElementById('breakdown-results').innerHTML = '';
      document.getElementById('guesser-results').innerHTML = '';
      status.textContent = '';
      return;
    }

    if (looksEnglish(trimmed)) {
      setModeLabel('english');
      const det = detectFromEnglish(trimmed);
      renderEnglishDetection(det);
      const more = det.suggestions.slice(4).map(s => ({
        ...s,
        english: s.archiveEnglish,
        note: `Matched: ${s.matchedWords.join(', ')}`,
        match_type: 'english_word_match',
      }));
      status.textContent = det.suggestions.length
        ? `${det.suggestions.length} possible Penobscot form${det.suggestions.length === 1 ? '' : 's'} detected`
        : '';
      renderMoreMatches(more, 'english');
    } else {
      setModeLabel('penobscot');
      renderPenobscotBreakdown(breakdown(trimmed));
      const hits = analyzePenobscot(trimmed);
      status.textContent = hits.length ? `${hits.length} more possible match${hits.length === 1 ? '' : 'es'}` : '';
      renderMoreMatches(hits, 'penobscot');
    }
  };

  form.addEventListener('submit', e => {
    e.preventDefault();
    run(input.value);
  });

  const params = new URLSearchParams(location.search);
  const prefill = params.get('q');
  if (prefill) {
    input.value = prefill;
    run(prefill);
  }
}

init();