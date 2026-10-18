# 📡 CivicPulse — Urban Infrastructure Intelligence System

Citizens and municipal workers report infrastructure problems; city teams see where issues cluster, how severe they are, how long they stay unresolved, and what to look at first.

**Stack:** Python · Streamlit · MongoDB Atlas (PyMongo) · pandas · Plotly. Runs **without any credentials** using a local JSON demo store seeded with clearly labelled synthetic data.

## What's implemented (MVP)
- **City overview** — metrics (reports, active, high severity, hotspots, resolved), dark map, weekly opened/resolved trend, issue mix, ranked dispatch list.
- **Report an issue** — type, area, severity, description, coordinates, public exposure, optional reporter details, plus category-specific fields (9 categories).
- **Municipal work queue** — search, category/status/area/severity filters, priority ranking, details, score breakdown, status updates (Open / In progress / Resolved), status history, "another citizen reported this" counter.
- **Infrastructure analytics** — hotspots, area summaries, weekly trends by category, median resolution time, nearby search by radius (`$geoNear`).
- MongoDB backend with GeoJSON points and indexes; demo backend with identical interface; automatic fallback to demo with a visible notice if MongoDB is unreachable.
- Resolution time recorded automatically when a report is marked Resolved (cleared if re-opened).

**Optional extensions (not built):** authentication/roles, public reporting portal, photo upload + computer vision, automatic duplicate merging, geocoding/address search, exports, notifications, unit tests, per-city ward polygons.

**Assumptions:** area names/coordinates are fictional wards (edit `AREAS` in `civicpulse/schema.py`); times are UTC; "exposure" is a reporter's rough estimate of people passing per day; the app has no login, so on a public deployment anyone can update statuses. Treat it as an MVP/internal tool until authentication is added.

## 1. Run locally
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Open http://localhost:8501. Demo data is written to `data/demo_reports.json` (git-ignored). Delete it to regenerate. The sidebar *Sample data* panel reloads or removes sample records.

## 2. Create a MongoDB Atlas database
1. Sign up at https://www.mongodb.com/atlas and create a free **M0** cluster.
2. **Database Access → Add New Database User** (password auth). Use a strong generated password and give it *Read and write to any database* (or limit to the `civicpulse` DB).
3. **Network Access → Add IP Address.** For local work add your current IP. For Streamlit Community Cloud (no fixed IPs) you must allow `0.0.0.0/0`; rely on a strong password and least-privilege user.
4. **Database → Connect → Drivers** and copy the connection string (`mongodb+srv://…`). Replace `<password>` (URL-encode special characters).
5. No manual collection setup: the app creates `civicpulse.reports` and its indexes on first connect.

## 3. Switch from demo storage to MongoDB
```bash
cp .env.example .env
```
Edit `.env`:
```
STORAGE_BACKEND=mongodb
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
```
Restart the app; the header badge shows *Connected to MongoDB Atlas*. The collection starts empty: open the sidebar **Sample data → Reload sample data** to insert labelled synthetic records (`source: "sample"`), and **Remove sample data** deletes only those. If the connection fails you'll see a warning and the app falls back to demo storage. (`.streamlit/secrets.toml` works too and takes precedence over `.env`.)

## 4. Report schema
```json
{
  "report_id": "CP-3FA9C1",
  "category": "pothole",
  "area": "Old Market",
  "severity": 4,
  "description": "…",
  "location": { "type": "Point", "coordinates": [75.8243, 26.9239] },
  "exposure": 1200,
  "supporting_reports": 3,
  "status": "Open",
  "created_at": "ISODate", "updated_at": "ISODate",
  "resolved_at": null, "resolution_hours": null,
  "details": { "width_cm": 40, "depth_cm": 8, "lane": "Middle of lane" },
  "reporter": { "name": null, "contact": null },
  "source": "user | sample",
  "status_history": [{ "status": "Open", "at": "…", "note": "Report received" }]
}
```
Common fields are shared; `details` varies by category (defined in `civicpulse/schema.py`, so adding a category means adding one dict). Coordinates are GeoJSON order **[longitude, latitude]**. `reporter` is optional.

**Indexes:** `2dsphere` on `location`; `category`; `status`; `created_at` (desc); `severity`; compound `status + severity`; unique `report_id`.

## 5. Priority score (explainable, adjustable)
Each factor is scaled to 0–1, then combined with weights that city teams set in the sidebar:

| Factor | Scaling | Default weight |
|---|---|---|
| Severity | severity ÷ 5 | 40 |
| Supporting reports | count ÷ cap (default 10), max 1 | 20 |
| Public exposure | log(1+people/day) ÷ log(1+cap), cap default 5,000 | 20 |
| Unresolved age | days open ÷ cap (default 30), max 1 | 20 |

`priority = 100 × Σ(weight × factor) ÷ Σ(weight)`; resolved reports score 0. Bands (Routine <30, Elevated 30–50, High 50–70, Top ≥70) are only labels for sorting attention. **The score is a triage aid for human review, not an automated safety decision.** Open manholes, exposed wiring or burst mains may need immediate action regardless of score. The queue's "Why this priority?" table shows every factor's contribution.

**Hotspots:** active reports are binned into square grid cells (default 600 m); cells with ≥ 3 active reports are hotspots, ranked by summed priority.

## 6. Prepare for GitHub (manual)
```bash
git init
git status            # confirm .env, secrets.toml, data/demo_reports.json are NOT listed
git add .
git commit -m "Initial CivicPulse MVP"
```
Create an empty repository on GitHub, then follow its instructions to add the remote and push. Never commit `.env` or `secrets.toml`. If a secret was ever committed, rotate it in Atlas.

## 7. Deploy to Streamlit Community Cloud (manual)
1. Push the repo to GitHub. 2. At https://share.streamlit.io choose **Create app**, select the repo, branch, and `app.py`. 3. Open **Advanced settings → Secrets** and paste (use your real values there only):
```toml
STORAGE_BACKEND = "mongodb"
MONGODB_URI = "mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority"
MONGODB_DB = "civicpulse"
MONGODB_COLLECTION = "reports"
```
4. Deploy. 5. Ensure Atlas Network Access permits Streamlit's outbound traffic (see step 2.3). Without secrets the cloud app runs in demo mode, whose file storage is ephemeral.

## Project layout
```
app.py                 Streamlit UI (4 workspaces)
civicpulse/schema.py   categories, category fields, validation, document builder
civicpulse/store.py    DemoStore (JSON) + MongoStore (PyMongo, indexes, $geoNear), fallback logic
civicpulse/analytics.py priority score, hotspots, area/category/time summaries
civicpulse/sample_data.py synthetic data generator
civicpulse/theme.py    dark theme CSS
.streamlit/config.toml theme · .env.example · requirements.txt
```
All sample data is synthetic; no real credentials or personal information are included.
