/** Lab Themes browser — semantic tags mined from English glosses. */
let semanticData = null;

function escapeHtmlTheme(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function themeAudioButtons(main, alt) {
  let h = '';
  if (main) h += `<button type="button" class="btn-play btn-play-sm" data-audio="../${main}" title="Play">&#9654;</button>`;
  if (alt) h += `<button type="button" class="btn-play btn-play-sm" data-audio="../${alt}" title="Play alt">&#9654;</button>`;
  return h ? `<div class="result-actions">${h}</div>` : '';
}

function renderThemeButtons() {
  const wrap = document.getElementById('theme-cats');
  if (!wrap || !semanticData) return;

  const tags = semanticData.tags || [];
  const byTag = semanticData.by_tag || {};
  const groups = {};
  for (const t of tags) {
    const n = (byTag[t.id] || []).length;
    if (!n) continue;
    // Skip pure meta markers in browse (still used for scoring)
    if (t.group === 'meta' && t.id !== 'place_name') continue;
    const g = t.group || 'other';
    if (!groups[g]) groups[g] = [];
    groups[g].push({ ...t, count: n });
  }

  const groupMeta = {};
  for (const g of (semanticData.groups || [])) {
    groupMeta[g.id] = g;
  }

  // Prefer group catalog order
  const order = (semanticData.groups || []).map(g => g.id);
  const groupIds = [
    ...order.filter(id => groups[id]),
    ...Object.keys(groups).filter(id => !order.includes(id)),
  ];

  let html = '';
  for (const gid of groupIds) {
    const cats = groups[gid].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
    const gLabel = (groupMeta[gid] && groupMeta[gid].label) || gid;
    html += `<div class="kinship-group"><h3 class="kinship-group-title">${escapeHtmlTheme(gLabel)}</h3><div class="kinship-btns">`;
    for (const cat of cats) {
      html += `<button type="button" class="kinship-btn" data-theme="${escapeHtmlTheme(cat.id)}" title="${escapeHtmlTheme(cat.description || '')}">${escapeHtmlTheme(cat.label)} <span class="kinship-count">${cat.count}</span></button>`;
    }
    html += '</div></div>';
  }
  wrap.innerHTML = html || '<p class="muted">No theme tags loaded.</p>';

  wrap.querySelectorAll('.kinship-btn').forEach(btn => {
    btn.addEventListener('click', () => showTheme(btn.dataset.theme));
  });
}

function showTheme(tagId) {
  const tag = (semanticData.tags || []).find(t => t.id === tagId);
  const items = (semanticData.by_tag && semanticData.by_tag[tagId]) || [];
  const el = document.getElementById('theme-results');
  if (!el || !tag) return;

  document.querySelectorAll('#theme-cats .kinship-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.theme === tagId);
  });

  const cards = items.map(item => {
    const pos = item.part_of_speech
      ? `<span class="kinship-pos">${escapeHtmlTheme(item.part_of_speech)}</span>`
      : '';
    const conf = item.confidence
      ? `<span class="badge badge-lab">${escapeHtmlTheme(item.confidence)}</span>`
      : '';
    return `<article class="kinship-card">
      <p class="kinship-hw"><a href="../entry/${item.entry_id}.html">${escapeHtmlTheme(item.headword)}</a> ${conf}</p>
      <p class="kinship-en">${escapeHtmlTheme(item.english)}</p>
      ${pos}
      <div class="kinship-card-foot">
        <a class="btn-lab-link" href="index.html?q=${encodeURIComponent(item.headword)}">Detect in Lab &#8594;</a>
        <a class="btn-archive-link" href="../entry/${item.entry_id}.html">Archive &#8594;</a>
        ${themeAudioButtons(item.audio_main, item.audio_alt)}
      </div>
    </article>`;
  }).join('');

  el.innerHTML = `
    <div class="kinship-results-head">
      <h3>${escapeHtmlTheme(tag.label)}</h3>
      <p class="muted">${escapeHtmlTheme(tag.description || '')} — ${items.length} archive ${items.length === 1 ? 'entry' : 'entries'}. Tags are guesses from English glosses, not official categories.</p>
      <p class="theme-practice"><a class="btn-games-link" href="../games/listen3.html?theme=${encodeURIComponent(tagId)}">Practice in Listen-3 &#8594;</a></p>
    </div>
    <div class="kinship-cards">${cards || '<p class="muted">No entries.</p>'}</div>`;

  if (typeof PenobscotAudio !== 'undefined') PenobscotAudio.bindPlayButtons(el);
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  const url = new URL(location.href);
  url.searchParams.set('theme', tagId);
  history.replaceState(null, '', url);
}

async function initThemes() {
  try {
    const resp = await fetch('../assets/semantic-tags.json');
    if (!resp.ok) return;
    semanticData = await resp.json();
    renderThemeButtons();

    const params = new URLSearchParams(location.search);
    const theme = params.get('theme');
    if (theme && semanticData.by_tag && semanticData.by_tag[theme]) {
      showTheme(theme);
    }
  } catch (e) {
    console.warn('semantic tags load failed', e);
  }
}

initThemes();
