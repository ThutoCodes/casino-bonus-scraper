import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

USER_AGENT = "CasinoBonusScraper/1.0 (+https://github.com/ThutoCodes/casino-bonus-scraper)"
BLOCK_STATUSES = {401, 403, 429}
BLOCK_MARKERS = ("captcha", "just a moment...", "access denied")


class FetchError(Exception):
    pass


class PoliteFetcher:
    """HTTP client that obeys robots.txt, rate-limits itself and never works around blocks."""

    def __init__(self, delay_seconds: float = 3.0, timeout_seconds: float = 20.0):
        self._delay = delay_seconds
        self._timeout = timeout_seconds
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request_at = 0.0

    def get(self, url: str) -> str:
        robots = self._robots_for(url)
        if not robots.can_fetch(USER_AGENT, url):
            raise FetchError(f"robots.txt disallows {url}")

        self._wait(robots.crawl_delay(USER_AGENT))
        try:
            response = self._session.get(url, timeout=self._timeout)
        except requests.RequestException as exc:
            raise FetchError(f"request to {url} failed: {exc}") from exc

        if response.status_code in BLOCK_STATUSES:
            raise FetchError(f"blocked by {url} (HTTP {response.status_code}), not retrying")
        if not response.ok:
            raise FetchError(f"HTTP {response.status_code} from {url}")

        # The server sends no charset, so requests would fall back to ISO-8859-1 and mangle "£".
        if "charset" not in response.headers.get("content-type", "").lower():
            response.encoding = "utf-8"

        if any(marker in response.text[:5000].lower() for marker in BLOCK_MARKERS):
            raise FetchError(f"{url} served a challenge page, not retrying")
        return response.text

    def _robots_for(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in self._robots:
            return self._robots[origin]

        parser = RobotFileParser()
        try:
            response = self._session.get(f"{origin}/robots.txt", timeout=self._timeout)
        except requests.RequestException as exc:
            raise FetchError(f"could not read robots.txt for {origin}: {exc}") from exc

        # Same rules as RobotFileParser.read(): auth errors mean disallow all, other 4xx allow all.
        if response.status_code in (401, 403):
            parser.disallow_all = True
        elif response.status_code >= 400:
            parser.allow_all = True
        else:
            parser.parse(response.text.splitlines())

        self._robots[origin] = parser
        self._last_request_at = time.monotonic()
        return parser

    def _wait(self, crawl_delay: float | None) -> None:
        delay = max(self._delay, crawl_delay or 0)
        remaining = self._last_request_at + delay - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_at = time.monotonic()
