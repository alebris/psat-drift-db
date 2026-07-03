"""Post-upload data cleaning.

Drift positions come from tags floating at the sea surface, so any fix that
falls on land is a location error (common with lower-quality Argos classes).
`remove_land_points` drops those rows using a global coastline mask.

`remove_unrealistic_speed` drops fixes that imply an unrealistic drift speed
from the previous accepted fix in the same deployment — another common
signature of a bad Argos location.

Resolution note: global-land-mask uses a ~1 km (0.01-degree) grid, so fixes
within roughly a grid cell of the coastline may not be perfectly classified.
This is appropriate for stripping clearly-erroneous inland fixes, not for
sub-kilometre coastal precision.
"""
from __future__ import annotations

import math

import pandas as pd
from global_land_mask import globe

EARTH_RADIUS_KM = 6371.0


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


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def remove_unrealistic_speed(df: pd.DataFrame, max_speed_kmh: float) -> pd.DataFrame:
    """Return a copy of `df` with implausibly fast fixes removed.

    Sequential filter, per `deploy_id`, sorted by `ts`: each point is
    compared to the last *accepted* point (not simply the previous row), so
    one bad fix can't cascade into rejecting every point after it. The first
    point of each deployment is always kept, since there's no prior
    reference to judge it against — a known limitation of this simple
    approach (a bad first fix isn't caught). A more robust forward-backward
    filter could replace this later if that turns out to matter in practice.

    Requires `deploy_id`, `ts`, `latitude`, `longitude` columns. The number
    of rows removed is recorded in `.attrs["speed_removed"]`.
    """
    if df.empty or "deploy_id" not in df.columns:
        df.attrs["speed_removed"] = 0
        return df

    keep_flags = pd.Series(True, index=df.index)

    for _, group in df.groupby("deploy_id", sort=False):
        group = group.sort_values("ts")
        last_lat = last_lon = last_ts = None
        for idx, row in group.iterrows():
            if last_ts is None:
                last_lat, last_lon, last_ts = row["latitude"], row["longitude"], row["ts"]
                continue
            dt_hours = (row["ts"] - last_ts).total_seconds() / 3600.0
            dist_km = _haversine_km(last_lat, last_lon, row["latitude"], row["longitude"])
            speed = dist_km / dt_hours if dt_hours > 0 else float("inf")
            if speed > max_speed_kmh:
                keep_flags[idx] = False
                continue
            last_lat, last_lon, last_ts = row["latitude"], row["longitude"], row["ts"]

    cleaned = df[keep_flags].copy()
    cleaned.attrs["speed_removed"] = int((~keep_flags).sum())
    return cleaned.sort_values("ts").reset_index(drop=True)
