"""Bojoko-specific knowledge: which pages to fetch and where the bonus terms live in them."""

from bs4 import BeautifulSoup

BASE_URL = "https://www.bojoko.com"
CASINO_SLUGS = ["casumo", "10bet", "36vegas"]


class ParseError(Exception):
    pass


def review_url(slug: str) -> str:
    return f"{BASE_URL}/casino/review/{slug}/"


def parse_review(html: str, slug: str) -> tuple[str, str]:
    """Return (casino name, free-text bonus terms) from a Bojoko review page."""
    soup = BeautifulSoup(html, "html.parser")
    return _casino_name(soup, slug), _bonus_terms(soup, slug)


def _casino_name(soup: BeautifulSoup, slug: str) -> str:
    heading = soup.find("h1")
    if heading:
        name = heading.get_text(" ", strip=True)
        for suffix in (" review", " Review"):
            name = name.split(suffix)[0]
        if name:
            return name.strip()
    return slug.replace("-", " ").title()


def _bonus_terms(soup: BeautifulSoup, slug: str) -> str:
    # The bonus card holds the headline offer, wagering, minimum deposit and the small print.
    card = soup.select_one(".card-toplist-row--bonus-card")
    if card:
        return card.get_text(" ", strip=True).replace("Play here »", "").strip()

    terms = soup.find(lambda tag: tag.name == "p" and "Significant Terms" in tag.get_text())
    if terms:
        return terms.get_text(" ", strip=True)

    raise ParseError(f"no bonus terms found on the review page for '{slug}'")
