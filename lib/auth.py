from __future__ import annotations

import streamlit as st

from lib.cookies import get_cookie_manager
from lib.db import get_client

COOKIE_KEY = "refresh_token"


def current_user():
    return st.session_state.get("user")


def _sync_profile(client, user, institution: str | None):
    if not institution:
        return
    try:
        client.table("profiles").update({"institution": institution}).eq("id", user.id).execute()
    except Exception:
        pass  # profile row is created by a DB trigger; safe to ignore races


def _save_session_cookie(session):
    cookies = get_cookie_manager()
    cookies[COOKIE_KEY] = session.refresh_token
    cookies.save()


def _clear_session_cookie():
    cookies = get_cookie_manager()
    if COOKIE_KEY in cookies:
        del cookies[COOKIE_KEY]
        cookies.save()


def try_restore_session():
    """Silently log the user back in from a stored refresh token, if any.

    Safe to call on every page, every rerun: it's a no-op once already
    logged in, and does nothing if there's no valid cookie. Call this near
    the top of every page, before require_login() or any user-dependent UI.
    """
    if current_user() is not None:
        return

    cookies = get_cookie_manager()
    if not cookies.ready():
        st.stop()  # component hasn't synced from the browser yet; Streamlit reruns automatically

    refresh_token = cookies.get(COOKIE_KEY)
    if not refresh_token:
        return

    client = get_client()
    try:
        res = client.auth.refresh_session(refresh_token)
        if res and res.session:
            st.session_state["user"] = res.user
            st.session_state["session"] = res.session
            _save_session_cookie(res.session)  # Supabase rotates refresh tokens; save the new one
    except Exception:
        _clear_session_cookie()  # stale/expired token — drop it rather than retry forever


def login_widget():
    client = get_client()
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            try:
                res = client.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state["user"] = res.user
                st.session_state["session"] = res.session
                _save_session_cookie(res.session)
                pending = st.session_state.pop("pending_institution", None)
                _sync_profile(client, res.user, pending)
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")

    with tab_signup:
        with st.form("signup_form"):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            display_name = st.text_input("Display name", key="signup_display_name")
            institution = st.text_input("Institution", key="signup_institution")
            submitted = st.form_submit_button("Sign up")
        if submitted:
            try:
                client.auth.sign_up(
                    {
                        "email": email,
                        "password": password,
                        "options": {"data": {"display_name": display_name}},
                    }
                )
                st.session_state["pending_institution"] = institution
                st.success("Account created. If email confirmation is enabled on this project, check your inbox, then log in.")
            except Exception as e:
                st.error(f"Sign up failed: {e}")


def require_login():
    try_restore_session()
    if current_user() is None:
        st.info("Please log in to continue.")
        login_widget()
        st.stop()


def logout_button():
    if st.sidebar.button("Log out"):
        client = get_client()
        client.auth.sign_out()
        for k in ("user", "session"):
            st.session_state.pop(k, None)
        _clear_session_cookie()
        st.rerun()
