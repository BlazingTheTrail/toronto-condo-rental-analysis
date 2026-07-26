"""Collect Toronto condo rental listings from rendered search-result pages.

This module replaces the legacy requests/BeautifulSoup scraper, whose static
HTTP requests now receive a Cloudflare 403 response. It uses a normal visible
Chromium browser through DrissionPage and parses only content rendered on the
public listing pages.

The scraper deliberately does not automate verification challenges. If the
site presents one, the run stops with a clear message. Review the source
website's terms, robots guidance, and request limits before collecting data.

Examples
--------
Run a one-page validation:

    python src/scraper.py --start-page 1 --end-page 1

Run pages 1 through 10:

    python src/scraper.py --start-page 1 --end-page 10

Output is written to ``data/raw`` by default. A checkpoint CSV is replaced
after every successfully processed page, while the final timestamped CSV is
kept as a separate snapshot.
"""

from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
from DrissionPage import ChromiumPage


BASE_URL = "https://condos.ca"
SEARCH_URL = f"{BASE_URL}/toronto?mode=Rent&page={{page_num}}"
DEFAULT_OUTPUT_DIR = Path("data/raw")

OUTPUT_COLUMNS = [
    "ScrapedAtUTC",
    "SourcePage",
    "SourceURL",
    "Address",
    "PriceCAD",
    "Room",
    "Bath",
    "Parking",
    "SizeMinSqft",
    "SizeMaxSqft",
    "SizeMidSqft",
    "SizeSqm",
    "Neighbourhood",
    "Area",
    "PropertyType",
    "Furnished",
    "OutdoorSpace",
    "AgeOfBuild",
    "RawText",
]

PRICE_PATTERN = re.compile(r"\$\s*([\d,]{3,})")
ROOM_PATTERN = re.compile(
    r"\b(Studio|\d+(?:\+\d+)?\s*BD)\b",
    re.IGNORECASE,
)
BATH_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*BA\b", re.IGNORECASE)
PARKING_PATTERN = re.compile(
    r"\b(\d+)\s*Parking\b",
    re.IGNORECASE,
)
SIZE_RANGE_PATTERN = re.compile(
    r"\b([\d,]{1,5})\s*-\s*([\d,]{1,5})\s*sqft\b",
    re.IGNORECASE,
)
SIZE_SINGLE_PATTERN = re.compile(
    r"\b([\d,]{1,5})\s*sqft\b",
    re.IGNORECASE,
)
BUILDING_AGE_PATTERN = re.compile(
    r"\b(\d+)\s*years?\s*old\b",
    re.IGNORECASE,
)

PROPERTY_TYPES = (
    "Comm Element Condo",
    "Co-Ownership Apt",
    "Condo Townhouse",
    "Leasehold Condo",
    "Condo Apt",
    "Co-Op Apt",
    "Apartment",
)

OUTDOOR_SPACE_TYPES = (
    "Enclosed Balcony",
    "Juliet Balcony",
    "Open Balcony",
    "Terrace",
    "Patio",
    "Balcony",
)


def configure_logging(verbose: bool = False) -> None:
    """Configure concise console logging."""

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def normalize_text(value: str | None) -> str:
    """Collapse repeated whitespace while preserving readable card text."""

    return " ".join((value or "").split())


def first_named_value(options: tuple[str, ...], text: str) -> str | None:
    """Return the first explicitly present category, or None."""

    lowered = text.casefold()
    for option in options:
        if option.casefold() in lowered:
            return option
    return None


def parse_furnished(text: str) -> str | None:
    """Parse furnishing only when the listing states it explicitly."""

    if re.search(r"\bunfurnished\b", text, re.IGNORECASE):
        return "No"
    if re.search(r"\bpart(?:ly|ially)?\s+furnished\b", text, re.IGNORECASE):
        return "Part"
    if re.search(r"\bfurnished\b", text, re.IGNORECASE):
        return "Yes"
    return None


def parse_building_age(text: str) -> str | None:
    """Return a reported age without inferring one from missing text."""

    age_match = BUILDING_AGE_PATTERN.search(text)
    if age_match:
        return f"{age_match.group(1)} years old"
    if re.search(r"\bbrand\s+new\b|\bnew\s+construction\b", text, re.IGNORECASE):
        return "New"
    return None


def parse_size(text: str) -> tuple[int | None, int | None]:
    """Parse a square-foot range or a single reported square-foot value."""

    range_match = SIZE_RANGE_PATTERN.search(text)
    if range_match:
        lower = int(range_match.group(1).replace(",", ""))
        upper = int(range_match.group(2).replace(",", ""))
        return lower, upper

    single_match = SIZE_SINGLE_PATTERN.search(text)
    if single_match:
        value = int(single_match.group(1).replace(",", ""))
        return value, value

    return None, None


def parse_room(text: str) -> str | None:
    """Parse Studio or remove the rendered BD suffix from a room value."""

    room_match = ROOM_PATTERN.search(text)
    if not room_match:
        return None

    room = normalize_text(room_match.group(1))
    if room.casefold() == "studio":
        return "Studio"
    return re.sub(r"\s*BD$", "", room, flags=re.IGNORECASE)


def find_listing_card(address_element: Any, max_parent_levels: int = 8) -> Any | None:
    """Find the closest parent that looks like a complete listing card."""

    current = address_element

    for _ in range(max_parent_levels):
        try:
            current = current.parent()
            text = normalize_text(current.text)
        except Exception as exc:
            logging.debug("Parent traversal stopped: %s", exc)
            return None

        has_price = PRICE_PATTERN.search(text) is not None
        has_unit_info = (
            ROOM_PATTERN.search(text) is not None
            or BATH_PATTERN.search(text) is not None
        )

        # A genuine result card contains one listing identifier. Requiring
        # exactly one prevents comparison drawers or page-level containers
        # containing many listings from being parsed as a single record.
        has_single_listing = text.count("MLS#:") == 1

        if has_price and has_unit_info and has_single_listing:
            return current

    return None


def find_source_url(address_element: Any, card: Any) -> str | None:
    """Find the nearest plausible property link without relying on CSS classes."""

    current = address_element

    for _ in range(5):
        try:
            href = current.attr("href")
            if href:
                return urljoin(BASE_URL, href)
            current = current.parent()
        except Exception:
            break

    try:
        for anchor in card.eles("tag:a"):
            href = anchor.attr("href")
            if href and "/toronto/" in href:
                return urljoin(BASE_URL, href)
    except Exception:
        return None

    return None


def parse_listing(
    address_element: Any,
    page_num: int,
    scraped_at_utc: str,
) -> dict[str, Any] | None:
    """Convert one rendered listing card into a normalized record."""

    card = find_listing_card(address_element)
    if card is None:
        return None

    raw_text = normalize_text(card.text)
    address = normalize_text(address_element.text)

    # The address element must belong to the card that was selected. This
    # rejects unrelated address elements rendered inside comparison widgets.
    if not address or address.casefold() not in raw_text.casefold():
        return None

    price_match = PRICE_PATTERN.search(raw_text)
    bath_match = BATH_PATTERN.search(raw_text)
    parking_match = PARKING_PATTERN.search(raw_text)
    size_min, size_max = parse_size(raw_text)

    price = (
        int(price_match.group(1).replace(",", ""))
        if price_match
        else None
    )
    room = parse_room(raw_text)
    bath = float(bath_match.group(1)) if bath_match else None
    parking = int(parking_match.group(1)) if parking_match else None

    # A band such as 0-499 sqft is open-ended in practice. Preserve its stated
    # bounds but do not report a misleading midpoint or square-metre estimate.
    size_mid = (
        (size_min + size_max) / 2
        if (
            size_min is not None
            and size_max is not None
            and size_min > 0
        )
        else None
    )
    size_sqm = round(size_mid * 0.092903, 2) if size_mid is not None else None

    return {
        "ScrapedAtUTC": scraped_at_utc,
        "SourcePage": page_num,
        "SourceURL": find_source_url(address_element, card),
        "Address": address or None,
        "PriceCAD": price,
        "Room": room,
        "Bath": bath,
        "Parking": parking,
        "SizeMinSqft": size_min,
        "SizeMaxSqft": size_max,
        "SizeMidSqft": size_mid,
        "SizeSqm": size_sqm,
        # These fields should remain missing until the page states them
        # explicitly or a later detail-page enrichment step supplies them.
        "Neighbourhood": None,
        "Area": None,
        # Result-card text does not provide these categories consistently.
        # Leave them missing until a detail-page enrichment step supplies them.
        "PropertyType": None,
        "Furnished": parse_furnished(raw_text),
        "OutdoorSpace": None,
        "AgeOfBuild": parse_building_age(raw_text),
        "RawText": raw_text,
    }


def page_has_verification(page: ChromiumPage) -> bool:
    """Detect a verification page and stop instead of automating it."""

    title = normalize_text(getattr(page, "title", ""))
    html = normalize_text(getattr(page, "html", ""))
    indicators = (
        "just a moment",
        "verify you are human",
        "checking your browser",
        "challenge-platform",
    )
    combined = f"{title} {html[:5000]}".casefold()
    return any(indicator in combined for indicator in indicators)


def scroll_until_stable(
    page: ChromiumPage,
    max_rounds: int = 6,
    stable_rounds_required: int = 2,
) -> list[Any]:
    """Scroll until the number of rendered address elements stops increasing."""

    previous_count = -1
    stable_rounds = 0
    address_elements: list[Any] = []

    for _ in range(max_rounds):
        address_elements = list(page.eles("tag:address"))
        current_count = len(address_elements)

        if current_count == previous_count:
            stable_rounds += 1
        else:
            stable_rounds = 0

        if stable_rounds >= stable_rounds_required:
            break

        previous_count = current_count
        page.scroll.to_bottom()
        page.wait(1.0, 1.8)

    return list(page.eles("tag:address"))


def scrape_one_page(
    page: ChromiumPage,
    page_num: int,
    timeout: float = 20,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Scrape one search-results page and return records plus parse errors."""

    url = SEARCH_URL.format(page_num=page_num)
    logging.info("Loading page %s: %s", page_num, url)
    page.get(url)

    if page_has_verification(page):
        raise RuntimeError(
            "The website presented a verification page. "
            "This scraper does not automate verification challenges."
        )

    first_address = page.ele("tag:address", timeout=timeout)
    if not first_address:
        logging.warning("Page %s did not render any address elements.", page_num)
        return [], []

    address_elements = scroll_until_stable(page)
    scraped_at_utc = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for position, address_element in enumerate(address_elements, start=1):
        try:
            record = parse_listing(
                address_element=address_element,
                page_num=page_num,
                scraped_at_utc=scraped_at_utc,
            )
            if record is None:
                errors.append(
                    {
                        "SourcePage": page_num,
                        "Position": position,
                        "Address": normalize_text(address_element.text),
                        "Error": "Could not identify a complete listing card.",
                    }
                )
                continue
            records.append(record)
        except Exception as exc:
            errors.append(
                {
                    "SourcePage": page_num,
                    "Position": position,
                    "Address": normalize_text(
                        getattr(address_element, "text", "")
                    ),
                    "Error": f"{type(exc).__name__}: {exc}",
                }
            )

    logging.info(
        "Page %s: %s records, %s parse errors.",
        page_num,
        len(records),
        len(errors),
    )
    return records, errors


def deduplicate_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Deduplicate by URL when available, otherwise by listing attributes."""

    if not records:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    frame = pd.DataFrame(records)
    with_url = frame[frame["SourceURL"].notna()].drop_duplicates(
        subset=["SourceURL"],
        keep="last",
    )
    without_url = frame[frame["SourceURL"].isna()].drop_duplicates(
        subset=["Address", "PriceCAD", "Room", "Bath"],
        keep="last",
    )

    combined = pd.concat([with_url, without_url], ignore_index=True)
    combined = combined.reindex(columns=OUTPUT_COLUMNS)
    return combined.sort_values(
        by=["SourcePage", "Address"],
        na_position="last",
    ).reset_index(drop=True)


def save_checkpoint(
    records: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    output_dir: Path,
) -> tuple[Path, Path]:
    """Replace checkpoint files with the latest accumulated state."""

    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / "toronto_condos_checkpoint.csv"
    error_path = output_dir / "toronto_condos_parse_errors.csv"

    deduplicate_records(records).to_csv(
        data_path,
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(
        errors,
        columns=["SourcePage", "Position", "Address", "Error"],
    ).to_csv(
        error_path,
        index=False,
        encoding="utf-8-sig",
    )
    return data_path, error_path


def scrape_pages(
    start_page: int,
    end_page: int,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    timeout: float = 20,
) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    """Scrape an inclusive page range with one browser and page checkpoints."""

    if start_page < 1:
        raise ValueError("start_page must be at least 1.")
    if end_page < start_page:
        raise ValueError("end_page must be greater than or equal to start_page.")

    output_dir.mkdir(parents=True, exist_ok=True)
    all_records: list[dict[str, Any]] = []
    all_errors: list[dict[str, Any]] = []
    page = ChromiumPage()

    try:
        for page_num in range(start_page, end_page + 1):
            records, errors = scrape_one_page(
                page=page,
                page_num=page_num,
                timeout=timeout,
            )
            all_records.extend(records)
            all_errors.extend(errors)

            checkpoint_path, error_path = save_checkpoint(
                records=all_records,
                errors=all_errors,
                output_dir=output_dir,
            )
            logging.info(
                "Checkpoint: %s | errors: %s",
                checkpoint_path,
                error_path,
            )

            if page_num < end_page:
                page.wait(2.0, 4.0)
    finally:
        try:
            page.quit()
        except Exception as exc:
            logging.warning("Browser did not close cleanly: %s", exc)

    final_frame = deduplicate_records(all_records)
    error_frame = pd.DataFrame(
        all_errors,
        columns=["SourcePage", "Position", "Address", "Error"],
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_path = output_dir / f"toronto_condos_{timestamp}.csv"
    final_frame.to_csv(final_path, index=False, encoding="utf-8-sig")

    logging.info(
        "Finished: %s unique records saved to %s.",
        len(final_frame),
        final_path,
    )
    return final_frame, error_frame, final_path


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""

    parser = argparse.ArgumentParser(
        description="Collect Toronto condo rental search-result listings."
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="First page to collect (default: 1).",
    )
    parser.add_argument(
        "--end-page",
        type=int,
        default=1,
        help="Last page to collect, inclusive (default: 1).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="CSV output directory (default: data/raw).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20,
        help="Seconds to wait for the first listing (default: 20).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main() -> None:
    """Run the command-line scraper."""

    args = build_parser().parse_args()
    configure_logging(verbose=args.verbose)
    scrape_pages(
        start_page=args.start_page,
        end_page=args.end_page,
        output_dir=args.output_dir,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
