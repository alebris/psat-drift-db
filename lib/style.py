"""Shared custom CSS. Streamlit's theme config can only set font size for the
whole app, not the sidebar page-navigation labels specifically — this
targets them directly instead.

Note: this relies on a data-testid Streamlit adds internally
(stSidebarNavItems), not an official public API, so it could in principle
stop matching after a future Streamlit upgrade. If the nav text stops
resizing after upgrading Streamlit, right-click a page name in the sidebar
in your browser -> Inspect, and look for the current data-testid a few
levels up from the link text to find the new selector.
"""
import streamlit as st

CUSTOM_CSS = """
<style>
[data-testid="stSidebarNavItems"] {
    font-size: 1.15rem;
}
</style>
"""


def apply_custom_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
