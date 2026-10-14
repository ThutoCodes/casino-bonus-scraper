import re

from pydantic import BaseModel, Field, field_validator

CURRENCY_SYMBOLS = {"£": "GBP", "€": "EUR", "$": "USD"}


class Money(BaseModel):
    amount: float
    currency: str = Field(description="ISO 4217 code, e.g. GBP, EUR, USD")

    @field_validator("currency")
    @classmethod
    def _to_iso_code(cls, value: str) -> str:
        return CURRENCY_SYMBOLS.get(value.strip(), value.strip().upper())


class BonusTerms(BaseModel):
    """The structured fields the language model extracts from free-text terms."""

    welcome_bonus: str | None = Field(
        description='Short summary of the welcome offer, e.g. "100% up to 500 EUR"'
    )
    wagering_multiplier: int | None = Field(
        description="Wagering requirement multiplier, e.g. 35 for 35x"
    )
    min_deposit: Money | None = Field(
        description="Minimum deposit needed to qualify for the welcome bonus"
    )

    @field_validator("welcome_bonus")
    @classmethod
    def _symbols_to_iso_codes(cls, value: str | None) -> str | None:
        """The prompt asks for "500 EUR", but models sometimes still write "€500"."""
        if value is None:
            return None
        return re.sub(
            r"([£€$])\s?(\d[\d,.]*)",
            lambda m: f"{m.group(2)} {CURRENCY_SYMBOLS[m.group(1)]}",
            value,
        )


class CasinoBonus(BonusTerms):
    casino: str
    source_url: str
    scraped_at: str
    raw_terms: str
    needs_review: bool
    review_notes: list[str]
