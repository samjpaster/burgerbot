"""
scrape_quotes.py
----------------
Fetches all characters from the Bob's Burgers API, then retrieves quote pages
via the Fandom MediaWiki API (api.php) — which is not blocked like direct HTML.

Quotes are parsed from {{Quote|text|context}} wikitext templates.

Output: D:\development\burgers\character_quotes.json

Schema:
{
  "Bob Belcher": {
    "wiki_url": "https://bobs-burgers.fandom.com/wiki/Bob_Belcher",
    "quotes": ["...", "..."]
  },
  ...
}

Run with:
    python scrape_quotes.py
"""

import asyncio
import json
import logging
import re
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scrape_quotes")

BASE_API = "https://bobsburgers-api.herokuapp.com"
FANDOM_API = "https://bobs-burgers.fandom.com/api.php"
OUTPUT_PATH = r"D:\development\burgers\character_quotes.json"

# Seconds between Fandom API requests (be polite)
REQUEST_DELAY = 0.4

# ---------------------------------------------------------------------------
# Parse {{Quote|text|context}} wikitext
# ---------------------------------------------------------------------------

# Matches {{Quote|first arg|...}} — captures only the first argument (the quote text)
_QUOTE_RE = re.compile(r"\{\{Quote\|([^|}]+)", re.IGNORECASE)


def extract_quotes_from_wikitext(wikitext: str) -> list[str]:
    quotes: list[str] = []
    for m in _QUOTE_RE.finditer(wikitext):
        text = m.group(1).strip()
        # Strip wiki markup: [[links]], ''italics'', '''bold''', <ref>...</ref>
        text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)  # [[link|label]] -> label
        text = re.sub(r"'{2,3}", "", text)                               # '' and '''
        text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", "", text)                             # any remaining HTML
        text = re.sub(r"\s+", " ", text).strip()
        if text and len(text) > 5:
            quotes.append(text)
    # Deduplicate, preserve order
    seen: set[str] = set()
    deduped: list[str] = []
    for q in quotes:
        if q not in seen:
            seen.add(q)
            deduped.append(q)
    return deduped


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

async def fetch_all_characters(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(f"{BASE_API}/characters")
    resp.raise_for_status()
    characters = resp.json()
    log.info(f"Fetched {len(characters)} characters from API")
    return characters


def wiki_page_title(wiki_url: str) -> str:
    """
    Convert a wiki URL like https://bobs-burgers.fandom.com/wiki/Bob_Belcher
    to the page title 'Bob_Belcher/Quotes' needed by the MediaWiki API.
    """
    # Everything after /wiki/
    match = re.search(r"/wiki/(.+)$", wiki_url)
    if not match:
        return ""
    return match.group(1) + "/Quotes"


async def fetch_quotes_for_character(
    client: httpx.AsyncClient, name: str, wiki_url: str
) -> list[str]:
    page_title = wiki_page_title(wiki_url)
    if not page_title:
        return []

    try:
        resp = await client.get(
            FANDOM_API,
            params={
                "action": "parse",
                "page": page_title,
                "prop": "wikitext",
                "format": "json",
            },
            timeout=15.0,
        )
        data = resp.json()

        if "error" in data:
            # missingtitle = no quotes page for this character
            code = data["error"].get("code", "")
            if code == "missingtitle":
                log.debug(f"  [{name}] No quotes page")
            else:
                log.warning(f"  [{name}] API error: {data['error']}")
            return []

        wikitext: str = data["parse"]["wikitext"]["*"]
        quotes = extract_quotes_from_wikitext(wikitext)
        log.info(f"  [{name}] {len(quotes)} quotes")
        return quotes

    except Exception as exc:
        log.warning(f"  [{name}] Error: {exc}")
        return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    log.info("=== scrape_quotes.py starting (MediaWiki API) ===")

    async with httpx.AsyncClient(timeout=20.0) as client:
        characters = await fetch_all_characters(client)

        result: dict[str, dict] = {}

        for i, char in enumerate(characters, 1):
            name: str = char.get("name", "Unknown").strip('"')
            wiki_url: str = char.get("wikiUrl", "")

            if not wiki_url:
                continue

            quotes = await fetch_quotes_for_character(client, name, wiki_url)
            if quotes:
                result[name] = {
                    "wiki_url": wiki_url,
                    "quotes": quotes,
                }

            if i % 50 == 0:
                log.info(f"  Progress: {i}/{len(characters)} characters processed, {len(result)} with quotes so far")

            await asyncio.sleep(REQUEST_DELAY)

    log.info(f"Done. {len(result)} characters with quotes collected.")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    log.info(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
