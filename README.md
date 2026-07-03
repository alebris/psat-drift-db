# PSAT Drift Database

A shared database of pop-up satellite tag (PSAT) drift positions, for surface
current / ocean drift research. Marine scientists upload post-detachment
drift tracks from their tags; oceanographers query and download the pooled
data by position, time, and location quality.

- **Backend:** Supabase (free tier) — Postgres + auth + REST API
- **Frontend:** Streamlit, deployed on Streamlit Community Cloud (free tier)
- **MVP format support:** Wildlife Computers merged `Locations.csv` exports.
  Lotek, Desert Star, and Microwave Telemetry formats are stubbed in the
  upload UI and can be added later — see "Adding a new manufacturer" below.

## 1. Create the Supabase project

1. Sign up at [supabase.com](https://supabase.com) and create a new project (free tier).
2. Open **SQL Editor**, paste in the contents of `schema.sql`, and run it.
   This creates the `profiles`, `deployments`, `positions`, and `downloads`
   tables with row-level security already configured: `deployments` and
   `positions` are **readable by anyone** (the map and statistics pages don't
   require login), but only insertable by the authenticated uploader, as
   themselves.

   **Already have a project running from an earlier version of this app?**
   Don't rerun `schema.sql` (it'll fail on tables that already exist) — run
   `migrations/001_public_read.sql` instead, which just updates the two read
   policies in place.
3. Under **Authentication → Providers**, email/password is enabled by
   default — that's all this app uses. Under **Authentication → Settings**,
   decide whether to require email confirmation (off is easiest while
   testing; on is more appropriate once this is public-facing).
4. Under **Project Settings → API**, copy the **Project URL** and the
   **anon public key** — you'll need both next. Supabase is migrating key
   naming: newer projects may instead show a **Publishable key**
   (`sb_publishable_...`) under **Settings → API Keys**. Either works here —
   they carry the same restricted, RLS-governed permissions. Always use the
   client-side/public-labeled key; never the **secret key** /
   **service_role key**, which bypasses Row Level Security entirely and
   must never appear in this app.

## 2. Configure secrets

Copy the template and fill in your Supabase values:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

`.streamlit/secrets.toml` is already git-ignored — never commit real keys.

## 3. Run locally

```bash
pip install -r requirements.txt
streamlit run Home.py
```

## 4. Deploy for free

1. Push this repo to a **public** GitHub repository (Streamlit Community
   Cloud's free tier requires a public repo).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, and deploy the repo with `Home.py` as the entry point.
3. In the app's **Settings → Secrets**, paste the same two keys from
   `.streamlit/secrets.toml`.
4. Done — the app redeploys automatically on every push to `main`.

The app will "sleep" after a period of inactivity and wake on the next
visit (a few seconds' cold start). There's no hard monthly usage cap on
this tier, unlike some alternatives, which is why it fits a low-maintenance,
occasional-use tool like this one.

## Project structure

```
Home.py                       Landing page + login/signup
pages/
  1_Browse_Map.py             Ocean-basemap map with drift tracks + area query tool
  2_Statistics.py             Summary metrics and charts
  3_Upload.py                 Upload (multiple files) + parse + clean + publish
  4_Download.py               Query builder, CSV/GeoJSON export, usage logging
lib/
  db.py                       Supabase client (one per browser session)
  auth.py                     Login/signup widgets and login guard
  style.py                    Shared CSS (sidebar nav sizing, card styling)
  quality.py                  Manufacturer quality code -> universal tier + shared color palette
  cleaning.py                 Land removal + unrealistic-speed removal
  parsers/
    wildlife_computers.py     WC Locations.csv parser
schema.sql                    Supabase table + RLS definitions
```

## Data model

- **deployments** — one row per uploaded tag deployment (deploy ID, PTT,
  instrument, manufacturer, species, uploader, source file).
- **positions** — one row per drift fix: timestamp, lat/lon, `location_type`
  (e.g. `Argos`, `GPS`, `GPE`), `quality_raw` (the manufacturer's own code,
  e.g. Argos LC `3`/`B`), a harmonized `quality_class`
  (`high`/`medium`/`low`/`unusable`/`unknown`) for cross-manufacturer
  filtering, and `raw_metadata` (JSON) preserving everything else from the
  source file (error ellipse, GPE error metrics, etc.) for full fidelity.
- **downloads** — a log of who downloaded what, for usage tracking.

On upload, three cleaning steps run automatically, each reported per file
before you confirm publishing: exact duplicate rows are removed; positions
falling **on land** are dropped (drift tags float at the sea surface, so land
fixes are location errors) using a global ~1 km coastline mask
(`global-land-mask`); and positions implying an **unrealistic drift speed**
from the previous accepted fix in the same deployment are dropped (a
sequential filter — see `lib/cleaning.py` for its known limitations). The
speed threshold defaults to 20 km/h and is adjustable per upload via a
slider. Beyond that, data is stored as submitted; downloaders filter further
by `quality_class` or `quality_raw` themselves.

**Read access is public** — the Browse map and Statistics pages work without
signing in. Only Upload and Download require authentication.

## Maps

The Browse page uses an ocean-styled basemap suited to marine drift data.
By default it uses Esri's **Ocean** basemap, which needs no API key. To use
MapTiler's **Ocean** style instead (the look at maptiler.com/maps ocean-v4),
create a free key at [cloud.maptiler.com](https://cloud.maptiler.com) and add
it to your secrets as `MAPTILER_KEY` (see `.streamlit/secrets.toml.example`).
Drift positions are drawn as points colored by quality tier and, optionally,
connected into per-deployment tracks. Click any point to reveal a
**"Show only deployment ..."** button, which filters the map down to that
one deployment; a **"Show all deployments"** button appears whenever a
filter is active to reset.

The **"Query area"** expander lets you type a lat/lon bounding box, which is
drawn on the map as a shaded rectangle; a **"Use this area on Download
page"** button carries those coordinates over to the Download page's area
filter, similar to GEBCO's grid-subsetting tool. On the Download page, area,
time period, and specific-tags filters are independent and combinable — use
any one, any two, or all three together. Checking "Filter by specific
tag(s)" reveals a dropdown of tags at the bottom of the page, just above the
query button.

## Adding a new manufacturer

1. Add a parser module under `lib/parsers/` that returns a DataFrame with
   the same normalized columns as `wildlife_computers.py`
   (`deploy_id, ptt, instrument_model, ts, latitude, longitude,
   location_type, quality_raw, quality_class, raw_metadata`).
2. Extend `lib/quality.py` with that manufacturer's quality-code mapping.
3. Wire the new format into the manufacturer selector in
   `pages/3_Upload.py` and add its enum value to the `manufacturer` check
   constraint in `schema.sql`.

No changes to the database schema or the other pages are needed — the
`raw_metadata` JSON column absorbs whatever manufacturer-specific fields
don't fit the universal columns.
