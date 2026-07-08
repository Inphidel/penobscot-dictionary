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
