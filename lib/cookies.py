"""Browser-cookie storage, used to keep users logged in across page reloads.

Streamlit's own session state does not survive a hard page refresh — a new
browser load gets a fresh session, which is why login was being lost every
time. This stores the Supabase *refresh token* (not the short-lived access
token) in an encrypted cookie, so it can be used to silently restore a
session on load. See lib/auth.py for how it's used.
"""
import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager


def get_cookie_manager() -> EncryptedCookieManager:
    if "cookie_manager" not in st.session_state:
        password = st.secrets.get("COOKIE_PASSWORD", "psat-drift-db-dev-only-change-me")
        st.session_state["cookie_manager"] = EncryptedCookieManager(
            prefix="psat_drift/", password=password
        )
    return st.session_state["cookie_manager"]
