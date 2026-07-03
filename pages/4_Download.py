import json

import pandas as pd
import streamlit as st

from lib.auth import require_login, current_user
from lib.db import get_client
from lib.style import apply_style

st.set_page_config(page_title="Download", page_icon="⬇️", layout="wide")
apply_style()
require_login()
user = current_user()
client = get_client()

st.title("Query and download")
st.caption("Combine any of the filters below to scope your query, then export the results.")


@st.cache_data(ttl=300)
def load_deployments():
    res = client.table("deployments").select("id, deploy_id, species, manufacturer").execute()
    return pd.DataFrame(res.data)


bbox = st.session_state.pop("download_bbox", None)
if bbox:
    st.session_state["dl_lat_min"] = bbox["lat_min"]
    st.session_state["dl_lat_max"] = bbox["lat_max"]
    st.session_state["dl_lon_min"] = bbox["lon_min"]
    st.session_state["dl_lon_max"] = bbox["lon_max"]
    st.success("Area pre-filled from your Browse Map selection.")

st.subheader("Area")
col1, col2 = st.columns(2)
lat_min = col1.number_input(
    "Min latitude", min_value=-90.0, max_value=90.0, value=st.session_state.get("dl_lat_min", -90.0), key="dl_lat_min"
)
lat_max = col1.number_input(
    "Max latitude", min_value=-90.0, max_value=90.0, value=st.session_state.get("dl_lat_max", 90.0), key="dl_lat_max"
)
lon_min = col2.number_input(
    "Min longitude", min_value=-180.0, max_value=180.0, value=st.session_state.get("dl_lon_min", -180.0), key="dl_lon_min"
)
lon_max = col2.number_input(
    "Max longitude", min_value=-180.0, max_value=180.0, value=st.session_state.get("dl_lon_max", 180.0), key="dl_lon_max"
)

st.subheader("Time period")
date_range = st.date_input("Date range (optional)", value=())

st.subheader("Quality")
quality_filter = st.multiselect(
    "Quality", ["high", "medium", "low", "unusable", "unknown"], default=["high", "medium", "low"]
)

st.subheader("Specific tags")
use_tag_filter = st.checkbox("Filter by specific tag(s) instead of the whole area")
selected_deploy_ids = []
if use_tag_filter:
    deployments = load_deployments()
    if deployments.empty:
        st.info("No tags available yet.")
    else:
        deployments["label"] = deployments.apply(
            lambda r: f"{r['deploy_id']}" + (f" — {r['species']}" if r.get("species") else ""), axis=1
        )
        label_to_id = dict(zip(deployments["label"], deployments["id"]))
        selected_labels = st.multiselect("Tags", sorted(label_to_id.keys()))
        selected_deploy_ids = [label_to_id[l] for l in selected_labels]

if st.button("Run query", type="primary"):
    if use_tag_filter and not selected_deploy_ids:
        st.warning("Select at least one tag, or uncheck the tag filter.")
        st.stop()
    if not quality_filter:
        st.warning("Select at least one quality level.")
        st.stop()

    query = (
        client.table("positions")
        .select("deployment_id, ts, latitude, longitude, location_type, quality_raw, quality_class, deployments(deploy_id, species, manufacturer)")
        .gte("latitude", lat_min)
        .lte("latitude", lat_max)
        .gte("longitude", lon_min)
        .lte("longitude", lon_max)
        .in_("quality_class", quality_filter)
    )
    if len(date_range) == 2:
        query = query.gte("ts", date_range[0].isoformat()).lte("ts", date_range[1].isoformat())
    if use_tag_filter:
        query = query.in_("deployment_id", selected_deploy_ids)

    res = query.execute()
    st.session_state["query_result"] = pd.DataFrame(res.data)
    st.session_state["query_filters"] = {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
        "quality": quality_filter,
        "date_range": [d.isoformat() for d in date_range] if len(date_range) == 2 else None,
        "tags": selected_labels if use_tag_filter else None,
    }

df = st.session_state.get("query_result")
filters = st.session_state.get("query_filters", {})

if df is not None:
    st.divider()
    st.write(f"{len(df)} positions match.")
    st.dataframe(df.head(50), use_container_width=True)

    if not df.empty:

        def log_download(row_count, filters):
            client.table("downloads").insert(
                {"user_id": user.id, "filters": filters, "row_count": row_count}
            ).execute()

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            csv_bytes,
            "psat_drift_export.csv",
            "text/csv",
            on_click=log_download,
            args=(len(df), filters),
        )

        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
                "properties": {k: v for k, v in row.items() if k not in ("latitude", "longitude")},
            }
            for _, row in df.iterrows()
        ]
        geojson_str = json.dumps({"type": "FeatureCollection", "features": features})
        st.download_button(
            "Download GeoJSON",
            geojson_str,
            "psat_drift_export.geojson",
            "application/geo+json",
            on_click=log_download,
            args=(len(df), filters),
        )
