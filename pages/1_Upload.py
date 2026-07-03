import pandas as pd
import streamlit as st

from lib.auth import require_login, current_user
from lib.db import get_client
from lib.cleaning import remove_land_points, remove_unrealistic_speed
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
    "Wildlife Computers Locations.csv file(s)",
    type="csv",
    accept_multiple_files=True,
    help="You can select several files at once — each is parsed and cleaned separately.",
)

max_speed_kmh = st.slider(
    "Maximum realistic drift speed between consecutive fixes (km/h)",
    min_value=1.0,
    max_value=100.0,
    value=20.0,
    step=1.0,
    help="Fixes implying faster drift than this from the previous accepted fix in the same "
    "deployment are treated as location errors and removed.",
)

with st.form("deployment_metadata"):
    st.subheader("Deployment metadata (applied to all files in this batch)")
    col1, col2 = st.columns(2)
    species = col1.text_input("Species (optional)")
    notes = col2.text_input("Notes (optional)")
    submitted = st.form_submit_button("Parse & clean files")

if submitted:
    if not uploaded_files:
        st.error("Please choose at least one file first.")
        st.stop()

    parsed = []
    for f in uploaded_files:
        try:
            positions = parse_wc_locations(f)
        except Exception as e:
            st.error(f"**{f.name}** — could not parse: {e}")
            continue

        if positions.empty:
            st.warning(f"**{f.name}** — no valid position rows found; skipped.")
            continue

        dupes = positions.attrs.get("dupes_removed", 0)

        land_cleaned = remove_land_points(positions)
        land = land_cleaned.attrs.get("land_removed", 0)

        speed_cleaned = remove_unrealistic_speed(land_cleaned, max_speed_kmh)
        speed = speed_cleaned.attrs.get("speed_removed", 0)

        parsed.append(
            {
                "filename": f.name,
                "positions": speed_cleaned,
                "dupes": dupes,
                "land": land,
                "speed": speed,
            }
        )

    if not parsed:
        st.error("No files could be processed.")
        st.stop()

    st.session_state["pending_batch"] = {
        "files": parsed,
        "species": species,
        "notes": notes,
        "max_speed_kmh": max_speed_kmh,
    }

batch = st.session_state.get("pending_batch")
if batch is not None:
    st.subheader("Review before publishing")
    st.caption(f"Speed filter applied at {batch['max_speed_kmh']:.0f} km/h.")

    total_positions = 0
    for item in batch["files"]:
        pos = item["positions"]
        total_positions += len(pos)
        deploy_ids = ", ".join(sorted(pos["deploy_id"].unique())) if not pos.empty else "\u2014"
        st.markdown(f"**{item['filename']}** \u2014 deployment(s): {deploy_ids}")
        cleaning_bits = []
        if item["dupes"]:
            cleaning_bits.append(f"{item['dupes']} duplicate row(s) removed")
        if item["land"]:
            cleaning_bits.append(f"{item['land']} on-land position(s) removed")
        if item["speed"]:
            cleaning_bits.append(f"{item['speed']} unrealistic-speed position(s) removed")
        summary = f"{len(pos)} positions kept"
        if cleaning_bits:
            summary += " (" + "; ".join(cleaning_bits) + ")"
        st.caption(summary)
        if not pos.empty:
            st.dataframe(pos.head(5), use_container_width=True)

    st.write(f"**Total positions to publish across batch: {total_positions}**")

    if st.button("Confirm and publish to database", type="primary"):
        try:
            published = 0
            for item in batch["files"]:
                positions = item["positions"]
                if positions.empty:
                    continue
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
                                "species": batch["species"] or None,
                                "source_filename": item["filename"],
                                "source_format": "wc_locations_v1",
                                "uploader_id": user.id,
                                "notes": batch["notes"] or None,
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
                    published += len(rows)

            st.success(f"Published {published} positions across {len(batch['files'])} file(s). Thank you!")
            del st.session_state["pending_batch"]
        except Exception as e:
            st.error(f"Upload failed: {e}")
