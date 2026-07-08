let kinshipData = null;

function escapeHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function audioButtons(main, alt) {
  let h = '';
  if (main) h += `<button type="button" class="btn-play btn-play-sm" data-audio="../${main}" title="Play">&#9654;</button>`;
  if (alt) h += `<button type="button" class="btn-play btn-play-sm" data-audio="../${alt}" title="Play alt">&#9654;</button>`;
  return h ? `<div class="result-actions">${h}</div>` : '';
}

function renderCategoryButtons() {
  const wrap = document.getElementById('kinship-cats');
  if (!wrap || !kinshipData) return;

  const groups = {};
  for (const cat of kinshipData.categories) {
    const g = cat.group || 'Other';
    if (!groups[g]) groups[g] = [];
    groups[g].push(cat);
  }

  let html = '';
  for (const [group, cats] of Object.entries(groups)) {
    html += `<div class="kinship-group"><h3 class="kinship-group-title">${escapeHtml(group)}</h3><div class="kinship-btns">`;
    for (const cat of cats) {
      const n = (kinshipData.by_category[cat.id] || []).length;
      if (!n) continue;
      html += `<button type="button" class="kinship-btn" data-cat="${escapeHtml(cat.id)}" title="${escapeHtml(cat.description)}">${escapeHtml(cat.label)} <span class="kinship-count">${n}</span></button>`;
    }
    html += '</div></div>';
  }
  wrap.innerHTML = html;

  wrap.querySelectorAll('.kinship-btn').forEach(btn => {
    btn.addEventListener('click', () => showCategory(btn.dataset.cat));
  });
}

function showCategory(catId) {
  const cat = kinshipData.categories.find(c => c.id === catId);
  const items = kinshipData.by_category[catId] || [];
  const el = document.getElementById('kinship-results');
  if (!el || !cat) return;

  document.querySelectorAll('.kinship-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.cat === catId);
  });

  const hints = (cat.morph_hints || []).map(([frag, note]) =>
    `<li><code>${escapeHtml(frag)}</code> — ${escapeHtml(note)}</li>`
  ).join('');

  const cards = items.map(item => {
    const morph = (item.morph_notes || []).map(m =>
      `<li><code>${escapeHtml(m.fragment)}</code> — ${escapeHtml(m.note)}</li>`
    ).join('');
    const morphBlock = morph
      ? `<div class="kinship-morph"><span class="breakdown-label">Parts that may explain this</span><ul>${morph}</ul></div>`
      : '';
    const pos = item.part_of_speech
      ? `<span class="kinship-pos">${escapeHtml(item.part_of_speech)}</span>`
      : '';
    return `<article class="kinship-card">
      <p class="kinship-hw"><a href="../entry/${item.entry_id}.html">${escapeHtml(item.headword)}</a></p>
      <p class="kinship-en">${escapeHtml(item.english)}</p>
      ${pos}
      ${morphBlock}
      <div class="kinship-card-foot">
        <a class="btn-lab-link" href="index.html?q=${encodeURIComponent(item.headword)}">Detect in Lab &#8594;</a>
        <a class="btn-archive-link" href="../entry/${item.entry_id}.html">Archive &#8594;</a>
        ${audioButtons(item.audio_main, item.audio_alt)}
      </div>
    </article>`;
  }).join('');

  el.innerHTML = `
    <div class="kinship-results-head">
      <h3>${escapeHtml(cat.label)}</h3>
      <p class="muted">${escapeHtml(cat.description)} — ${items.length} archive ${items.length === 1 ? 'entry' : 'entries'}. Pattern hints are guesses, not grammar rules.</p>
      ${hints ? `<div class="kinship-hints"><span class="breakdown-label">Common patterns in this category</span><ul>${hints}</ul></div>` : ''}
    </div>
    <div class="kinship-cards">${cards || '<p class="muted">No entries.</p>'}</div>`;

  PenobscotAudio.bindPlayButtons(el);
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function init() {
  const resp = await fetch('../assets/kinship-index.json');
  kinshipData = await resp.json();
  renderCategoryButtons();

  const params = new URLSearchParams(location.search);
  const cat = params.get('kinship');
  if (cat && kinshipData.by_category[cat]) showCategory(cat);
}

init();