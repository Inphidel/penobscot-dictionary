/**
 * Listen-3: hear Penobscot audio, pick the correct English (1 of 3).
 * Deck from theme tags that have recordings. Lab / study only.
 */
(function () {
  const MIN_DECK = 3;
  let data = null;
  let deck = [];
  let queue = [];
  let index = 0;
  let correct = 0;
  let answered = false;
  let sessionSize = 10;
  let selectedTags = new Set();

  const $ = (id) => document.getElementById(id);

  function esc(s) {
    return (s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function pickDistractors(item, pool, n) {
    const others = pool.filter((x) => x.entry_id !== item.entry_id);
    // Prefer different short English text
    const unique = [];
    const seen = new Set([item.english_short.toLowerCase()]);
    for (const o of shuffle(others)) {
      const key = (o.english_short || '').toLowerCase();
      if (!key || seen.has(key)) continue;
      seen.add(key);
      unique.push(o);
      if (unique.length >= n) break;
    }
    return unique.slice(0, n);
  }

  function audioUrl(path) {
    if (!path) return '';
    if (path.startsWith('../') || path.startsWith('http') || path.startsWith('audio/')) {
      return path.startsWith('audio/') ? '../' + path : path;
    }
    return '../' + path;
  }

  function show(el, on) {
    if (!el) return;
    el.hidden = !on;
  }

  function renderPicker() {
    const wrap = $('listen3-tags');
    if (!wrap || !data) return;

    const groups = data.groups || [];
    const tags = (data.tags || []).filter((t) => (t.count || 0) >= MIN_DECK);
    const byGroup = {};
    for (const t of tags) {
      const g = t.group || 'other';
      if (!byGroup[g]) byGroup[g] = [];
      byGroup[g].push(t);
    }

    const groupMeta = {};
    for (const g of groups) groupMeta[g.id] = g;

    const order = groups.map((g) => g.id).filter((id) => byGroup[id]);
    for (const id of Object.keys(byGroup)) {
      if (!order.includes(id)) order.push(id);
    }

    let html = '';
    for (const gid of order) {
      const list = byGroup[gid].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
      const gLabel = (groupMeta[gid] && groupMeta[gid].label) || gid;
      html += `<div class="listen3-group"><h3 class="kinship-group-title">${esc(gLabel)}</h3><div class="kinship-btns">`;
      for (const t of list) {
        const active = selectedTags.has(t.id) ? ' active' : '';
        html += `<button type="button" class="kinship-btn listen3-tag-btn${active}" data-tag="${esc(t.id)}" title="${esc(t.description || '')}">${esc(t.label)} <span class="kinship-count">${t.count}</span></button>`;
      }
      html += '</div></div>';
    }
    wrap.innerHTML = html || '<p class="muted">No theme decks with enough audio yet.</p>';

    wrap.querySelectorAll('.listen3-tag-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.tag;
        if (selectedTags.has(id)) selectedTags.delete(id);
        else selectedTags.add(id);
        btn.classList.toggle('active', selectedTags.has(id));
        updateStartState();
      });
    });
  }

  function buildDeckFromSelection() {
    if (!data) return [];
    const decks = data.decks || {};
    if (!selectedTags.size) {
      // all playable unique
      const map = new Map();
      for (const items of Object.values(decks)) {
        for (const it of items || []) {
          if (it.audio && !map.has(it.entry_id)) map.set(it.entry_id, it);
        }
      }
      return [...map.values()];
    }
    const map = new Map();
    for (const tid of selectedTags) {
      for (const it of decks[tid] || []) {
        if (it.audio && !map.has(it.entry_id)) map.set(it.entry_id, it);
      }
    }
    return [...map.values()];
  }

  function updateStartState() {
    const n = buildDeckFromSelection().length;
    const info = $('listen3-deck-info');
    const start = $('listen3-start');
    if (info) {
      if (!selectedTags.size) {
        info.textContent = `No theme selected — Start will use all playable words (${n} with audio). Or pick one or more themes.`;
      } else {
        const labels = (data.tags || [])
          .filter((t) => selectedTags.has(t.id))
          .map((t) => t.label);
        info.textContent = `${labels.join(', ')} — ${n} words with audio`;
      }
    }
    if (start) start.disabled = n < MIN_DECK;
  }

  function startSession() {
    deck = buildDeckFromSelection();
    if (deck.length < MIN_DECK) return;

    const sizeSel = $('listen3-size');
    sessionSize = sizeSel ? parseInt(sizeSel.value, 10) : 10;
    if (!sessionSize || sessionSize < 1) sessionSize = deck.length;

    queue = shuffle(deck).slice(0, Math.min(sessionSize, deck.length));
    index = 0;
    correct = 0;
    answered = false;

    show($('listen3-setup'), false);
    show($('listen3-play'), true);
    show($('listen3-done'), false);
    renderRound();
  }

  function renderRound() {
    answered = false;
    const item = queue[index];
    if (!item) {
      endSession();
      return;
    }

    const progress = $('listen3-progress');
    if (progress) progress.textContent = `${index + 1} / ${queue.length}`;

    const scoreEl = $('listen3-score');
    if (scoreEl) scoreEl.textContent = `${correct} correct`;

    const feedback = $('listen3-feedback');
    if (feedback) {
      feedback.hidden = true;
      feedback.className = 'listen3-feedback';
      feedback.innerHTML = '';
    }

    const nextBtn = $('listen3-next');
    if (nextBtn) nextBtn.hidden = true;

    const playBtn = $('listen3-play-btn');
    if (playBtn) {
      playBtn.dataset.audio = audioUrl(item.audio);
      playBtn.classList.remove('playing', 'loading');
    }

    // Build 3 choices
    let distractors = pickDistractors(item, deck, 2);
    if (distractors.length < 2) {
      // fall back to full catalog
      const all = [];
      for (const items of Object.values(data.decks || {})) all.push(...(items || []));
      distractors = pickDistractors(item, all, 2);
    }

    const choices = shuffle([
      { item, correct: true },
      ...distractors.map((d) => ({ item: d, correct: false })),
    ]);

    const choicesEl = $('listen3-choices');
    if (choicesEl) {
      choicesEl.innerHTML = choices
        .map(
          (c, i) =>
            `<button type="button" class="listen3-choice" data-i="${i}" data-correct="${c.correct ? '1' : '0'}" data-eid="${esc(c.item.entry_id)}">${esc(c.item.english_short || c.item.english)}</button>`
        )
        .join('');
      choicesEl.querySelectorAll('.listen3-choice').forEach((btn) => {
        btn.addEventListener('click', () => onChoice(btn, item));
      });
    }

    // Auto-play after short delay
    setTimeout(() => {
      if (playBtn && typeof PenobscotAudio !== 'undefined') {
        PenobscotAudio.play(playBtn.dataset.audio, playBtn);
      }
    }, 200);
  }

  function onChoice(btn, item) {
    if (answered) return;
    answered = true;
    const isCorrect = btn.dataset.correct === '1';
    if (isCorrect) correct += 1;

    $('listen3-choices').querySelectorAll('.listen3-choice').forEach((b) => {
      b.disabled = true;
      if (b.dataset.correct === '1') b.classList.add('is-correct');
      else if (b === btn && !isCorrect) b.classList.add('is-wrong');
    });

    const scoreEl = $('listen3-score');
    if (scoreEl) scoreEl.textContent = `${correct} correct`;

    const feedback = $('listen3-feedback');
    if (feedback) {
      feedback.hidden = false;
      feedback.className = 'listen3-feedback ' + (isCorrect ? 'ok' : 'bad');
      const full = item.english || item.english_short || '';
      feedback.innerHTML = `
        <p class="listen3-fb-title">${isCorrect ? 'Correct' : 'Not quite'}</p>
        <p class="listen3-fb-hw"><span class="font-word">${esc(item.headword)}</span></p>
        <p class="listen3-fb-en">${esc(full)}</p>
        <p class="listen3-fb-links">
          <a class="btn-archive-link" href="../entry/${esc(item.entry_id)}.html">Archive entry &#8594;</a>
          <a class="btn-lab-link" href="../lab/index.html?q=${encodeURIComponent(item.headword)}">Lab &#8594;</a>
        </p>`;
    }

    const nextBtn = $('listen3-next');
    if (nextBtn) {
      nextBtn.hidden = false;
      nextBtn.textContent = index + 1 >= queue.length ? 'See results' : 'Next';
    }
  }

  function endSession() {
    show($('listen3-play'), false);
    show($('listen3-done'), true);
    const total = queue.length;
    const pct = total ? Math.round((100 * correct) / total) : 0;
    const summary = $('listen3-summary');
    if (summary) {
      summary.innerHTML = `<p class="listen3-summary-score">${correct} / ${total} correct (${pct}%)</p>
        <p class="muted">Theme practice only — verify with archive audio and speakers.</p>`;
    }
    try {
      const key = 'penobscot-listen3-last';
      localStorage.setItem(
        key,
        JSON.stringify({ correct, total, tags: [...selectedTags], at: Date.now() })
      );
    } catch (_) { /* ignore */ }
  }

  function backToSetup() {
    if (typeof PenobscotAudio !== 'undefined' && PenobscotAudio.stopActive) {
      try { PenobscotAudio.stopActive(); } catch (_) {}
    }
    show($('listen3-setup'), true);
    show($('listen3-play'), false);
    show($('listen3-done'), false);
    updateStartState();
  }

  async function init() {
    try {
      const resp = await fetch('../assets/listen3-decks.json');
      data = await resp.json();
    } catch (e) {
      const setup = $('listen3-setup');
      if (setup) setup.innerHTML = '<p class="muted">Could not load game decks. Rebuild the site or check assets/listen3-decks.json.</p>';
      return;
    }

    renderPicker();
    updateStartState();

    // URL ?theme=dog
    const params = new URLSearchParams(location.search);
    const theme = params.get('theme');
    if (theme && data.decks && data.decks[theme]) {
      selectedTags.add(theme);
      renderPicker();
      updateStartState();
    }

    const start = $('listen3-start');
    if (start) start.addEventListener('click', startSession);

    const playBtn = $('listen3-play-btn');
    if (playBtn) {
      playBtn.addEventListener('click', () => {
        const url = playBtn.dataset.audio;
        if (url && typeof PenobscotAudio !== 'undefined') PenobscotAudio.play(url, playBtn);
      });
    }

    const nextBtn = $('listen3-next');
    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        index += 1;
        if (index >= queue.length) endSession();
        else renderRound();
      });
    }

    const again = $('listen3-again');
    if (again) again.addEventListener('click', startSession);

    const change = $('listen3-change');
    if (change) change.addEventListener('click', backToSetup);

    const clear = $('listen3-clear');
    if (clear) {
      clear.addEventListener('click', () => {
        selectedTags.clear();
        renderPicker();
        updateStartState();
      });
    }
  }

  init();
})();
