"""Tests for cleaning, scope rules, and quality metrics."""

from __future__ import annotations

import unittest

import pandas as pd

from src.clean_data import (
    REQUIRED_COLUMNS,
    build_quality_summary,
    clean_records,
    validate_schema,
)


def sample_row(
    address: str,
    source_url: str,
    price: int = 2500,
    size_min: int = 500,
    size_max: int = 599,
    size_mid: float | None = 549.5,
    size_sqm: float | None = 51.05,
) -> dict[str, object]:
    """Create one representative raw scraper row."""

    return {
        "ScrapedAtUTC": "2026-07-25T19:39:00+00:00",
        "SourcePage": 1,
        "SourceURL": source_url,
        "Address": address,
        "PriceCAD": price,
        "Room": "1",
        "Bath": 1,
        "Parking": 0,
        "SizeMinSqft": size_min,
        "SizeMaxSqft": size_max,
        "SizeMidSqft": size_mid,
        "SizeSqm": size_sqm,
        "Neighbourhood": None,
        "Area": None,
        "PropertyType": None,
        "Furnished": None,
        "OutdoorSpace": None,
        "AgeOfBuild": None,
        "RawText": (
            f"${price:,} {address} 1BD 1BA 0 Parking "
            f"{size_min}-{size_max} sqft MLS#: C123 TEST REALTY"
        ),
    }


class CleaningTests(unittest.TestCase):
    """Verify analysis-scope and data-quality behavior."""

    def test_missing_required_column_raises(self) -> None:
        frame = pd.DataFrame({"Address": ["1 Test Street"]})
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            validate_schema(frame)

    def test_duplicate_url_is_removed(self) -> None:
        row = sample_row(
            address="101 - 1 Test Street",
            source_url="https://example.test/unit-101",
        )
        frame = pd.DataFrame([row, row], columns=REQUIRED_COLUMNS)
        cleaned = clean_records(frame)
        self.assertEqual(len(cleaned), 1)

    def test_room_only_listing_is_excluded(self) -> None:
        frame = pd.DataFrame(
            [
                sample_row(
                    address="3111 MASTERBED - 55 Cooper Street",
                    source_url="https://example.test/unit-masterbed",
                )
            ],
            columns=REQUIRED_COLUMNS,
        )
        cleaned = clean_records(frame)
        self.assertFalse(bool(cleaned.loc[0, "AnalysisEligible"]))
        self.assertEqual(
            cleaned.loc[0, "ExclusionReason"],
            "Room-only or shared-accommodation listing",
        )

    def test_lower_level_listing_is_excluded(self) -> None:
        frame = pd.DataFrame(
            [
                sample_row(
                    address="Lower Level - 14 Gooch Court",
                    source_url="https://example.test/lower-level",
                )
            ],
            columns=REQUIRED_COLUMNS,
        )
        cleaned = clean_records(frame)
        self.assertFalse(bool(cleaned.loc[0, "AnalysisEligible"]))
        self.assertEqual(
            cleaned.loc[0, "ExclusionReason"],
            "Lower-level or basement listing",
        )

    def test_open_size_range_has_no_price_per_sqft(self) -> None:
        frame = pd.DataFrame(
            [
                sample_row(
                    address="101 - 1 Test Street",
                    source_url="https://example.test/unit-101",
                    size_min=0,
                    size_max=499,
                    size_mid=None,
                    size_sqm=None,
                )
            ],
            columns=REQUIRED_COLUMNS,
        )
        cleaned = clean_records(frame)
        self.assertTrue(bool(cleaned.loc[0, "OpenEndedSizeRange"]))
        self.assertTrue(pd.isna(cleaned.loc[0, "AnalysisSizeSqft"]))
        self.assertTrue(pd.isna(cleaned.loc[0, "PricePerSqft"]))

    def test_summary_reconciles_rows(self) -> None:
        rows = [
            sample_row(
                address="101 - 1 Test Street",
                source_url="https://example.test/unit-101",
            ),
            sample_row(
                address="3111 MASTERBED - 55 Cooper Street",
                source_url="https://example.test/unit-masterbed",
            ),
        ]
        raw = pd.DataFrame(rows, columns=REQUIRED_COLUMNS)
        cleaned = clean_records(raw)
        summary = build_quality_summary(raw, cleaned).set_index("Metric")["Value"]

        self.assertEqual(summary["RowsInput"], 2)
        self.assertEqual(summary["RowsAnalysisEligible"], 1)
        self.assertEqual(summary["RowsExcluded"], 1)


if __name__ == "__main__":
    unittest.main()
