import streamlit as st

from lib.auth import current_user, login_widget, logout_button
from lib.style import apply_style

st.set_page_config(page_title="PSAT Drift Database", page_icon="\U0001F30A", layout="wide")
apply_style()

st.title("\U0001F30A PSAT Drift Database")
st.caption("A shared database of pop-up satellite tag (PSAT) drift positions for surface current research.")

user = current_user()

if user is None:
    st.markdown(
        "Marine scientists upload post-release drift tracks from PSAT tags; "
        "oceanographers query and download the pooled data by position, time, and quality. "
        "**Browse the map and statistics freely below** — signing in is only needed to upload or download data."
    )
else:
    logout_button()
    st.success(f"Signed in as {user.email}")

st.divider()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.subheader("\U0001F5FA️ Browse Map")
    st.caption("Explore drift tracks on an interactive ocean map, filtered by data quality.")
with col2:
    st.subheader("\U0001F4CA Statistics")
    st.caption("Summary charts of deployments, positions, and data quality across the database.")
with col3:
    st.subheader("⬆️ Upload")
    st.caption("Contribute post-release drift tracks from your own tag deployments.")
with col4:
    st.subheader("⬇️ Download")
    st.caption("Query the pooled data by area, time period, or specific tags, and export it.")

st.divider()

if user is None:
    login_widget()
