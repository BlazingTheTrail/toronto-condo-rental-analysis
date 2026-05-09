"""Scraper for Toronto condo rental listings.

This module refactors the original notebook scraping logic into reusable functions.
The CSS selectors are based on the original project and may need to be updated if
Condos.ca changes its frontend structure.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import (
    BASE_URL,
    HEADERS,
    MAX_PAGES,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT,
    SEARCH_URL_TEMPLATE,
    SELECTORS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

COLUMNS = [
    "address",
    "price",
    "neighbourhood",
    "area",
    "rooms",
    "bathrooms",
    "parking",
    "furnished",
    "building_age",
    "outdoor_space",
    "property_type",
    "size",
    "url",
]


def fetch_page(url: str) -> Optional[BeautifulSoup]:
    """Fetch a web page and return a BeautifulSoup object.

    Returns None if the request fails.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as exc:
        logging.warning("Failed to fetch %s: %s", url, exc)
        return None


def get_listing_urls(max_pages: int = MAX_PAGES) -> List[str]:
    """Collect listing URLs from paginated Toronto rental search results."""
    listing_urls: List[str] = []

    for page in range(1, max_pages + 1):
        url = SEARCH_URL_TEMPLATE.format(page=page)
        soup = fetch_page(url)
        if soup is None:
            continue

        page_links = []
        for link in soup.select(SELECTORS["listing_link"]):
            href = link.get("href")
            if href:
                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                page_links.append(full_url)

        logging.info("Page %s: found %s listing URLs", page, len(page_links))
        listing_urls.extend(page_links)
        time.sleep(REQUEST_DELAY_SECONDS)

    return sorted(set(listing_urls))


def get_text(soup: BeautifulSoup, selector: str) -> Optional[str]:
    """Extract stripped text from the first element matching a CSS selector."""
    element = soup.select_one(selector)
    return element.get_text(strip=True) if element else None


def safe_get(values: List[str], index: int) -> Optional[str]:
    """Safely retrieve a list item by index."""
    return values[index] if len(values) > index else None


def parse_listing(url: str) -> Dict[str, Optional[str]]:
    """Parse a single rental listing page into a dictionary."""
    soup = fetch_page(url)
    if soup is None:
        return {column: None for column in COLUMNS} | {"url": url}

    summary_values = [item.get_text(strip=True) for item in soup.select(SELECTORS["summary_values"])]
    detail_values = [item.get_text(strip=True) for item in soup.select(SELECTORS["detail_values"])]

    return {
        "address": get_text(soup, SELECTORS["address"]),
        "price": get_text(soup, SELECTORS["price"]),
        "neighbourhood": get_text(soup, SELECTORS["neighbourhood"]),
        "area": get_text(soup, SELECTORS["area"]),
        "rooms": safe_get(summary_values, 0),
        "bathrooms": safe_get(summary_values, 1),
        "parking": safe_get(summary_values, 2),
        # Index positions follow the original notebook logic.
        "furnished": safe_get(detail_values, 2),
        "building_age": safe_get(detail_values, 4),
        "outdoor_space": safe_get(detail_values, 5),
        "property_type": safe_get(detail_values, 10),
        "size": safe_get(detail_values, 16),
        "url": url,
    }


def scrape_listings(listing_urls: Iterable[str]) -> pd.DataFrame:
    """Scrape all listing URLs into a DataFrame."""
    records = []
    for idx, url in enumerate(listing_urls, start=1):
        logging.info("Scraping listing %s: %s", idx, url)
        records.append(parse_listing(url))
        time.sleep(REQUEST_DELAY_SECONDS)
    return pd.DataFrame(records, columns=COLUMNS)


def main() -> None:
    output_path = Path("data/raw/condos_raw.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    urls = get_listing_urls()
    logging.info("Collected %s unique listing URLs", len(urls))

    raw_df = scrape_listings(urls)
    raw_df.to_csv(output_path, index=False)
    logging.info("Saved raw data to %s", output_path)


if __name__ == "__main__":
    main()
