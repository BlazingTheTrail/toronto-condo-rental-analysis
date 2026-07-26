"""Create reproducible Toronto condo rental summaries and charts.

This module consumes the analysis-ready CSV produced by ``clean_data.py`` and
exports compact summary tables plus publication-ready PNG charts.

Example
-------
    python src/analyze.py \
        --input data/processed/toronto_condos_20260725_193901_clean.csv
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter


DEFAULT_OUTPUT_DIR = Path("outputs")

REQUIRED_COLUMNS = [
    "Address",
    "SourceURL",
    "PriceCAD",
    "Room",
    "Bath",
    "Parking",
    "AnalysisSizeSqft",
    "PricePerSqft",
    "OpenEndedSizeRange",
    "PriceOutlierIQR",
    "AnalysisEligible",
]

NAVY = "#17324D"
BLUE = "#3274A1"
TEAL = "#2A9D8F"
GOLD = "#E9A23B"
RED = "#C84C4C"
LIGHT_BLUE = "#DCEAF3"
LIGHT_GREY = "#E8EDF2"
MID_GREY = "#687684"
DARK_GREY = "#263238"


def configure_logging(verbose: bool = False) -> None:
    """Configure concise command-line logging."""

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def validate_schema(frame: pd.DataFrame) -> None:
    """Raise a clear error if the processed dataset is incomplete."""

    missing = [column for column in REQUIRED_COLUMNS if column not in frame]
    if missing:
        raise ValueError(
            "Processed CSV is missing required columns: " + ", ".join(missing)
        )


def as_boolean(series: pd.Series) -> pd.Series:
    """Normalize Boolean values loaded from CSV."""

    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return (
        series.astype("string")
        .str.strip()
        .str.casefold()
        .map({"true": True, "false": False, "1": True, "0": False})
        .fillna(False)
        .astype(bool)
    )


def load_analysis_data(input_path: Path) -> pd.DataFrame:
    """Load, validate, and retain only analysis-eligible records."""

    frame = pd.read_csv(input_path)
    validate_schema(frame)

    for column in [
        "PriceCAD",
        "Bath",
        "Parking",
        "AnalysisSizeSqft",
        "PricePerSqft",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    for column in [
        "AnalysisEligible",
        "OpenEndedSizeRange",
        "PriceOutlierIQR",
    ]:
        frame[column] = as_boolean(frame[column])

    frame = frame.loc[frame["AnalysisEligible"]].copy()
    frame = frame.dropna(subset=["Address", "SourceURL", "PriceCAD", "Room"])
    return frame.reset_index(drop=True)


def room_sort_key(value: Any) -> tuple[int, int, str]:
    """Sort Studio, bedroom, and bedroom-plus-den labels naturally."""

    label = str(value).strip()
    if label.casefold() == "studio":
        return (0, 0, label)

    parts = label.split("+", maxsplit=1)
    try:
        bedrooms = int(parts[0])
        dens = int(parts[1]) if len(parts) == 2 else 0
        return (bedrooms, dens, label)
    except ValueError:
        return (999, 999, label)


def build_overview(frame: pd.DataFrame) -> pd.DataFrame:
    """Create the headline project metrics."""

    closed_size = frame["AnalysisSizeSqft"].dropna()
    price_per_sqft = frame["PricePerSqft"].dropna()

    metrics: list[tuple[str, Any]] = [
        ("Listings", len(frame)),
        ("MedianRentCAD", frame["PriceCAD"].median()),
        ("MeanRentCAD", frame["PriceCAD"].mean()),
        ("RentQ1CAD", frame["PriceCAD"].quantile(0.25)),
        ("RentQ3CAD", frame["PriceCAD"].quantile(0.75)),
        ("MinimumRentCAD", frame["PriceCAD"].min()),
        ("MaximumRentCAD", frame["PriceCAD"].max()),
        ("ListingsWithClosedSizeRange", len(closed_size)),
        (
            "MedianAnalysisSizeSqft",
            closed_size.median() if not closed_size.empty else pd.NA,
        ),
        (
            "MedianPricePerSqftCAD",
            price_per_sqft.median() if not price_per_sqft.empty else pd.NA,
        ),
        ("OpenEndedSizeRangeListings", int(frame["OpenEndedSizeRange"].sum())),
        ("PriceOutlierListings", int(frame["PriceOutlierIQR"].sum())),
    ]
    return pd.DataFrame(metrics, columns=["Metric", "Value"])


def summarize_by_room(frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize asking rent by room configuration."""

    summary = (
        frame.groupby("Room", dropna=False)["PriceCAD"]
        .agg(
            Listings="count",
            MedianRentCAD="median",
            MeanRentCAD="mean",
            RentQ1CAD=lambda values: values.quantile(0.25),
            RentQ3CAD=lambda values: values.quantile(0.75),
        )
        .reset_index()
    )
    order = sorted(summary["Room"].tolist(), key=room_sort_key)
    order_lookup = {label: position for position, label in enumerate(order)}
    summary["_order"] = summary["Room"].map(order_lookup)
    return (
        summary.sort_values("_order")
        .drop(columns="_order")
        .reset_index(drop=True)
    )


def summarize_by_parking(frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize asking rent by parking-space count."""

    return (
        frame.groupby("Parking", dropna=False)["PriceCAD"]
        .agg(
            Listings="count",
            MedianRentCAD="median",
            MeanRentCAD="mean",
            RentQ1CAD=lambda values: values.quantile(0.25),
            RentQ3CAD=lambda values: values.quantile(0.75),
        )
        .reset_index()
        .sort_values("Parking")
        .reset_index(drop=True)
    )


def apply_chart_style() -> None:
    """Apply a restrained portfolio-oriented visual style."""

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": LIGHT_GREY,
            "axes.labelcolor": DARK_GREY,
            "axes.titlecolor": NAVY,
            "axes.titlesize": 17,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "xtick.color": MID_GREY,
            "ytick.color": MID_GREY,
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "grid.color": LIGHT_GREY,
            "grid.linewidth": 0.8,
            "grid.alpha": 0.8,
        }
    )


def currency_axis(value: float, position: int) -> str:
    """Format chart axes as whole Canadian-dollar values."""

    del position
    return f"${value:,.0f}"


def save_figure(fig: plt.Figure, path: Path) -> None:
    """Save and close one chart consistently."""

    fig.savefig(
        path,
        dpi=180,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)


def chart_rent_distribution(frame: pd.DataFrame, output_path: Path) -> None:
    """Plot the core distribution while retaining a view of all outliers."""

    prices = frame["PriceCAD"]
    display_limit = prices.quantile(0.99)
    display_prices = prices.loc[prices.le(display_limit)]
    median_rent = prices.median()

    fig, (hist_ax, box_ax) = plt.subplots(
        1,
        2,
        figsize=(12, 5.8),
        gridspec_kw={"width_ratios": [4.5, 1]},
    )

    hist_ax.hist(
        display_prices,
        bins=22,
        color=BLUE,
        edgecolor="white",
        linewidth=0.8,
    )
    hist_ax.axvline(
        median_rent,
        color=GOLD,
        linewidth=2.5,
        label=f"Median: ${median_rent:,.0f}",
    )
    hist_ax.set_title("Monthly Asking Rent Distribution", loc="left")
    hist_ax.set_xlabel("Monthly asking rent (CAD)")
    hist_ax.set_ylabel("Listings")
    hist_ax.xaxis.set_major_formatter(FuncFormatter(currency_axis))
    hist_ax.grid(axis="y")
    hist_ax.legend(frameon=False, loc="upper right")
    hist_ax.text(
        0,
        -0.19,
        "Histogram displayed through the 99th percentile; the box plot retains all observations.",
        transform=hist_ax.transAxes,
        color=MID_GREY,
        fontsize=9,
    )

    box_ax.boxplot(
        prices,
        vert=True,
        patch_artist=True,
        boxprops={"facecolor": LIGHT_BLUE, "edgecolor": BLUE},
        medianprops={"color": GOLD, "linewidth": 2.5},
        whiskerprops={"color": BLUE},
        capprops={"color": BLUE},
        flierprops={
            "marker": "o",
            "markerfacecolor": RED,
            "markeredgecolor": "white",
            "markersize": 4,
            "alpha": 0.75,
        },
    )
    box_ax.set_title("All Values", fontsize=12)
    box_ax.set_xticks([])
    box_ax.yaxis.set_major_formatter(FuncFormatter(currency_axis))
    box_ax.grid(axis="y")

    fig.subplots_adjust(wspace=0.28, bottom=0.22)
    save_figure(fig, output_path)


def chart_rent_by_room(
    room_summary: pd.DataFrame,
    output_path: Path,
    minimum_group_size: int = 5,
) -> None:
    """Plot median asking rent for sufficiently represented room groups."""

    chart_data = room_summary.loc[
        room_summary["Listings"].ge(minimum_group_size)
    ].copy()

    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.bar(
        chart_data["Room"],
        chart_data["MedianRentCAD"],
        color=TEAL,
        width=0.68,
    )
    ax.set_title("Median Asking Rent by Room Configuration", loc="left")
    ax.set_xlabel("Room configuration")
    ax.set_ylabel("Median monthly asking rent (CAD)")
    ax.yaxis.set_major_formatter(FuncFormatter(currency_axis))
    ax.grid(axis="y")
    ax.set_axisbelow(True)

    for bar, (_, row) in zip(bars, chart_data.iterrows()):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + chart_data["MedianRentCAD"].max() * 0.025,
            f"${row['MedianRentCAD']:,.0f}\n(n={int(row['Listings'])})",
            ha="center",
            va="bottom",
            fontsize=9,
            color=DARK_GREY,
        )

    ax.set_ylim(0, chart_data["MedianRentCAD"].max() * 1.22)
    ax.text(
        0,
        -0.17,
        f"Only room groups with at least {minimum_group_size} listings are displayed.",
        transform=ax.transAxes,
        color=MID_GREY,
        fontsize=9,
    )
    fig.subplots_adjust(bottom=0.2)
    save_figure(fig, output_path)


def chart_rent_by_parking(
    parking_summary: pd.DataFrame,
    output_path: Path,
    minimum_group_size: int = 5,
) -> None:
    """Plot median asking rent by reported parking-space count."""

    chart_data = parking_summary.loc[
        parking_summary["Listings"].ge(minimum_group_size)
    ].copy()
    labels = [str(int(value)) for value in chart_data["Parking"]]
    x_positions = np.arange(len(chart_data))

    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    bars = ax.bar(
        x_positions,
        chart_data["MedianRentCAD"],
        color=[BLUE, TEAL, GOLD, RED][: len(chart_data)],
        width=0.62,
    )
    ax.set_title("Median Asking Rent by Parking Availability", loc="left")
    ax.set_xlabel("Reported parking spaces")
    ax.set_ylabel("Median monthly asking rent (CAD)")
    ax.yaxis.set_major_formatter(FuncFormatter(currency_axis))
    ax.set_xticks(x_positions, labels)
    ax.grid(axis="y")
    ax.set_axisbelow(True)

    for bar, (_, row) in zip(bars, chart_data.iterrows()):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + chart_data["MedianRentCAD"].max() * 0.025,
            f"${row['MedianRentCAD']:,.0f}\n(n={int(row['Listings'])})",
            ha="center",
            va="bottom",
            fontsize=9,
            color=DARK_GREY,
        )

    ax.set_ylim(0, chart_data["MedianRentCAD"].max() * 1.23)
    ax.text(
        0,
        -0.17,
        "Groups with fewer than 5 listings are omitted. Unadjusted comparison; "
        "differences may also reflect size and room count.",
        transform=ax.transAxes,
        color=MID_GREY,
        fontsize=9,
    )
    fig.subplots_adjust(bottom=0.2)
    save_figure(fig, output_path)


def chart_rent_vs_size(frame: pd.DataFrame, output_path: Path) -> None:
    """Plot asking rent against the midpoint of closed size ranges."""

    chart_data = frame.dropna(
        subset=["AnalysisSizeSqft", "PriceCAD"]
    ).copy()
    regular = chart_data.loc[~chart_data["PriceOutlierIQR"]]
    outliers = chart_data.loc[chart_data["PriceOutlierIQR"]]

    fig, ax = plt.subplots(figsize=(11, 6.3))
    ax.scatter(
        regular["AnalysisSizeSqft"],
        regular["PriceCAD"],
        s=35,
        color=BLUE,
        alpha=0.62,
        edgecolor="white",
        linewidth=0.4,
        label="Within IQR bounds",
    )
    if not outliers.empty:
        ax.scatter(
            outliers["AnalysisSizeSqft"],
            outliers["PriceCAD"],
            s=45,
            color=RED,
            alpha=0.82,
            edgecolor="white",
            linewidth=0.5,
            label="IQR price flag",
        )

    if len(regular) >= 2:
        coefficients = np.polyfit(
            regular["AnalysisSizeSqft"],
            regular["PriceCAD"],
            deg=1,
        )
        x_values = np.linspace(
            regular["AnalysisSizeSqft"].min(),
            regular["AnalysisSizeSqft"].max(),
            100,
        )
        ax.plot(
            x_values,
            coefficients[0] * x_values + coefficients[1],
            color=GOLD,
            linewidth=2.4,
            label="Linear trend (unflagged listings)",
        )

    ax.set_title("Asking Rent and Approximate Unit Size", loc="left")
    ax.set_xlabel("Approximate size (sqft midpoint)")
    ax.set_ylabel("Monthly asking rent (CAD)")
    ax.yaxis.set_major_formatter(FuncFormatter(currency_axis))
    ax.grid()
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left")
    ax.text(
        0,
        -0.17,
        "Uses only closed reported size ranges; size is a range midpoint, not an exact measurement.",
        transform=ax.transAxes,
        color=MID_GREY,
        fontsize=9,
    )
    fig.subplots_adjust(bottom=0.2)
    save_figure(fig, output_path)


def save_tables(
    output_dir: Path,
    overview: pd.DataFrame,
    room_summary: pd.DataFrame,
    parking_summary: pd.DataFrame,
) -> tuple[Path, Path, Path]:
    """Save reusable summary tables."""

    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    overview_path = tables_dir / "analysis_overview.csv"
    room_path = tables_dir / "rent_by_room.csv"
    parking_path = tables_dir / "rent_by_parking.csv"

    overview.to_csv(overview_path, index=False, encoding="utf-8-sig")
    room_summary.to_csv(room_path, index=False, encoding="utf-8-sig")
    parking_summary.to_csv(parking_path, index=False, encoding="utf-8-sig")
    return overview_path, room_path, parking_path


def run_analysis(
    input_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path]:
    """Generate all summary tables and charts."""

    frame = load_analysis_data(input_path)
    overview = build_overview(frame)
    room_summary = summarize_by_room(frame)
    parking_summary = summarize_by_parking(frame)

    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    apply_chart_style()

    chart_paths = {
        "rent_distribution": charts_dir / "rent_distribution.png",
        "rent_by_room": charts_dir / "median_rent_by_room.png",
        "rent_by_parking": charts_dir / "median_rent_by_parking.png",
        "rent_vs_size": charts_dir / "rent_vs_size.png",
    }
    chart_rent_distribution(frame, chart_paths["rent_distribution"])
    chart_rent_by_room(room_summary, chart_paths["rent_by_room"])
    chart_rent_by_parking(parking_summary, chart_paths["rent_by_parking"])
    chart_rent_vs_size(frame, chart_paths["rent_vs_size"])

    table_paths = save_tables(
        output_dir=output_dir,
        overview=overview,
        room_summary=room_summary,
        parking_summary=parking_summary,
    )
    paths = {
        **chart_paths,
        "overview_table": table_paths[0],
        "room_table": table_paths[1],
        "parking_table": table_paths[2],
    }

    logging.info(
        "Finished: %s listings summarized; %s charts created.",
        len(frame),
        len(chart_paths),
    )
    for label, path in paths.items():
        logging.debug("%s: %s", label, path)
    return paths


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""

    parser = argparse.ArgumentParser(
        description="Analyze cleaned Toronto condo rental data."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Analysis-ready CSV produced by clean_data.py.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Table and chart directory (default: outputs).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main() -> None:
    """Run the command-line analysis."""

    args = build_parser().parse_args()
    configure_logging(verbose=args.verbose)
    run_analysis(input_path=args.input, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
