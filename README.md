# Penobscot Dictionary — Local Archive & Lab

A complete local backup of the [Penobscot Dictionary](https://penobscot-dictionary.appspot.com/entry/) with searchable browsable interface, offline audio, and experimental Lab tools — built for language learning.

> Data sourced from the Penobscot Dictionary (Penobscot Indian Nation, University of Maine, American Philosophical Society). Based on the manuscript of Frank T. Siebert.

## Archive status

| | Count |
|--|--|
| Dictionary entries | **10,113** |
| Entries with audio | **9,354** |
| Audio files (.mp3) | **10,396** |
| Browse sections | **26** |

## Install your own mirror (Option A — pre-built site)

This repo includes a **ready-to-serve** `site/` folder (HTML, search indexes, Lab tools, and audio under `site/audio/`).

```bash
git clone https://github.com/Inphidel/penobscot-dictionary.git
cd penobscot-dictionary

# Audio must be served over http/https (not file://)
python -m http.server 8080 --directory site
# Open http://localhost:8080
```

On a Linux VPS, point nginx or Apache at the `site/` directory. Example URL: `https://yoursite.example/penobscot/`.

### Update an existing mirror

```bash
cd penobscot-dictionary
git pull
# Static site — no restart needed if using nginx; new files are live immediately
```

## What’s in the repo

| Path | Purpose |
|------|---------|
| `site/` | **Public website** — search, browse, entries, Lab, audio |
| `data/entries.json` | Full dictionary catalog (machine-readable) |
| `data/lab/` | Mined patterns for Lab tools |
| `scripts/` | Crawl, rebuild, and mining tools |
| `entries/` | One markdown file per word (optional study format) |

Local development keeps a separate `audio/` folder (junctioned to `site/audio/`). Only `site/audio/` is committed so mirrors get one copy of the recordings.

## Re-crawl or rebuild from scratch

```bash
pip install -r requirements.txt

# If rebuilding: link audio for scripts (Linux/macOS)
ln -sf site/audio audio

python scripts/spider.py          # crawl official site (resumable)
python scripts/finish.py          # audio + markdown + site
# or: python scripts/build_site.py
```

## Using the site

- **Search** — Penobscot or English; partial Penobscot fragments show amber Lab matches
- **Browse** — by sound/letter (a, č, kʷ, root, …)
- **Lab** — English → possible Penobscot; Penobscot → meaning; kinship/perspective browse
- **Audio** — play, loop, save recordings on entry and search results
- **POS labels** — hover abbreviations (AI, INAN, Initial, …) for explanations

Archive pages (green) are official dictionary copies. Lab pages (amber) are **experimental pattern guesses** — verify with audio and speakers.

## Lab rebuild only

```bash
python scripts/mine_affixes.py
python scripts/mine_kinship.py
python scripts/build_site.py
```

## Attribution

Archive text and audio are not edited by this project. Each entry links to the official Penobscot Dictionary. Lab tools are local experiments, not Penobscot Nation publications.