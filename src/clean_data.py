"""Clean and validate Toronto condo rental search-result data.

The scraper intentionally preserves raw card values. This module performs the
next stage of the pipeline: schema validation, duplicate removal, scope
classification, quality flags, and creation of analysis-ready CSV files.

Examples
--------
Clean one timestamped scraper output:

    python src/clean_data.py \
        --input data/raw/toronto_condos_20260725_193901.csv

Write processed files to a different directory:

    python src/clean_data.py \
        --input data/raw/toronto_condos_20260725_193901.csv \
        --output-dir data/processed
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_OUTPUT_DIR = Path("data/processed")

REQUIRED_COLUMNS = [
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

CRITICAL_COLUMNS = [
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
    "RawText",
]

STRING_COLUMNS = [
    "SourceURL",
    "Address",
    "Room",
    "Neighbourhood",
    "Area",
    "PropertyType",
    "Furnished",
    "OutdoorSpace",
    "AgeOfBuild",
    "RawText",
]

NUMERIC_COLUMNS = [
    "SourcePage",
    "PriceCAD",
    "Bath",
    "Parking",
    "SizeMinSqft",
    "SizeMaxSqft",
    "SizeMidSqft",
    "SizeSqm",
]

ROOM_ONLY_PATTERN = re.compile(
    r"\b(?:master\s*bed(?:room)?|masterbed|"
    r"room\s*(?:only|rental)|shared)\b",
    re.IGNORECASE,
)
LOWER_LEVEL_PATTERN = re.compile(
    r"\b(?:lower\s+level|basement)\b",
    re.IGNORECASE,
)
NON_RESIDENTIAL_UNIT_PATTERN = re.compile(
    r"\b(?:parking|locker)\b",
    re.IGNORECASE,
)


def configure_logging(verbose: bool = False) -> None:
    """Configure concise command-line logging."""

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def normalize_text(value: Any) -> Any:
    """Collapse whitespace in text while preserving missing values."""

    if pd.isna(value):
        return pd.NA
    return " ".join(str(value).split())


def validate_schema(frame: pd.DataFrame) -> None:
    """Raise a clear error when required scraper columns are absent."""

    missing = [column for column in REQUIRED_COLUMNS if column not in frame]
    if missing:
        raise ValueError(
            "Input CSV is missing required columns: " + ", ".join(missing)
        )


def standardize_types(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with normalized strings, numbers, and UTC timestamps."""

    result = frame.copy()

    for column in STRING_COLUMNS:
        result[column] = result[column].map(normalize_text).astype("string")

    for column in NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    result["ScrapedAtUTC"] = pd.to_datetime(
        result["ScrapedAtUTC"],
        errors="coerce",
        utc=True,
    )
    return result


def classify_exclusion_reason(frame: pd.DataFrame) -> pd.Series:
    """Classify records outside the whole-unit condo analysis scope."""

    searchable = (
        frame["Address"].fillna("")
        + " "
        + frame["SourceURL"].fillna("")
    )

    reason = pd.Series(pd.NA, index=frame.index, dtype="string")
    reason.loc[
        searchable.str.contains(
            NON_RESIDENTIAL_UNIT_PATTERN,
            regex=True,
        )
    ] = "Non-residential parking or locker listing"
    reason.loc[
        reason.isna()
        & searchable.str.contains(
            ROOM_ONLY_PATTERN,
            regex=True,
        )
    ] = "Room-only or shared-accommodation listing"
    reason.loc[
        reason.isna()
        & searchable.str.contains(
            LOWER_LEVEL_PATTERN,
            regex=True,
        )
    ] = "Lower-level or basement listing"
    return reason


def add_quality_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add transparent quality and analysis-scope flags."""

    result = frame.copy()

    result["MissingCriticalField"] = result[CRITICAL_COLUMNS].isna().any(axis=1)
    result["InvalidPrice"] = result["PriceCAD"].le(0) | result["PriceCAD"].isna()
    result["InvalidBath"] = result["Bath"].le(0) | result["Bath"].isna()
    result["InvalidParking"] = result["Parking"].lt(0) | result["Parking"].isna()
    result["InvalidSizeRange"] = (
        result["SizeMinSqft"].isna()
        | result["SizeMaxSqft"].isna()
        | result["SizeMinSqft"].lt(0)
        | result["SizeMaxSqft"].lt(result["SizeMinSqft"])
    )

    result["OpenEndedSizeRange"] = result["SizeMinSqft"].eq(0)

    closed_size = (
        ~result["InvalidSizeRange"]
        & ~result["OpenEndedSizeRange"]
        & result["SizeMidSqft"].gt(0)
    )
    result["AnalysisSizeSqft"] = result["SizeMidSqft"].where(closed_size)
    result["PricePerSqft"] = (
        result["PriceCAD"] / result["AnalysisSizeSqft"]
    ).where(closed_size)

    q1 = result["PriceCAD"].quantile(0.25)
    q3 = result["PriceCAD"].quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    result["PriceOutlierIQR"] = (
        result["PriceCAD"].lt(lower_bound)
        | result["PriceCAD"].gt(upper_bound)
    )

    result["ExclusionReason"] = classify_exclusion_reason(result)
    invalid_quality = result[
        [
            "MissingCriticalField",
            "InvalidPrice",
            "InvalidBath",
            "InvalidParking",
            "InvalidSizeRange",
        ]
    ].any(axis=1)
    result["AnalysisEligible"] = (
        result["ExclusionReason"].isna() & ~invalid_quality
    )
    return result


def clean_records(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate, normalize, deduplicate, and flag raw scraper records."""

    validate_schema(frame)
    result = standardize_types(frame)
    result = result.drop_duplicates()
    result = result.drop_duplicates(subset=["SourceURL"], keep="last")
    result = result.reset_index(drop=True)
    result = add_quality_columns(result)
    return result.sort_values(
        by=["SourcePage", "Address"],
        na_position="last",
    ).reset_index(drop=True)


def build_quality_summary(
    raw_frame: pd.DataFrame,
    cleaned_frame: pd.DataFrame,
) -> pd.DataFrame:
    """Create a compact, auditable key-value quality report."""

    optional_columns = [
        "Neighbourhood",
        "Area",
        "PropertyType",
        "Furnished",
        "OutdoorSpace",
        "AgeOfBuild",
    ]
    metrics: list[tuple[str, Any]] = [
        ("RowsInput", len(raw_frame)),
        ("RowsAfterDeduplication", len(cleaned_frame)),
        (
            "RowsAnalysisEligible",
            int(cleaned_frame["AnalysisEligible"].sum()),
        ),
        (
            "RowsExcluded",
            int((~cleaned_frame["AnalysisEligible"]).sum()),
        ),
        (
            "RowsMissingCriticalField",
            int(cleaned_frame["MissingCriticalField"].sum()),
        ),
        (
            "RowsInvalidPrice",
            int(cleaned_frame["InvalidPrice"].sum()),
        ),
        (
            "RowsInvalidBath",
            int(cleaned_frame["InvalidBath"].sum()),
        ),
        (
            "RowsInvalidParking",
            int(cleaned_frame["InvalidParking"].sum()),
        ),
        (
            "RowsInvalidSizeRange",
            int(cleaned_frame["InvalidSizeRange"].sum()),
        ),
        (
            "RowsOpenEndedSizeRange",
            int(cleaned_frame["OpenEndedSizeRange"].sum()),
        ),
        (
            "RowsPriceOutlierIQR",
            int(cleaned_frame["PriceOutlierIQR"].sum()),
        ),
    ]

    for column in optional_columns:
        metrics.append(
            (
                f"RowsMissing{column}",
                int(cleaned_frame[column].isna().sum()),
            )
        )

    return pd.DataFrame(metrics, columns=["Metric", "Value"])


def save_outputs(
    input_path: Path,
    output_dir: Path,
    cleaned_frame: pd.DataFrame,
    summary_frame: pd.DataFrame,
) -> tuple[Path, Path, Path]:
    """Save analysis-ready, excluded, and quality-summary CSV files."""

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    clean_path = output_dir / f"{stem}_clean.csv"
    excluded_path = output_dir / f"{stem}_excluded.csv"
    summary_path = output_dir / f"{stem}_quality_summary.csv"

    cleaned_frame.loc[cleaned_frame["AnalysisEligible"]].to_csv(
        clean_path,
        index=False,
        encoding="utf-8-sig",
    )
    cleaned_frame.loc[~cleaned_frame["AnalysisEligible"]].to_csv(
        excluded_path,
        index=False,
        encoding="utf-8-sig",
    )
    summary_frame.to_csv(
        summary_path,
        index=False,
        encoding="utf-8-sig",
    )
    return clean_path, excluded_path, summary_path


def clean_file(
    input_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame, tuple[Path, Path, Path]]:
    """Clean one scraper CSV and save all processed outputs."""

    raw_frame = pd.read_csv(input_path)
    cleaned_frame = clean_records(raw_frame)
    summary_frame = build_quality_summary(raw_frame, cleaned_frame)
    paths = save_outputs(
        input_path=input_path,
        output_dir=output_dir,
        cleaned_frame=cleaned_frame,
        summary_frame=summary_frame,
    )
    return cleaned_frame, summary_frame, paths


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""

    parser = argparse.ArgumentParser(
        description="Clean and validate Toronto condo rental scraper output."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Timestamped raw scraper CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Processed CSV directory (default: data/processed).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main() -> None:
    """Run the command-line cleaning pipeline."""

    args = build_parser().parse_args()
    configure_logging(verbose=args.verbose)
    cleaned_frame, summary_frame, paths = clean_file(
        input_path=args.input,
        output_dir=args.output_dir,
    )

    clean_path, excluded_path, summary_path = paths
    logging.info(
        "Finished: %s rows checked, %s analysis-ready, %s excluded.",
        len(cleaned_frame),
        int(cleaned_frame["AnalysisEligible"].sum()),
        int((~cleaned_frame["AnalysisEligible"]).sum()),
    )
    logging.info("Clean data: %s", clean_path)
    logging.info("Excluded records: %s", excluded_path)
    logging.info("Quality summary: %s", summary_path)
    logging.debug("Quality metrics:\n%s", summary_frame.to_string(index=False))


if __name__ == "__main__":
    main()
