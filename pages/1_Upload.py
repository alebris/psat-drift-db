import pandas as pd
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

uploaded_files = st.file_uploader(
    "Wildlife Computers Locations.csv", type="csv", accept_multiple_files=True
)

with st.form("deployment_metadata"):
    st.subheader("Deployment metadata")
    col1, col2 = st.columns(2)
    species = col1.text_input("Species (optional)")
    notes = col2.text_input("Notes (optional)")
    submitted = st.form_submit_button("Parse file")

if submitted:
    if not uploaded_files:
        st.error("Please choose at least one file first.")
        st.stop()

    parsed = []
    dupes_removed = 0
    for f in uploaded_files:
        try:
            file_positions = parse_wc_locations(f)
        except Exception as e:
            st.error(f"Could not parse {f.name}: {e}")
            st.stop()
        dupes_removed += file_positions.attrs.get("dupes_removed", 0)
        if not file_positions.empty:
            file_positions["source_filename"] = f.name
            parsed.append(file_positions)

    if not parsed:
        st.error("No valid position rows found in these files.")
        st.stop()

    positions = pd.concat(parsed, ignore_index=True)
    before = len(positions)
    positions = positions.drop_duplicates(subset=["deploy_id", "ts", "latitude", "longitude"])
    dupes_removed += before - len(positions)
    positions = positions.sort_values("ts").reset_index(drop=True)
    positions.attrs["dupes_removed"] = dupes_removed

    st.session_state["pending_upload"] = {
        "positions": positions,
        "species": species,
        "notes": notes,
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
                source_filenames = ", ".join(sorted(group["source_filename"].unique()))
                deployment = (
                    client.table("deployments")
                    .insert(
                        {
                            "deploy_id": str(deploy_id),
                            "ptt": str(first["ptt"]),
                            "instrument_model": str(first["instrument_model"]),
                            "manufacturer": "wildlife_computers",
                            "species": pending["species"] or None,
                            "source_filename": source_filenames,
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
