"""Regression tests for scraper parsing and card validation."""

from __future__ import annotations

import unittest
from typing import Any

from src.scraper import parse_listing, parse_room, parse_size


class FakeElement:
    """Minimal rendered-element stand-in for parser tests."""

    def __init__(
        self,
        text: str,
        parent: "FakeElement | None" = None,
        href: str | None = None,
    ) -> None:
        self.text = text
        self._parent = parent
        self._href = href

    def parent(self) -> "FakeElement":
        if self._parent is None:
            raise RuntimeError("Reached root element.")
        return self._parent

    def attr(self, name: str) -> str | None:
        if name == "href":
            return self._href
        return None

    def eles(self, query: str) -> list[Any]:
        del query
        return []


class ScraperParsingTests(unittest.TestCase):
    """Verify parsing rules that previously caused data-quality defects."""

    def test_size_range_with_commas(self) -> None:
        self.assertEqual(parse_size("1,000-1,199 sqft"), (1000, 1199))

    def test_open_ended_size_range(self) -> None:
        self.assertEqual(parse_size("0-499 sqft"), (0, 499))

    def test_single_size(self) -> None:
        self.assertEqual(parse_size("700 sqft"), (700, 700))

    def test_studio_room(self) -> None:
        self.assertEqual(parse_room("Studio 1BA"), "Studio")

    def test_bedroom_and_den(self) -> None:
        self.assertEqual(parse_room("2+1BD 2BA"), "2+1")

    def test_open_range_has_no_midpoint(self) -> None:
        card = FakeElement(
            "$2,100 1 day 101 - 1 Test Street Studio 1BA "
            "0 Parking 0-499 sqft MLS#: C123 TEST REALTY"
        )
        address = FakeElement(
            "101 - 1 Test Street",
            parent=card,
            href="/toronto/test-building/unit-101-C123",
        )

        record = parse_listing(
            address_element=address,
            page_num=1,
            scraped_at_utc="2026-07-25T00:00:00+00:00",
        )

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["SizeMinSqft"], 0)
        self.assertEqual(record["SizeMaxSqft"], 499)
        self.assertIsNone(record["SizeMidSqft"])
        self.assertIsNone(record["SizeSqm"])

    def test_multi_listing_container_is_rejected(self) -> None:
        container = FakeElement(
            "$2,000 A 1BD 1BA 0 Parking 500-599 sqft MLS#: A "
            "$2,500 B 2BD 2BA 1 Parking 700-799 sqft MLS#: B"
        )
        address = FakeElement(
            "A",
            parent=container,
            href="/toronto/a",
        )

        record = parse_listing(
            address_element=address,
            page_num=1,
            scraped_at_utc="2026-07-25T00:00:00+00:00",
        )
        self.assertIsNone(record)


if __name__ == "__main__":
    unittest.main()
