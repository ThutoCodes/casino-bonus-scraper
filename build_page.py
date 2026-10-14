"""Generates docs/index.html from data/bonuses.json. Runs as part of scrape.py, or on its own."""

import json
import sys
from html import escape
from pathlib import Path

DATA_PATH = Path("data/bonuses.json")
PAGE_PATH = Path("docs/index.html")

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Casino Welcome Bonuses</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0 auto; padding: 16px; max-width: 960px;
         color: #1a1a1a; background: #fff; line-height: 1.5; }}
  h1 {{ font-size: 1.5rem; margin: 0 0 4px; }}
  .meta {{ color: #555; font-size: 0.9rem; margin: 0 0 16px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid #ddd; vertical-align: top; }}
  th {{ background: #f4f4f4; font-size: 0.85rem; }}
  .flag {{ display: inline-block; margin-top: 4px; font-size: 0.8rem; color: #8a4b00;
           background: #fff3e0; padding: 2px 6px; border-radius: 4px; }}
  a {{ color: #0b57d0; word-break: break-word; }}
  @media (max-width: 640px) {{
    thead {{ display: none; }}
    table, tbody, tr, td {{ display: block; width: 100%; box-sizing: border-box; }}
    tr {{ border: 1px solid #ddd; border-radius: 8px; margin-bottom: 12px; padding: 4px 0; }}
    td {{ border: none; padding: 6px 12px; }}
    td::before {{ content: attr(data-label); display: block; font-size: 0.75rem; color: #555; }}
  }}
</style>
</head>
<body>
<h1>Casino Welcome Bonuses</h1>
<p class="meta">Source: <a href="{source}" rel="noopener">{source}</a> &middot; Generated {generated_at} UTC</p>
<table>
<thead>
<tr><th>Casino</th><th>Welcome bonus</th><th>Wagering</th><th>Min deposit</th><th>Source</th></tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
<p class="meta">Bonus terms were scraped from public review pages and converted to fields by a language model.
Values the script could not match back to the source text are marked for review.</p>
</body>
</html>
"""

ROW_TEMPLATE = """<tr>
<td data-label="Casino"><strong>{casino}</strong>{flag}</td>
<td data-label="Welcome bonus">{welcome_bonus}</td>
<td data-label="Wagering">{wagering}</td>
<td data-label="Min deposit">{min_deposit}</td>
<td data-label="Source"><a href="{source_url}" rel="noopener">{source_url}</a></td>
</tr>"""


def render(data: dict) -> str:
    rows = "\n".join(_render_row(casino) for casino in data["casinos"])
    return PAGE_TEMPLATE.format(
        source=escape(data["source"]),
        generated_at=escape(data["generated_at"][:16].replace("T", " ")),
        rows=rows,
    )


def _render_row(casino: dict) -> str:
    wagering = casino["wagering_multiplier"]
    deposit = casino["min_deposit"]
    flag = ""
    if casino["needs_review"]:
        title = escape("; ".join(casino["review_notes"]))
        flag = f'<br><span class="flag" title="{title}">Needs review</span>'
    return ROW_TEMPLATE.format(
        casino=escape(casino["casino"]),
        flag=flag,
        welcome_bonus=escape(casino["welcome_bonus"] or "Not stated"),
        wagering=f"{wagering}x" if wagering is not None else "Not stated",
        min_deposit=escape(f"{deposit['amount']:g} {deposit['currency']}") if deposit else "Not stated",
        source_url=escape(casino["source_url"]),
    )


def write_page(data_path: Path = DATA_PATH, page_path: Path = PAGE_PATH) -> None:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(render(data), encoding="utf-8")


if __name__ == "__main__":
    try:
        write_page()
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        sys.exit(f"Could not build page from {DATA_PATH}: {exc}")
    print(f"Wrote {PAGE_PATH}")
