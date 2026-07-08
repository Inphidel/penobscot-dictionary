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
  t = t.normalize('NFD').replace(/[̀-ͯ]/g, '');
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
  return /[čəαʷ́̀]|kʷ|hʷ|nə/i.test(query) || !/^[a-zA-Z\s.,;!?'"()-]+$/.test(query);
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
        query.toLowerCase().split(/\s+/).filter(Boolean).forEach(term => {
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
  const base = (headword || 'penobscot-word').replace(/[<>:"/\\|?*]/g, '').trim() || 'penobscot-word';
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
