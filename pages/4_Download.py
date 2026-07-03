import json

import folium
import pandas as pd
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium

from lib.auth import require_login, current_user
from lib.db import get_client
from lib.maps import ocean_basemap
from lib.style import apply_custom_css

st.set_page_config(page_title="Download", page_icon="\u2b07\ufe0f", layout="wide")
apply_custom_css()
require_login()
user = current_user()
client = get_client()

st.title("Query and download")
st.caption(
    "Draw a rectangle on the map to limit results to that area — or skip drawing entirely "
    "and use only the time period below to query by date alone."
)

if "query_bbox" not in st.session_state:
    st.session_state["query_bbox"] = None
if "query_map_generation" not in st.session_state:
    st.session_state["query_map_generation"] = 0

fmap = folium.Map(location=[20, 0], zoom_start=2, tiles=None, control_scale=True, prefer_canvas=True)
ocean_basemap(fmap)

if st.session_state["query_bbox"]:
    b = st.session_state["query_bbox"]
    folium.Rectangle(
        bounds=[[b["lat_min"], b["lon_min"]], [b["lat_max"], b["lon_max"]]],
        color="#3366aa",
        weight=2,
        fill=True,
        fill_opacity=0.08,
    ).add_to(fmap)

Draw(
    export=False,
    draw_options={
        "rectangle": {"shapeOptions": {"color": "#3366aa"}},
        "polygon": False,
        "circle": False,
        "circlemarker": False,
        "marker": False,
        "polyline": False,
    },
    edit_options={"edit": False, "remove": False},
).add_to(fmap)

map_data = st_folium(
    fmap,
    use_container_width=True,
    height=500,
    key=f"query_map_{st.session_state['query_map_generation']}",
)

last_drawing = map_data.get("last_active_drawing") if map_data else None
if last_drawing:
    coords = last_drawing["geometry"]["coordinates"][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    new_bbox = {"lat_min": min(lats), "lat_max": max(lats), "lon_min": min(lons), "lon_max": max(lons)}
    if new_bbox != st.session_state["query_bbox"]:
        st.session_state["query_bbox"] = new_bbox
        st.rerun()

col_a, col_b = st.columns([4, 1])
with col_a:
    if st.session_state["query_bbox"]:
        b = st.session_state["query_bbox"]
        st.caption(
            f"Area selected: lat {b['lat_min']:.2f} to {b['lat_max']:.2f}, "
            f"lon {b['lon_min']:.2f} to {b['lon_max']:.2f}"
        )
    else:
        st.caption("No area drawn \u2014 spatial filter won't be applied; search covers everywhere.")
with col_b:
    if st.session_state["query_bbox"]:
        if st.button("Clear drawn area", use_container_width=True):
            st.session_state["query_bbox"] = None
            st.session_state["query_map_generation"] += 1
            st.rerun()

date_range = st.date_input("Time period (optional)", value=())
quality_filter = st.multiselect(
    "Quality", ["high", "medium", "low", "unusable", "unknown"], default=["high", "medium", "low"]
)

if st.button("Run query", type="primary"):
    query = (
        client.table("positions")
        .select(
            "deployment_id, ts, latitude, longitude, location_type, quality_raw, quality_class, "
            "deployments(deploy_id, species, manufacturer)"
        )
        .in_("quality_class", quality_filter)
    )

    bbox = st.session_state["query_bbox"]
    if bbox:
        query = (
            query.gte("latitude", bbox["lat_min"])
            .lte("latitude", bbox["lat_max"])
            .gte("longitude", bbox["lon_min"])
            .lte("longitude", bbox["lon_max"])
        )
    if len(date_range) == 2:
        query = query.gte("ts", date_range[0].isoformat()).lte("ts", date_range[1].isoformat())

    res = query.execute()
    st.session_state["query_result"] = pd.DataFrame(res.data)
    st.session_state["query_filters"] = {
        "bbox": bbox,
        "quality": quality_filter,
        "date_range": [d.isoformat() for d in date_range] if len(date_range) == 2 else None,
    }

df = st.session_state.get("query_result")
filters = st.session_state.get("query_filters", {})

if df is not None:
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
