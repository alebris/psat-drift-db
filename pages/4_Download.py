import json

import pandas as pd
import streamlit as st

from lib.auth import require_login, current_user
from lib.db import get_client

st.set_page_config(page_title="Download", page_icon="\u2b07\ufe0f", layout="wide")
require_login()
user = current_user()
client = get_client()

st.title("Query and download")

col1, col2 = st.columns(2)
lat_min = col1.number_input("Min latitude", value=-90.0, min_value=-90.0, max_value=90.0)
lat_max = col1.number_input("Max latitude", value=90.0, min_value=-90.0, max_value=90.0)
lon_min = col2.number_input("Min longitude", value=-180.0, min_value=-180.0, max_value=180.0)
lon_max = col2.number_input("Max longitude", value=180.0, min_value=-180.0, max_value=180.0)

date_range = st.date_input("Date range (optional)", value=())
quality_filter = st.multiselect(
    "Quality", ["high", "medium", "low", "unusable", "unknown"], default=["high", "medium", "low"]
)

if st.button("Run query", type="primary"):
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

    res = query.execute()
    st.session_state["query_result"] = pd.DataFrame(res.data)
    st.session_state["query_filters"] = {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
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
