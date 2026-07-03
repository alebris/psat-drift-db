"""Shared basemap and styling helpers for the Browse and Download map pages."""
import folium
import streamlit as st

QUALITY_COLORS = {
    "high": "#1a9850",
    "medium": "#f2b705",
    "low": "#d62728",
    "unusable": "#888888",
    "unknown": "#555555",
}


def ocean_basemap(fmap: folium.Map) -> None:
    """Adds an ocean-styled basemap to `fmap`.

    Uses a MapTiler style (yours, or the built-in "ocean" preset) when
    MAPTILER_KEY is set in secrets — a single tile layer with labels baked
    in. Falls back to Esri's keyless Ocean basemap otherwise. Deliberately
    a single TileLayer either way: stacking a separate labels overlay on
    top roughly doubles tile requests on every pan/zoom, which was a real
    contributor to the map feeling slow.
    """
    key = st.secrets.get("MAPTILER_KEY", None)
    style = st.secrets.get("MAPTILER_STYLE_ID", "ocean")

    if key:
        folium.TileLayer(
            tiles=f"https://api.maptiler.com/maps/{style}/{{z}}/{{x}}/{{y}}.png?key={key}",
            attr="\u00a9 MapTiler \u00a9 OpenStreetMap contributors",
            name="MapTiler",
            control=False,
            max_zoom=20,
        ).add_to(fmap)
    else:
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}",
            attr="Esri, GEBCO, NOAA, National Geographic, and other contributors",
            name="Esri Ocean",
            control=False,
            max_zoom=13,
        ).add_to(fmap)
