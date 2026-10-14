"""Scrape welcome bonus terms for 3 casinos, structure them with Gemini, write JSON and the web page.

Usage: python scrape.py
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from build_page import DATA_PATH, write_page
from extractor import BonusExtractor, ExtractionError, find_ungrounded
from fetcher import FetchError, PoliteFetcher
from models import CasinoBonus
from source import BASE_URL, CASINO_SLUGS, ParseError, parse_review, review_url

DEFAULT_MODEL = "gemini-3.5-flash-lite"

log = logging.getLogger("scraper")


def scrape_casino(slug: str, fetcher: PoliteFetcher, extractor: BonusExtractor) -> CasinoBonus:
    url = review_url(slug)
    name, terms = parse_review(fetcher.get(url), slug)
    fields = extractor.extract(terms)
    notes = find_ungrounded(fields, terms)
    return CasinoBonus(
        **fields.model_dump(),
        casino=name,
        source_url=url,
        scraped_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        raw_terms=terms,
        needs_review=bool(notes),
        review_notes=notes,
    )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    load_dotenv()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
        return 2

    fetcher = PoliteFetcher()
    extractor = BonusExtractor(api_key, os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))

    records: list[CasinoBonus] = []
    failed: list[str] = []
    for slug in CASINO_SLUGS:
        try:
            record = scrape_casino(slug, fetcher, extractor)
        except (FetchError, ParseError, ExtractionError) as exc:
            log.error("%s: %s", slug, exc)
            failed.append(slug)
            continue
        records.append(record)
        log.info(
            "%s: %s | %sx | min %s%s",
            record.casino,
            record.welcome_bonus,
            record.wagering_multiplier,
            record.min_deposit.amount if record.min_deposit else None,
            f" | NEEDS REVIEW: {'; '.join(record.review_notes)}" if record.needs_review else "",
        )

    if not records:
        log.error("No casinos scraped, leaving %s unchanged", DATA_PATH)
        return 1

    output = {
        "source": BASE_URL,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "casinos": [record.model_dump() for record in records],
    }
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_page()
    log.info("Wrote %d casinos to %s and rebuilt the page", len(records), DATA_PATH)

    if failed:
        log.error("Failed: %s", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
