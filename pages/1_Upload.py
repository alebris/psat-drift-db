import streamlit as st

from lib.auth import require_login, current_user
from lib.db import get_client
from lib.parsers.wildlife_computers import parse_wc_locations

st.set_page_config(page_title="Upload", page_icon="\u2b06\ufe0f", layout="wide")
require_login()
user = current_user()
client = get_client()

st.title("Upload drift data")

manufacturer = st.selectbox(
    "Tag manufacturer / file format",
    [
        "Wildlife Computers (Locations.csv)",
        "Lotek (coming soon)",
        "Desert Star (coming soon)",
        "Microwave Telemetry (coming soon)",
    ],
)

if manufacturer != "Wildlife Computers (Locations.csv)":
    st.info("This format isn't wired up yet — only Wildlife Computers merged Locations.csv exports can be uploaded right now.")
    st.stop()

uploaded = st.file_uploader("Wildlife Computers Locations.csv", type="csv")

with st.form("deployment_metadata"):
    st.subheader("Deployment metadata")
    col1, col2 = st.columns(2)
    species = col1.text_input("Species (optional)")
    notes = col2.text_input("Notes (optional)")
    submitted = st.form_submit_button("Parse file")

if submitted:
    if uploaded is None:
        st.error("Please choose a file first.")
        st.stop()
    try:
        positions = parse_wc_locations(uploaded)
    except Exception as e:
        st.error(f"Could not parse file: {e}")
        st.stop()

    if positions.empty:
        st.error("No valid position rows found in this file.")
        st.stop()

    st.session_state["pending_upload"] = {
        "positions": positions,
        "species": species,
        "notes": notes,
        "filename": uploaded.name,
    }

pending = st.session_state.get("pending_upload")
if pending is not None:
    positions = pending["positions"]
    deploy_ids = sorted(positions["deploy_id"].unique())
    st.write(f"Parsed **{len(positions)}** positions across **{len(deploy_ids)}** deployment ID(s): {', '.join(deploy_ids)}")

    dupes_removed = positions.attrs.get("dupes_removed", 0)
    if dupes_removed:
        st.caption(f"{dupes_removed} exact duplicate row(s) removed automatically.")

    st.dataframe(positions.head(20), use_container_width=True)

    if st.button("Confirm and publish to database", type="primary"):
        try:
            for deploy_id, group in positions.groupby("deploy_id"):
                first = group.iloc[0]
                deployment = (
                    client.table("deployments")
                    .insert(
                        {
                            "deploy_id": str(deploy_id),
                            "ptt": str(first["ptt"]),
                            "instrument_model": str(first["instrument_model"]),
                            "manufacturer": "wildlife_computers",
                            "species": pending["species"] or None,
                            "source_filename": pending["filename"],
                            "source_format": "wc_locations_v1",
                            "uploader_id": user.id,
                            "notes": pending["notes"] or None,
                        }
                    )
                    .execute()
                )
                deployment_id = deployment.data[0]["id"]

                rows = [
                    {
                        "deployment_id": deployment_id,
                        "ts": row["ts"].isoformat(),
                        "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"]),
                        "location_type": row["location_type"],
                        "quality_raw": row["quality_raw"],
                        "quality_class": row["quality_class"],
                        "raw_metadata": row["raw_metadata"],
                    }
                    for _, row in group.iterrows()
                ]
                for i in range(0, len(rows), 500):
                    client.table("positions").insert(rows[i : i + 500]).execute()

            st.success("Upload published. Thank you!")
            del st.session_state["pending_upload"]
        except Exception as e:
            st.error(f"Upload failed: {e}")
