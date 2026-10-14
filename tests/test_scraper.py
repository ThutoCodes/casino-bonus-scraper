import pytest

from extractor import find_ungrounded
from models import BonusTerms, Money
from source import ParseError, parse_review

TERMS = (
    "Significant Terms: 18+. New customers only. Opt-in required. 50% Deposit Bonus up to £100 "
    "on first deposit. Min deposit £20. 10x wagering on bonus amount. Max £5 per bet."
)

REVIEW_HTML = """
<html><body>
<h1>10bet Casino review</h1>
<div class="card-toplist-row card-toplist-row--bonus-card">
  <a>Play here »</a>
  <dl><dt>1st deposit bonus</dt><dd>100%/£25</dd>
      <dt>Minimum deposit for bonus</dt><dd>£10</dd></dl>
  <small class="card-toplist-row__footer">Wager bonus 10x within 3 days on slots. 18+.</small>
</div>
</body></html>
"""


def test_parse_review_extracts_name_and_bonus_card():
    name, terms = parse_review(REVIEW_HTML, "10bet")

    assert name == "10bet Casino"
    assert "100%/£25" in terms
    assert "Wager bonus 10x" in terms
    assert "Play here" not in terms


def test_parse_review_falls_back_to_significant_terms():
    html = f"<div class='box__content'><p><sup><em>Significant Terms:</em></sup> {TERMS[19:]}</p></div>"

    _, terms = parse_review(html, "casumo")

    assert "10x wagering" in terms


def test_parse_review_raises_when_no_terms():
    with pytest.raises(ParseError):
        parse_review("<html><body><h1>Empty</h1></body></html>", "empty")


def test_grounded_values_are_not_flagged():
    fields = BonusTerms(
        welcome_bonus="50% up to 100 GBP",
        wagering_multiplier=10,
        min_deposit=Money(amount=20, currency="GBP"),
    )

    assert find_ungrounded(fields, TERMS) == []


def test_invented_values_are_flagged():
    fields = BonusTerms(
        welcome_bonus="100% up to 500 GBP",
        wagering_multiplier=35,
        min_deposit=Money(amount=10, currency="GBP"),
    )

    notes = find_ungrounded(fields, TERMS)

    assert "wagering 35x not found in terms" in notes
    assert "welcome bonus value 500 not found in terms" in notes
    assert "minimum deposit 10.0 not found in terms" in notes


def test_zero_wagering_is_flagged_when_terms_only_mention_10x():
    fields = BonusTerms(
        welcome_bonus="50% up to 100 GBP",
        wagering_multiplier=0,
        min_deposit=Money(amount=20, currency="GBP"),
    )

    assert find_ungrounded(fields, TERMS) == [
        "wagering returned as 0 but terms do not say 'no wagering'"
    ]


def test_currency_symbols_are_normalised_to_iso_codes():
    fields = BonusTerms(
        welcome_bonus="100% up to £25",
        wagering_multiplier=10,
        min_deposit=Money(amount=10, currency="£"),
    )

    assert fields.welcome_bonus == "100% up to 25 GBP"
    assert fields.min_deposit.currency == "GBP"


def test_missing_fields_are_flagged():
    fields = BonusTerms(welcome_bonus=None, wagering_multiplier=None, min_deposit=None)

    assert len(find_ungrounded(fields, TERMS)) == 3
