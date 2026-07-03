import pandas as pd
import plotly.express as px
import streamlit as st

from lib.db import get_client
from lib.quality import QUALITY_COLORS
from lib.style import apply_style

st.set_page_config(page_title="Statistics", page_icon="\U0001F4CA", layout="wide")
apply_style()
client = get_client()

st.title("Database statistics")


@st.cache_data(ttl=300)
def load_summary():
    deployments = pd.DataFrame(
        client.table("deployments").select("id, manufacturer, species, uploaded_at").execute().data
    )
    positions = pd.DataFrame(
        client.table("positions").select("id, deployment_id, ts, quality_class").execute().data
    )
    return deployments, positions


deployments, positions = load_summary()

col1, col2, col3 = st.columns(3)
col1.metric("Tag deployments", len(deployments))
col2.metric("Total positions", len(positions))
col3.metric("Manufacturers represented", deployments["manufacturer"].nunique() if not deployments.empty else 0)

if not positions.empty:
    fig = px.pie(
        positions,
        names="quality_class",
        title="Position quality distribution",
        color="quality_class",
        color_discrete_map=QUALITY_COLORS,
    )
    st.plotly_chart(fig, use_container_width=True)

    positions["ts"] = pd.to_datetime(positions["ts"])
    by_month = positions.set_index("ts").resample("MS").size().reset_index(name="count")
    fig2 = px.bar(by_month, x="ts", y="count", title="Positions per month", color_discrete_sequence=["#0f6f8c"])
    st.plotly_chart(fig2, use_container_width=True)

if not deployments.empty:
    counts = deployments["manufacturer"].value_counts().reset_index()
    counts.columns = ["manufacturer", "count"]
    fig3 = px.bar(
        counts, x="manufacturer", y="count", title="Deployments per manufacturer",
        color_discrete_sequence=["#0f6f8c"],
    )
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No deployments uploaded yet.")
