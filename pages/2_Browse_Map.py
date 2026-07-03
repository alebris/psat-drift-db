import pandas as pd
import pydeck as pdk
import streamlit as st

from lib.auth import require_login
from lib.db import get_client

st.set_page_config(page_title="Browse map", page_icon="\U0001F5FA\ufe0f", layout="wide")
require_login()
client = get_client()

st.title("Browse drift tracks")

QUALITY_COLORS = {
    "high": [26, 152, 80],
    "medium": [255, 191, 0],
    "low": [214, 39, 40],
    "unusable": [120, 120, 120],
    "unknown": [80, 80, 80],
}


@st.cache_data(ttl=300)
def load_deployments():
    res = client.table("deployments").select("id, deploy_id, species, manufacturer, uploaded_at").execute()
    return pd.DataFrame(res.data)


deployments = load_deployments()

if deployments.empty:
    st.info("No data uploaded yet.")
    st.stop()

selected = st.multiselect(
    "Deployments",
    options=list(deployments["id"]),
    default=list(deployments["id"]),
    format_func=lambda i: deployments.loc[deployments["id"] == i, "deploy_id"].values[0],
)
quality_filter = st.multiselect(
    "Quality", ["high", "medium", "low", "unusable", "unknown"], default=["high", "medium", "low"]
)

if not selected or not quality_filter:
    st.warning("Select at least one deployment and one quality level.")
    st.stop()


@st.cache_data(ttl=300)
def load_positions(deployment_ids, qualities):
    res = (
        client.table("positions")
        .select("deployment_id, ts, latitude, longitude, location_type, quality_class")
        .in_("deployment_id", deployment_ids)
        .in_("quality_class", qualities)
        .execute()
    )
    return pd.DataFrame(res.data)


positions = load_positions(selected, quality_filter)

if positions.empty:
    st.warning("No positions match these filters.")
    st.stop()

positions["color"] = positions["quality_class"].map(QUALITY_COLORS)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=positions,
    get_position="[longitude, latitude]",
    get_fill_color="color",
    get_radius=2000,
    pickable=True,
)
view_state = pdk.ViewState(
    latitude=positions["latitude"].mean(),
    longitude=positions["longitude"].mean(),
    zoom=5,
)
st.pydeck_chart(
    pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{ts}\nquality: {quality_class}"})
)

st.caption(f"{len(positions)} positions shown. Colors: green = high quality, amber = medium, red = low, grey = unusable/unknown.")
