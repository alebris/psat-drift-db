"""Post-upload data cleaning.

Drift positions come from tags floating at the sea surface, so any fix that
falls on land is a location error (common with lower-quality Argos classes).
`remove_land_points` drops those rows using a global coastline mask.

Resolution note: global-land-mask uses a ~1 km (0.01-degree) grid, so fixes
within roughly a grid cell of the coastline may not be perfectly classified.
This is appropriate for stripping clearly-erroneous inland fixes, not for
sub-kilometre coastal precision.
"""
from __future__ import annotations

import pandas as pd
from global_land_mask import globe


def remove_land_points(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of `df` with on-land positions removed.

    Expects `latitude` and `longitude` columns. The number of rows removed is
    recorded in `.attrs["land_removed"]`.
    """
    if df.empty:
        df.attrs["land_removed"] = 0
        return df

    on_land = [
        bool(globe.is_land(lat, lon))
        for lat, lon in zip(df["latitude"], df["longitude"])
    ]
    mask = [not x for x in on_land]
    cleaned = df[mask].copy()
    cleaned.attrs["land_removed"] = int(sum(on_land))
    return cleaned.reset_index(drop=True)
