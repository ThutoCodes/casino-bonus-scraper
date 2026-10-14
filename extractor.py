import logging
import re
import time

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from models import BonusTerms

# Gemini's free tier returns 429/503 under load; these are temporary, so a short backoff helps.
RETRYABLE_STATUSES = {429, 500, 503, 504}
MAX_ATTEMPTS = 4
RETRY_BASE_SECONDS = 5
REQUEST_TIMEOUT_MS = 60_000

log = logging.getLogger("scraper")

PROMPT = """You extract casino welcome bonus details from the terms text below.

Rules:
- Use only information stated in the text. If a field is not stated, return null. Never guess.
- welcome_bonus: short summary like "100% up to 500 EUR". Add free spins if they are part of
  the welcome offer, e.g. "100% up to 500 EUR + 50 free spins". Use ISO currency codes.
- wagering_multiplier: the multiplier for the welcome bonus wagering, e.g. "35x" -> 35.
  Use the wagering that applies to what the offer actually gives: if the offer is only free
  spins, use the wagering on spin winnings, even if a "bonus money" line says 0x.
  Return 0 only if the whole offer is stated to have no wagering.
- min_deposit: the minimum deposit needed to qualify for the welcome bonus, with an ISO 4217
  currency code (GBP for £, EUR for €, USD for $).

Terms text:
\"\"\"{terms}\"\"\"
"""


class ExtractionError(Exception):
    pass


class BonusExtractor:
    """Turns free-text bonus terms into structured fields using Gemini."""

    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS)
        )
        self._model = model

    def extract(self, terms: str) -> BonusTerms:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BonusTerms,
            temperature=0,
        )
        response = self._generate(PROMPT.format(terms=terms), config)
        if not response.text:
            raise ExtractionError("Gemini returned an empty response")
        try:
            return BonusTerms.model_validate_json(response.text)
        except ValidationError as exc:
            raise ExtractionError(f"Gemini output did not match the schema: {exc}") from exc

    def _generate(self, prompt: str, config: types.GenerateContentConfig) -> types.GenerateContentResponse:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return self._client.models.generate_content(
                    model=self._model, contents=prompt, config=config
                )
            except errors.APIError as exc:
                if exc.code not in RETRYABLE_STATUSES or attempt == MAX_ATTEMPTS:
                    raise ExtractionError(f"Gemini request failed: {exc}") from exc
                wait = RETRY_BASE_SECONDS * 2 ** (attempt - 1)
                log.warning("Gemini returned %s, retrying in %ss (attempt %d/%d)", exc.code, wait, attempt, MAX_ATTEMPTS)
                time.sleep(wait)


def find_ungrounded(fields: BonusTerms, terms: str) -> list[str]:
    """List extracted values that cannot be found in the source text, so they get flagged.

    The model is told to use only the given text, but it can still invent a plausible number.
    This catches that by checking each number it returned against the text it was given.
    """
    notes = []
    numbers_in_terms = set(_numbers(terms))

    if fields.welcome_bonus is None:
        notes.append("welcome bonus not stated in terms")
    else:
        for number in _numbers(fields.welcome_bonus):
            if number not in numbers_in_terms:
                notes.append(f"welcome bonus value {number} not found in terms")

    if fields.wagering_multiplier is None:
        notes.append("wagering requirement not stated in terms")
    elif fields.wagering_multiplier == 0:
        if not re.search(r"no[\s-]wagering|wager[\s-]free|\b0\s*x\b", terms, re.I):
            notes.append("wagering returned as 0 but terms do not say 'no wagering'")
    elif not re.search(rf"\b{fields.wagering_multiplier}\s*(x|times)\b", terms, re.I):
        notes.append(f"wagering {fields.wagering_multiplier}x not found in terms")

    if fields.min_deposit is None:
        notes.append("minimum deposit not stated in terms")
    elif _format_number(fields.min_deposit.amount) not in _money_amounts(terms):
        notes.append(f"minimum deposit {fields.min_deposit.amount} not found in terms")

    return notes


def _money_amounts(text: str) -> set[str]:
    """Numbers written as money, e.g. "£20" or "20 EUR", so "10x wagering" does not count as 10."""
    symbol_first = re.findall(r"[£€$]\s?(\d[\d,]*(?:\.\d+)?)", text)
    code_after = re.findall(r"(\d[\d,]*(?:\.\d+)?)\s?(?:GBP|EUR|USD)\b", text, re.I)
    return {_format_number(float(n.replace(",", ""))) for n in symbol_first + code_after}


def _numbers(text: str) -> list[str]:
    return [_format_number(float(n.replace(",", ""))) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]


def _format_number(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)
