import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from lib.db import get_client
from lib.quality import QUALITY_COLORS
from lib.style import apply_style

st.set_page_config(page_title="Browse map", page_icon="\U0001F5FA️", layout="wide")
apply_style()
client = get_client()

title_col, refresh_col = st.columns([5, 1])
title_col.title("Browse drift tracks")
if refresh_col.button("\U0001F504 Refresh data", use_container_width=True, help="Reload the latest data from the database (bypasses the 5-minute cache)."):
    st.cache_data.clear()
    st.rerun()

if "selected_deployment" not in st.session_state:
    st.session_state["selected_deployment"] = None


def ocean_basemap(fmap):
    key = st.secrets.get("MAPTILER_KEY", None)
    if key:
        folium.TileLayer(
            tiles=f"https://api.maptiler.com/maps/ocean/{{z}}/{{x}}/{{y}}.png?key={key}",
            attr="© MapTiler © OpenStreetMap contributors",
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

id_to_deploy = dict(zip(deployments["id"], deployments["deploy_id"]))
deploy_to_id = dict(zip(deployments["deploy_id"], deployments["id"]))

top_col1, top_col2, top_col3 = st.columns([2, 2, 1])
quality_filter = top_col1.multiselect(
    "Quality", ["high", "medium", "low", "unusable", "unknown"], default=["high", "medium", "low"]
)
show_tracks = top_col2.checkbox("Connect points into drift tracks", value=True)

selected_id = st.session_state["selected_deployment"]
if selected_id:
    top_col3.button(
        "Show all deployments",
        on_click=lambda: st.session_state.update(selected_deployment=None),
        use_container_width=True,
    )
    st.caption(f"Showing only deployment **{id_to_deploy.get(selected_id, selected_id)}**.")

with st.expander("\U0001F4E6 Query area — draw a bounding box to send to the Download page"):
    st.caption(
        "Enter coordinates to draw a box on the map below, then send that area to the "
        "Download page to query positions within it — similar to GEBCO's grid subsetting tool."
    )
    with st.form("bbox_form"):
        b1, b2 = st.columns(2)
        box_lat_min = b1.number_input("Min latitude", value=-90.0, min_value=-90.0, max_value=90.0)
        box_lat_max = b1.number_input("Max latitude", value=90.0, min_value=-90.0, max_value=90.0)
        box_lon_min = b2.number_input("Min longitude", value=-180.0, min_value=-180.0, max_value=180.0)
        box_lon_max = b2.number_input("Max longitude", value=180.0, min_value=-180.0, max_value=180.0)
        draw_submitted = st.form_submit_button("Draw box on map")

    if draw_submitted:
        st.session_state["map_bbox"] = {
            "lat_min": box_lat_min,
            "lat_max": box_lat_max,
            "lon_min": box_lon_min,
            "lon_max": box_lon_max,
        }

    map_bbox = st.session_state.get("map_bbox")
    if map_bbox:
        bc1, bc2, bc3 = st.columns([1, 1.6, 3])
        if bc1.button("Clear box"):
            del st.session_state["map_bbox"]
            st.rerun()
        if bc2.button("Use this area on Download page →", type="primary"):
            st.session_state["download_bbox"] = map_bbox
            st.switch_page("pages/4_Download.py")

if not quality_filter:
    st.warning("Select at least one quality level.")
    st.stop()

deployment_ids = [selected_id] if selected_id else list(deployments["id"])
positions = load_positions(deployment_ids, quality_filter)

if positions.empty:
    st.warning("No positions match these filters.")
    st.stop()

center = [positions["latitude"].mean(), positions["longitude"].mean()]
fmap = folium.Map(location=center, zoom_start=5, tiles=None, control_scale=True)
ocean_basemap(fmap)

map_bbox = st.session_state.get("map_bbox")
if map_bbox:
    folium.Rectangle(
        bounds=[
            [map_bbox["lat_min"], map_bbox["lon_min"]],
            [map_bbox["lat_max"], map_bbox["lon_max"]],
        ],
        color="#0f6f8c",
        weight=2,
        fill=True,
        fill_color="#0f6f8c",
        fill_opacity=0.08,
        tooltip="Query area",
    ).add_to(fmap)

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
            stroke=False,
            fill=True,
            fill_color=QUALITY_COLORS.get(row["quality_class"], "#555555"),
            fill_opacity=0.9,
            tooltip=deploy_label,
            popup=folium.Popup(
                f"<b>{deploy_label}</b><br>{row['ts']}<br>"
                f"type: {row['location_type']}<br>quality: {row['quality_class']}",
                max_width=220,
            ),
        ).add_to(fmap)

map_data = st_folium(fmap, use_container_width=True, height=820)

clicked_label = map_data.get("last_object_clicked_tooltip") if map_data else None
clicked_id = deploy_to_id.get(clicked_label) if clicked_label else None

if clicked_id and clicked_id != selected_id:
    st.button(
        f"Show only deployment {clicked_label}",
        type="primary",
        on_click=lambda cid=clicked_id: st.session_state.update(selected_deployment=cid),
    )

legend = "  ".join(
    f"<span style='color:{c}'>●</span> {q}" for q, c in QUALITY_COLORS.items()
)
st.markdown(f"{len(positions)} positions shown.  &nbsp; {legend}", unsafe_allow_html=True)
