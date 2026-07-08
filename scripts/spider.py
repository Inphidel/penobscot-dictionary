#!/usr/bin/env python3
"""Crawl penobscot-dictionary.appspot.com and build entries.json."""

from __future__ import annotations

import argparse
import hashlib
import random
import re
import sys
import time
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from common import (
    BASE_URL,
    CRAWL_STATE_JSON,
    ENTRIES_JSON,
    LETTERS_JSON,
    ensure_dirs,
    entry_url,
    load_json,
    save_json,
)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "PenobscotDictionaryArchive/1.0 (language revitalization; local backup)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
})

ENTRY_LINK_RE = re.compile(r"/entry/(\d+)/")
LOOKUP_LINK_RE = re.compile(r"/entry_lookup/([^/]+)/(\d+)")


def fetch(url: str, retries: int = 5) -> str:
    for attempt in range(retries):
        try:
            resp = SESSION.get(url, timeout=30)
            if resp.status_code == 404:
                return ""
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt + random.uniform(0, 1))
    return ""


def polite_sleep(rate: float) -> None:
    time.sleep((1.0 / rate) + random.uniform(0, 0.3))


def discover_letters() -> list[tuple[str, str]]:
    """Return list of (letter_key, url_path_segment) from index page."""
    html = fetch(f"{BASE_URL}/entry/")
    soup = BeautifulSoup(html, "lxml")
    letters: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        m = LOOKUP_LINK_RE.match(a["href"])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            letters.append((unquote(m.group(1)), m.group(1)))
    return letters


def parse_list_page(html: str) -> tuple[list[dict], str | None]:
    """Extract entry stubs and next-page URL from a word-list page."""
    soup = BeautifulSoup(html, "lxml")
    stubs: list[dict] = []
    for a in soup.find_all("a", href=True):
        m = ENTRY_LINK_RE.fullmatch(a["href"])
        if m:
            stubs.append({"id": m.group(1), "headword": a.get_text(strip=True)})
    next_url = None
    for a in soup.select("a[aria-label='Next']"):
        href = a.get("href")
        if href:
            next_url = urljoin(BASE_URL, href)
            break
    return stubs, next_url


def crawl_letter(letter_key: str, path_segment: str, rate: float, state: dict) -> dict:
    """Crawl all pages for one browse letter. Returns letter -> [entry ids]."""
    letter_state = state.setdefault("letters", {}).setdefault(letter_key, {})
    if letter_state.get("completed"):
        return letter_state.get("entry_ids", [])

    start_url = f"{BASE_URL}/entry_lookup/{path_segment}/1"
    url = start_url
    visited_pages: set[str] = set()
    all_ids: list[str] = []
    page_num = 0

    while url and url not in visited_pages:
        visited_pages.add(url)
        page_num += 1
        html = fetch(url)
        if not html:
            break
        stubs, next_url = parse_list_page(html)
        for stub in stubs:
            all_ids.append(stub["id"])
            state.setdefault("stubs", {})[stub["id"]] = {
                "headword": stub["headword"],
                "browse_letters": list(set(
                    state.get("stubs", {}).get(stub["id"], {}).get("browse_letters", [])
                    + [letter_key]
                )),
            }
        letter_state["last_page"] = page_num
        letter_state["entry_ids"] = list(dict.fromkeys(all_ids))
        save_json(CRAWL_STATE_JSON, state)
        polite_sleep(rate)
        url = next_url

    letter_state["completed"] = True
    letter_state["entry_ids"] = list(dict.fromkeys(all_ids))
    save_json(CRAWL_STATE_JSON, state)
    return letter_state["entry_ids"]


def parse_entry_page(html: str, entry_id: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.select_one(".panel-heading h1")
    if not h1:
        return None

    entry: dict = {
        "id": entry_id,
        "headword": h1.get_text(strip=True),
        "source_url": entry_url(entry_id),
        "fields": {},
        "audio": [],
        "examples": [],
    }

    for p in soup.select(".entry_main_content p"):
        strong = p.find("strong")
        if not strong:
            continue
        label = strong.get_text(strip=True).strip().rstrip(":")
        value = p.get_text(strip=True)
        if label and value.lower().startswith(label.lower()):
            value = value[len(label):].lstrip(" :")
        if label:
            key = label.lower().replace(" ", "_").strip("_")
            entry["fields"][key] = value

    entry["part_of_speech"] = entry["fields"].get("part_of_speech", "")
    entry["sub_part_of_speech"] = entry["fields"].get("sub_part_of_speech", "")
    entry["english"] = entry["fields"].get("english_translation", "")

    audio_sources = soup.select(".audio_block audio source")
    for i, source in enumerate(audio_sources):
        src = source.get("src", "")
        if not src:
            continue
        filename = urlparse(src).path.rsplit("/", 1)[-1]
        audio_type = "guide" if filename.endswith("-gp.mp3") else "main"
        entry["audio"].append({
            "type": audio_type,
            "filename": filename,
            "remote_url": src,
            "local_path": f"audio/{filename}",
        })

    for table in soup.select("table.table-bordered"):
        headers = [th.get_text(strip=True) for th in table.select("thead th")]
        if not headers or "Penobscot" not in headers[0]:
            continue
        for tr in table.select("tbody tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if not cells or not any(cells):
                continue
            entry["examples"].append({
                "penobscot": cells[0] if len(cells) > 0 else "",
                "english": cells[1] if len(cells) > 1 else "",
                "part_of_speech": cells[2] if len(cells) > 2 else "",
            })

    entry["content_hash"] = hashlib.sha256(html.encode("utf-8")).hexdigest()[:16]
    return entry


def crawl_entries(entry_ids: list[str], entries: dict, state: dict, rate: float, force: bool) -> None:
    done = set(state.get("fetched_entries", []))
    todo = [eid for eid in entry_ids if force or eid not in done]

    for eid in tqdm(todo, desc="Fetching entries", unit="entry"):
        url = entry_url(eid)
        html = fetch(url)
        polite_sleep(rate)
        if not html:
            state.setdefault("failed_entries", []).append(eid)
            save_json(CRAWL_STATE_JSON, state)
            continue
        parsed = parse_entry_page(html, eid)
        if parsed:
            stub = state.get("stubs", {}).get(eid, {})
            parsed["browse_letters"] = stub.get("browse_letters", [])
            if not parsed["headword"] and stub.get("headword"):
                parsed["headword"] = stub["headword"]
            entries[eid] = parsed
            done.add(eid)
            state["fetched_entries"] = list(done)
            if len(done) % 10 == 0:
                save_json(ENTRIES_JSON, {"entries": entries, "meta": build_meta(entries)})
                save_json(CRAWL_STATE_JSON, state)
        else:
            state.setdefault("failed_entries", []).append(eid)
            save_json(CRAWL_STATE_JSON, state)

    save_json(ENTRIES_JSON, {"entries": entries, "meta": build_meta(entries)})
    save_json(CRAWL_STATE_JSON, state)


def build_meta(entries: dict) -> dict:
    with_audio = sum(1 for e in entries.values() if e.get("audio"))
    return {
        "total_entries": len(entries),
        "entries_with_audio": with_audio,
        "source": BASE_URL,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Spider the Penobscot Dictionary")
    parser.add_argument("--rate", type=float, default=2.0, help="Requests per second")
    parser.add_argument("--force", action="store_true", help="Re-fetch all entries")
    parser.add_argument("--letters-only", action="store_true", help="Only crawl index pages")
    parser.add_argument("--letter", type=str, help="Crawl only this letter key")
    args = parser.parse_args()

    ensure_dirs()
    state = load_json(CRAWL_STATE_JSON, {"stubs": {}, "letters": {}, "fetched_entries": []})
    catalog = load_json(ENTRIES_JSON, {"entries": {}, "meta": {}})
    entries: dict = catalog.get("entries", {})

    print("Discovering browse letters...")
    letters = discover_letters()
    print(f"Found {len(letters)} browse sections")

    if args.letter:
        letters = [(k, p) for k, p in letters if k == args.letter]
        if not letters:
            print(f"Letter not found: {args.letter}", file=sys.stderr)
            return 1

    all_ids: list[str] = []
    letter_map: dict = {}

    for letter_key, path_segment in tqdm(letters, desc="Crawling indexes"):
        ids = crawl_letter(letter_key, path_segment, args.rate, state)
        letter_map[letter_key] = ids
        all_ids.extend(ids)

    all_ids = list(dict.fromkeys(all_ids))
    save_json(LETTERS_JSON, letter_map)
    print(f"Discovered {len(all_ids)} unique entry IDs")

    if args.letters_only:
        return 0

    crawl_entries(all_ids, entries, state, args.rate, args.force)
    print(f"Done. {len(entries)} entries saved to {ENTRIES_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())