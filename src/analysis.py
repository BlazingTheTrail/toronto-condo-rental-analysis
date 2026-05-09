"""Reusable analysis functions for Toronto condo rental data."""

from __future__ import annotations

import pandas as pd


def area_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return area-level rental price and size summary statistics."""
    return (
        df.groupby("area", dropna=False)
        .agg(
            listings=("price", "size"),
            median_price=("price", "median"),
            average_price=("price", "mean"),
            median_size_sqft=("size_sqft_estimate", "median"),
            average_size_sqft=("size_sqft_estimate", "mean"),
        )
        .sort_values("median_price", ascending=False)
        .reset_index()
    )


def property_type_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return listing count and median rent by property type."""
    return (
        df.groupby("property_type", dropna=False)
        .agg(listings=("price", "size"), median_price=("price", "median"))
        .sort_values("listings", ascending=False)
        .reset_index()
    )


def furnished_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return listing count and median rent by furnishing status."""
    return (
        df.groupby("furnished", dropna=False)
        .agg(listings=("price", "size"), median_price=("price", "median"))
        .sort_values("listings", ascending=False)
        .reset_index()
    )
