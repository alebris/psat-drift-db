"""Shared custom CSS for a consistent, professional look across all pages.

Streamlit's theme config (.streamlit/config.toml) sets the base palette and
font. This module layers on the details the theme config can't reach —
larger sidebar navigation labels, card-style metrics, tighter headers —
by targeting Streamlit's internal DOM structure directly.

Note: the selectors below rely on data-testid attributes Streamlit adds
internally (not a public API), so they could stop matching after a future
Streamlit upgrade. If styling looks off after upgrading, right-click the
affected element in the browser -> Inspect, and look for its current
data-testid to update the selector.
"""
import streamlit as st

CUSTOM_CSS = """
<style>
/* ---- Sidebar navigation: bigger, roomier labels ---- */
[data-testid="stSidebarNavItems"] {
    font-size: 1.15rem;
    padding-top: 0.5rem;
}
[data-testid="stSidebarNavItems"] a {
    padding: 0.6rem 1rem;
    border-radius: 8px;
    font-weight: 500;
    gap: 0.6rem;
}
[data-testid="stSidebarNavItems"] a:hover {
    background-color: rgba(15, 111, 140, 0.08);
}
[data-testid="stSidebarNavItems"] [data-testid="stIconMaterial"] {
    font-size: 1.25rem;
}

section[data-testid="stSidebar"] {
    border-right: 1px solid #e6ebee;
}

/* ---- Titles ---- */
h1 {
    font-weight: 650;
    letter-spacing: -0.01em;
}

/* ---- Metric cards ---- */
[data-testid="stMetric"] {
    background: #f4f8f9;
    border: 1px solid #e6ebee;
    border-radius: 10px;
    padding: 1rem 1.1rem;
}

/* ---- Buttons ---- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    border-radius: 8px;
}

/* ---- Tighten default top padding ---- */
.block-container {
    padding-top: 2.2rem;
}
</style>
"""


def apply_style():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
