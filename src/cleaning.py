"""Data cleaning utilities for Toronto condo rental data."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pandas as pd


def parse_price(value: object) -> Optional[float]:
    """Convert a rent price string such as '$2,800' into a number."""
    if pd.isna(value):
        return None
    digits = re.sub(r"[^0-9.]", "", str(value))
    return float(digits) if digits else None


def parse_numeric(value: object) -> Optional[float]:
    """Extract the first numeric value from a string."""
    if pd.isna(value):
        return None
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    return float(match.group()) if match else None


def parse_size(value: object) -> Optional[float]:
    """Convert a size range such as '600-699 sqft' into the midpoint.

    The original notebook used the upper bound. The midpoint is usually a more
    representative numeric estimate for analysis.
    """
    if pd.isna(value):
        return None

    numbers = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(value))]
    if not numbers:
        return None
    if len(numbers) == 1:
        return numbers[0]
    return sum(numbers[:2]) / 2


def clean_condo_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean raw condo rental listing data."""
    cleaned = df.copy()
    cleaned.columns = [column.strip().lower().replace(" ", "_") for column in cleaned.columns]

    cleaned = cleaned.replace({"NA": pd.NA, "N/A": pd.NA, "": pd.NA})

    if "price" in cleaned.columns:
        cleaned["price"] = cleaned["price"].apply(parse_price)

    for column in ["bathrooms", "parking"]:
        if column in cleaned.columns:
            cleaned[column] = cleaned[column].apply(parse_numeric)

    if "size" in cleaned.columns:
        cleaned["size_sqft_estimate"] = cleaned["size"].apply(parse_size)

    if "furnished" in cleaned.columns:
        cleaned["furnished"] = cleaned["furnished"].str.strip().str.title()
        cleaned = cleaned[cleaned["furnished"].isin(["Yes", "No", "Part"]) | cleaned["furnished"].isna()]

    cleaned = cleaned.drop_duplicates()

    if "price" in cleaned.columns:
        cleaned = cleaned[cleaned["price"].notna()]

    return cleaned.reset_index(drop=True)


def main() -> None:
    input_path = Path("data/raw/condos_raw.csv")
    output_path = Path("data/processed/condos_clean.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    cleaned = clean_condo_data(df)
    cleaned.to_csv(output_path, index=False)
    print(f"Saved cleaned data to {output_path}")


if __name__ == "__main__":
    main()
