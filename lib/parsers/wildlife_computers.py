"""Parser for Wildlife Computers merged Locations.csv exports.

Expected columns (as produced by WC Portal / DAP Processor):
DeployID, Ptt, Instr, Date, Type, Quality, Latitude, Longitude,
Error radius, Error Semi-major axis, Error Semi-minor axis,
Error Ellipse orientation, Offset, Offset orientation, GPE MSD, GPE U,
Count, Comment
"""
from __future__ import annotations

import pandas as pd

from lib.quality import harmonize

REQUIRED_COLUMNS = ["DeployID", "Ptt", "Instr", "Date", "Type", "Quality", "Latitude", "Longitude"]

METADATA_COLUMNS = [
    "Error radius",
    "Error Semi-major axis",
    "Error Semi-minor axis",
    "Error Ellipse orientation",
    "Offset",
    "Offset orientation",
    "GPE MSD",
    "GPE U",
    "Count",
    "Comment",
]


def parse_wc_locations(filepath_or_buffer) -> pd.DataFrame:
    """Parse a WC merged Locations.csv into the normalized positions schema:
    deploy_id, ptt, instrument_model, ts, latitude, longitude, location_type,
    quality_raw, quality_class, raw_metadata.

    Rows with no location fix (blank Latitude/Longitude) and exact duplicate
    rows are dropped. The number of duplicates removed is stashed in
    `.attrs["dupes_removed"]` for display purposes.
    """
    df = pd.read_csv(filepath_or_buffer, dtype=str)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.dropna(subset=["Latitude", "Longitude"]).copy()
    if df.empty:
        return df

    df["ts"] = pd.to_datetime(df["Date"], format="%H:%M:%S %d-%b-%Y", utc=True)
    df["latitude"] = df["Latitude"].astype(float)
    df["longitude"] = df["Longitude"].astype(float)
    df["quality_raw"] = df["Quality"]
    df["quality_class"] = [
        harmonize(t, q) for t, q in zip(df["Type"], df["Quality"])
    ]

    present_metadata_cols = [c for c in METADATA_COLUMNS if c in df.columns]
    df["raw_metadata"] = df[present_metadata_cols].apply(
        lambda row: {k: v for k, v in row.dropna().items()}, axis=1
    )

    out = df[
        ["DeployID", "Ptt", "Instr", "ts", "latitude", "longitude", "Type", "quality_raw", "quality_class", "raw_metadata"]
    ].rename(
        columns={
            "DeployID": "deploy_id",
            "Ptt": "ptt",
            "Instr": "instrument_model",
            "Type": "location_type",
        }
    )

    before = len(out)
    out = out.drop_duplicates(subset=["deploy_id", "ts", "latitude", "longitude"])
    out.attrs["dupes_removed"] = before - len(out)

    return out.sort_values("ts").reset_index(drop=True)
