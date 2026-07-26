"""Tests for reproducible analysis summaries."""

from __future__ import annotations

import unittest

import pandas as pd

from src.analyze import (
    REQUIRED_COLUMNS,
    build_overview,
    room_sort_key,
    summarize_by_parking,
    summarize_by_room,
    validate_schema,
)


def analysis_frame() -> pd.DataFrame:
    """Create a compact representative analysis dataset."""

    return pd.DataFrame(
        [
            {
                "Address": "1 Test Street",
                "SourceURL": "https://example.test/1",
                "PriceCAD": 2000,
                "Room": "Studio",
                "Bath": 1,
                "Parking": 0,
                "AnalysisSizeSqft": pd.NA,
                "PricePerSqft": pd.NA,
                "OpenEndedSizeRange": True,
                "PriceOutlierIQR": False,
                "AnalysisEligible": True,
            },
            {
                "Address": "2 Test Street",
                "SourceURL": "https://example.test/2",
                "PriceCAD": 2500,
                "Room": "1",
                "Bath": 1,
                "Parking": 1,
                "AnalysisSizeSqft": 549.5,
                "PricePerSqft": 2500 / 549.5,
                "OpenEndedSizeRange": False,
                "PriceOutlierIQR": False,
                "AnalysisEligible": True,
            },
            {
                "Address": "3 Test Street",
                "SourceURL": "https://example.test/3",
                "PriceCAD": 3000,
                "Room": "1+1",
                "Bath": 1,
                "Parking": 1,
                "AnalysisSizeSqft": 649.5,
                "PricePerSqft": 3000 / 649.5,
                "OpenEndedSizeRange": False,
                "PriceOutlierIQR": False,
                "AnalysisEligible": True,
            },
        ],
        columns=REQUIRED_COLUMNS,
    )


class AnalysisTests(unittest.TestCase):
    """Verify overview and grouped summaries."""

    def test_missing_required_column_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            validate_schema(pd.DataFrame({"PriceCAD": [2000]}))

    def test_room_sorting_is_natural(self) -> None:
        labels = ["2+1", "1", "Studio", "2", "1+1"]
        self.assertEqual(
            sorted(labels, key=room_sort_key),
            ["Studio", "1", "1+1", "2", "2+1"],
        )

    def test_overview_reconciles(self) -> None:
        overview = build_overview(analysis_frame()).set_index("Metric")["Value"]
        self.assertEqual(overview["Listings"], 3)
        self.assertEqual(overview["MedianRentCAD"], 2500)
        self.assertEqual(overview["OpenEndedSizeRangeListings"], 1)
        self.assertEqual(overview["ListingsWithClosedSizeRange"], 2)

    def test_room_summary_counts(self) -> None:
        summary = summarize_by_room(analysis_frame()).set_index("Room")
        self.assertEqual(summary.loc["Studio", "Listings"], 1)
        self.assertEqual(summary.loc["1+1", "MedianRentCAD"], 3000)

    def test_parking_summary_counts(self) -> None:
        summary = summarize_by_parking(analysis_frame()).set_index("Parking")
        self.assertEqual(summary.loc[0, "Listings"], 1)
        self.assertEqual(summary.loc[1, "Listings"], 2)
        self.assertEqual(summary.loc[1, "MedianRentCAD"], 2750)


if __name__ == "__main__":
    unittest.main()
