import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from lib.auth import require_login
from lib.db import get_client

st.set_page_config(page_title="Browse map", page_icon="\U0001F5FA\ufe0f", layout="wide")
require_login()
client = get_client()

st.title("Browse drift tracks")

QUALITY_COLORS = {
    "high": "#1a9850",
    "medium": "#f2b705",
    "low": "#d62728",
    "unusable": "#888888",
    "unknown": "#555555",
}


def ocean_basemap(fmap):
    """Add an ocean-styled basemap. Uses MapTiler's Ocean style when a key is
    configured in secrets; otherwise falls back to Esri's keyless Ocean
    basemap so the app still looks right out of the box."""
    key = st.secrets.get("MAPTILER_KEY", None)
    if key:
        folium.TileLayer(
            tiles=f"https://api.maptiler.com/maps/ocean/{{z}}/{{x}}/{{y}}.png?key={key}",
            attr="\u00a9 MapTiler \u00a9 OpenStreetMap contributors",
            name="MapTiler Ocean",
            control=False,
        ).add_to(fmap)
    else:
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}",
            attr="Esri, GEBCO, NOAA, National Geographic, and other contributors",
            name="Esri Ocean",
            control=False,
        ).add_to(fmap)
        # light labels/reference overlay on top of the ocean base
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Reference/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Ocean reference",
            control=False,
            overlay=True,
        ).add_to(fmap)


@st.cache_data(ttl=300)
def load_deployments():
    res = client.table("deployments").select("id, deploy_id, species, manufacturer, uploaded_at").execute()
    return pd.DataFrame(res.data)


@st.cache_data(ttl=300)
def load_positions(deployment_ids, qualities):
    res = (
        client.table("positions")
        .select("deployment_id, ts, latitude, longitude, location_type, quality_class")
        .in_("deployment_id", deployment_ids)
        .in_("quality_class", qualities)
        .order("ts")
        .execute()
    )
    return pd.DataFrame(res.data)


deployments = load_deployments()
if deployments.empty:
    st.info("No data uploaded yet.")
    st.stop()

col_a, col_b = st.columns(2)
selected = col_a.multiselect(
    "Deployments",
    options=list(deployments["id"]),
    default=list(deployments["id"]),
    format_func=lambda i: deployments.loc[deployments["id"] == i, "deploy_id"].values[0],
)
quality_filter = col_b.multiselect(
    "Quality", ["high", "medium", "low", "unusable", "unknown"], default=["high", "medium", "low"]
)
show_tracks = st.checkbox("Connect points into drift tracks", value=True)

if not selected or not quality_filter:
    st.warning("Select at least one deployment and one quality level.")
    st.stop()

positions = load_positions(selected, quality_filter)
if positions.empty:
    st.warning("No positions match these filters.")
    st.stop()

center = [positions["latitude"].mean(), positions["longitude"].mean()]
fmap = folium.Map(location=center, zoom_start=5, tiles=None, control_scale=True)
ocean_basemap(fmap)

id_to_deploy = dict(zip(deployments["id"], deployments["deploy_id"]))

for deployment_id, group in positions.groupby("deployment_id"):
    group = group.sort_values("ts")
    deploy_label = id_to_deploy.get(deployment_id, str(deployment_id))

    if show_tracks and len(group) > 1:
        folium.PolyLine(
            locations=group[["latitude", "longitude"]].values.tolist(),
            color="#3366aa",
            weight=1.5,
            opacity=0.6,
        ).add_to(fmap)

    for _, row in group.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=4,
            color=None,
            fill=True,
            fill_color=QUALITY_COLORS.get(row["quality_class"], "#555555"),
            fill_opacity=0.85,
            popup=folium.Popup(
                f"<b>{deploy_label}</b><br>{row['ts']}<br>"
                f"type: {row['location_type']}<br>quality: {row['quality_class']}",
                max_width=220,
            ),
        ).add_to(fmap)

st_folium(fmap, use_container_width=True, height=600, returned_objects=[])

legend = "  ".join(
    f"<span style='color:{c}'>\u25cf</span> {q}" for q, c in QUALITY_COLORS.items()
)
st.markdown(f"{len(positions)} positions shown.  &nbsp; {legend}", unsafe_allow_html=True)
