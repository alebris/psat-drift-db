import streamlit as st

from lib.auth import current_user, login_widget, logout_button

st.set_page_config(page_title="PSAT Drift Database", page_icon="\U0001F30A", layout="wide")

st.title("\U0001F30A PSAT Drift Database")
st.caption("A shared database of pop-up satellite tag (PSAT) drift positions for surface current research.")

user = current_user()

if user is None:
    st.markdown(
        "Marine scientists upload post-release drift tracks from PSAT tags; "
        "oceanographers query and download the pooled data by position, time, and quality. "
        "**Browse the map and statistics freely below** — signing in is only needed to upload or download data."
    )
    login_widget()
else:
    logout_button()
    st.success(f"Signed in as {user.email}")
    st.markdown(
        "Use the sidebar to **Upload** new drift data, **Browse** the map, "
        "view **Statistics**, or **Download** filtered data."
    )
