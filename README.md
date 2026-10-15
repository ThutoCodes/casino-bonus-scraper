# Casino Bonus Scraper

Scrapes the welcome bonus for 3 online casinos from [Bojoko](https://www.bojoko.com), uses a language model (Google Gemini) to turn the free-text bonus terms into structured fields, writes them to `data/bonuses.json` and generates a mobile-friendly page from that JSON.

**Live page:** https://thutocodes.github.io/casino-bonus-scraper/

**Write-up** (production plan, AI notes, time taken): [WRITEUP.md](WRITEUP.md)

| Field | Example from the output |
|---|---|
| Welcome bonus | 50% up to 100 GBP |
| Wagering requirement (multiplier) | 10 |
| Minimum deposit | 20 GBP |
| Source URL | https://www.bojoko.com/casino/review/casumo/ |

## Install and run

Requires Python 3.11+ and a free Gemini API key from https://aistudio.google.com/apikey (no card needed).

```bash
git clone https://github.com/ThutoCodes/casino-bonus-scraper.git
cd casino-bonus-scraper
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
cp .env.example .env            # then put your key after GEMINI_API_KEY=
python scrape.py
```

`python scrape.py` is the single command: it fetches the pages, extracts the fields, writes `data/bonuses.json` and rebuilds `docs/index.html`. To rebuild only the page from the existing JSON, run `python build_page.py`.

Exit code is `0` when all casinos succeed and `1` if any failed, so a scheduler can alert on it.

Run the tests (offline, no API key needed):

```bash
pytest
```

## How it works

```
scrape.py      orchestrates the run, one casino at a time
  fetcher.py   robots.txt check, rate limit, stops on blocks
  source.py    Bojoko-specific: review URLs and where the bonus terms are in the HTML
  extractor.py Gemini call with a JSON schema, retries, and the grounding check
  models.py    Pydantic models for the output
build_page.py  data/bonuses.json -> docs/index.html
```

1. **Fetch.** `PoliteFetcher` reads `robots.txt` before any request, identifies itself with a descriptive User-Agent, waits at least 3 seconds between requests (or the site's `Crawl-delay` if longer) and gives up on 401/403/429 or a CAPTCHA/challenge page instead of trying to get around it.
2. **Parse.** Each Bojoko review page has one bonus card holding the headline offer, the bonus wagering, the minimum deposit for the bonus and the small print. That text is passed to the model as-is.
3. **Extract.** Gemini (`gemini-3.5-flash-lite`, temperature 0) returns JSON that must match the `BonusTerms` schema. The prompt tells it to use only the given text and return `null` for anything not stated. Temporary API errors (429/5xx) are retried with backoff; requests time out after 60s.
4. **Check.** `find_ungrounded` verifies that every number the model returned actually appears in the source text (and the minimum deposit appears as an amount of money, not just any number). Anything that cannot be matched marks the record `needs_review: true` with a note, and the page shows a "Needs review" label.
5. **Write.** Output goes to `data/bonuses.json` with `scraped_at` and the `raw_terms` the values came from, so every value can be checked by hand. If every casino fails, the previous JSON is left untouched.

## Why Bojoko

I checked several comparison sites before choosing a source:

| Site | Result |
|---|---|
| casino.guru | Rejected: returned 403 with a Cloudflare challenge. |
| casinotopsonline.com | Rejected: `robots.txt` disallows `*/bonuses`. |
| bojoko.com | Chosen: `robots.txt` allows `/casino/review/`, pages are plain server-rendered HTML, and each review has a consistent bonus card. |

Bojoko is a UK site, so all values are in GBP.

## Known limitations

- The casino list (`CASINO_SLUGS` in `source.py`) is fixed at 3. Scaling up would mean reading the list from Bojoko's sitemap or a database.
- The page parser depends on Bojoko's current CSS class (`card-toplist-row--bonus-card`). If they change their markup, `source.py` raises a `ParseError` for that casino rather than writing bad data.
- The grounding check catches invented numbers, not misread ones. Real example: 36Vegas offers spins only, and its card lists "bonus money 0x" and "bonus spins 2x". The model first returned 0x, which passed the check because "0x" is in the text. The prompt now says to use the wagering for what the offer actually gives, but a wrong-but-present number can still get through.
- Gemini's free tier is sometimes overloaded (503). The retries usually cover it; set `GEMINI_MODEL` in `.env` to switch model if needed.
