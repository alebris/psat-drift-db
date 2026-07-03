"""Supabase client access.

Deliberately NOT cached with st.cache_resource: Streamlit can serve multiple
concurrent users from the same process, and a cached client would share one
user's authenticated session with every other session. Each browser session
gets its own client stored in st.session_state instead.
"""
import streamlit as st
from supabase import create_client, Client


def get_client() -> Client:
    if "supabase_client" not in st.session_state:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
        st.session_state["supabase_client"] = create_client(url, key)
    return st.session_state["supabase_client"]
