"""CivicPulse: Urban Infrastructure Intelligence System (Streamlit UI)."""
from __future__ import annotations
import html
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from civicpulse import analytics as an, schema as sc, theme
from civicpulse.store import StoreError, get_store

st.set_page_config(page_title="CivicPulse", page_icon="📡", layout="wide")
theme.inject()

CAT = sc.CATEGORIES
COLORS = {c["label"]: c["color"] for c in CAT.values()}
SCALE = ["#22D3EE", "#FACC15", "#FB923C", "#F43F5E"]
BAND_CLS = {"Top": "red", "High": "orange", "Elevated": "yellow", "Routine": "cyan", "Closed": "grey"}
STATUS_CLS = {"Open": "red", "In progress": "yellow", "Resolved": "green"}


@st.cache_resource(show_spinner="Connecting to storage…")
def _store(): return get_store()


def pill(text, cls): return f'<span class="pill {cls}">{html.escape(str(text))}</span>'


def style(fig, h=340):
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=h,
                      margin=dict(l=8, r=8, t=36, b=8), font=dict(family="Space Grotesk"), legend=dict(orientation="h", y=-0.2))
    return fig


def make_map(d, hot=None, h=470, extra=None):
    ctr = {"lat": d.lat.mean(), "lon": d.lng.mean()}
    fig = px.scatter_map(d, lat="lat", lon="lng", color="priority", size="severity", size_max=13, range_color=(0, 100),
                         color_continuous_scale=SCALE, center=ctr, zoom=11.6, map_style="carto-darkmatter", hover_name="report_id",
                         hover_data={"category_label": True, "area": True, "severity": True, "priority": True, "status": True,
                                     "lat": False, "lng": False})
    if hot is not None and not hot.empty:
        fig.add_trace(go.Scattermap(lat=hot.lat, lon=hot.lng, mode="markers", name="Hotspot",
                                    marker=dict(size=(26 + 5 * hot.reports).clip(upper=70), color="rgba(244,63,94,0.22)"),
                                    text=hot.hotspot + " · " + hot.reports.astype(str) + " active", hoverinfo="text"))
    if extra is not None:
        fig.add_trace(extra)
    fig.update_layout(coloraxis_colorbar=dict(title="Priority", len=.5, thickness=10))
    return style(fig, h)


def dispatch_list(d, n=8):
    for i, r in enumerate(d[d.status != "Resolved"].sort_values("priority", ascending=False).head(n).itertuples(), 1):
        st.markdown(
            f'<div class="dispatch"><div class="rank">{i:02d}</div><div class="body"><b>{CAT[r.category]["icon"]} {CAT[r.category]["label"]}</b>'
            f' · {html.escape(r.area)}<br><small>{r.report_id} · {r.age_days:.0f}d open · {r.supporting_reports} supporting · '
            f'{pill(r.band, BAND_CLS[r.band])} {pill(r.status, STATUS_CLS[r.status])}</small></div><div class="score">{r.priority:.0f}</div></div>',
            unsafe_allow_html=True)


# ---------------------------------------------------------------- pages
def page_overview(df, hot):
    act = df[df.status != "Resolved"]
    m = st.columns(5)
    m[0].metric("Total reports", len(df))
    m[1].metric("Active issues", len(act))
    m[2].metric("High severity (4–5)", int((act.severity >= 4).sum()))
    m[3].metric("Hotspots", len(hot))
    m[4].metric("Resolved", int((df.status == "Resolved").sum()))
    st.write("")
    left, right = st.columns([2, 1])
    with left:
        st.subheader("Live issue map")
        st.caption("Dot colour = priority score, size = severity, red halos = hotspots.")
        if act.empty: st.info("No active issues.")
        else: st.plotly_chart(make_map(act, hot), use_container_width=True)
    with right:
        st.subheader("Dispatch list")
        st.caption("Ranked by the adjustable priority score, a triage aid for human review.")
        dispatch_list(df)
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Reporting trend")
        flow = an.weekly_flow(df).melt("week", var_name="Flow", value_name="Reports")
        st.plotly_chart(style(px.area(flow, x="week", y="Reports", color="Flow", color_discrete_map={"Opened": "#22D3EE", "Resolved": "#4ADE80"})), use_container_width=True)
    with c2:
        st.subheader("Issue mix (active)")
        if not act.empty:
            st.plotly_chart(style(px.pie(act, names="category_label", hole=.6, color="category_label", color_discrete_map=COLORS)), use_container_width=True)


def field_widget(cat, f):
    key, k = f"d_{cat}_{f['key']}", f["kind"]
    if k == "select": return st.selectbox(f["label"], f["options"], key=key)
    if k == "number": return st.number_input(f["label"], 0, f["max"], f["default"], key=key)
    if k == "bool": return st.checkbox(f["label"], key=key)
    return st.text_input(f["label"], key=key)


def page_report(store):
    st.subheader("Report an issue")
    c1, c2 = st.columns(2)
    cat = c1.selectbox("Issue type", list(CAT), format_func=lambda k: f"{CAT[k]['icon']} {CAT[k]['label']}")
    area = c2.selectbox("Area", list(sc.AREAS))
    lng0, lat0 = sc.AREAS[area]
    with st.form("report_form"):
        a, b = st.columns(2)
        sev = a.select_slider("Severity", [1, 2, 3, 4, 5], 3, format_func=lambda s: f"{s} · {sc.SEVERITY_LABELS[s]}")
        expo = b.number_input("Estimated public exposure (people/day)", 0, 100000, 200, step=50)
        desc = st.text_area("Description", placeholder="What is the problem, and what makes it risky or disruptive?")
        la, lo = st.columns(2)
        lat = la.number_input("Latitude", -90.0, 90.0, float(lat0), step=0.0005, format="%.6f", key=f"lat_{area}")
        lng = lo.number_input("Longitude", -180.0, 180.0, float(lng0), step=0.0005, format="%.6f", key=f"lng_{area}")
        st.markdown(f"**{CAT[cat]['icon']} {CAT[cat]['label']} details**")
        cols, details = st.columns(2), {}
        for i, f in enumerate(CAT[cat]["fields"]):
            with cols[i % 2]: details[f["key"]] = field_widget(cat, f)
        with st.expander("Optional reporter details"):
            rn, rc = st.text_input("Name (optional)"), st.text_input("Contact (optional)")
            st.caption("Optional. Don't enter other people's personal information.")
        submitted = st.form_submit_button("Submit report", type="primary")
    if submitted:
        try:
            doc = sc.build_report(cat, area, sev, desc, lat, lng, expo, details, rn, rc)
            store.insert(doc)
            st.success(f"Report **{doc['report_id']}** submitted. It is now in the municipal work queue.")
        except ValueError as e:
            st.error(str(e))
        except StoreError as e:
            st.error(f"Could not save the report: {e}")
    st.caption("Map preview of the entered coordinates")
    st.map(pd.DataFrame({"lat": [lat], "lon": [lng]}), height=180, zoom=14)


def page_queue(df, w, store):
    st.subheader("Municipal work queue")
    f1, f2, f3 = st.columns(3)
    q = f1.text_input("Search", placeholder="ID, area, description…")
    cats = f2.multiselect("Category", sorted(df.category_label.unique()))
    stat = f3.multiselect("Status", sc.STATUSES, default=["Open", "In progress"])
    g1, g2 = st.columns(2)
    areas = g1.multiselect("Area", sorted(df.area.unique()))
    min_sev = g2.slider("Minimum severity", 1, 5, 1)
    v = df[df.severity >= min_sev]
    if q: v = v[v[["report_id", "area", "description", "category_label"]].apply(lambda c: c.str.contains(q, case=False, regex=False)).any(axis=1)]
    if cats: v = v[v.category_label.isin(cats)]
    if stat: v = v[v.status.isin(stat)]
    if areas: v = v[v.area.isin(areas)]
    v = v.sort_values("priority", ascending=False).reset_index(drop=True)
    st.caption(f"{len(v)} reports · ranked by priority score")
    view = v[["report_id", "priority", "band", "category_label", "area", "severity", "status", "age_days", "supporting_reports"]].round(1)
    ev = st.dataframe(view, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row", height=320)
    if not ev.selection.rows:
        return st.info("Select a row to see details and update its status.")
    r = next(v.iloc[[ev.selection.rows[0]]].itertuples())
    doc = next(d for d in store.list_reports() if d["report_id"] == r.report_id)
    st.markdown(f"### {CAT[r.category]['icon']} {r.report_id} · {CAT[r.category]['label']} {pill(r.status, STATUS_CLS[r.status])}", unsafe_allow_html=True)
    d1, d2 = st.columns([3, 2])
    with d1:
        st.write(doc["description"])
        st.caption(f"{r.area} · {r.lat:.5f}, {r.lng:.5f} · exposure {r.exposure:,}/day · created {r.created_at:%d %b %Y %H:%M} UTC"
                   + (f" · resolved in {r.resolution_hours:.0f} h" if r.status == "Resolved" else "") + (" · SAMPLE DATA" if r.source == "sample" else ""))
        st.json(doc.get("details", {}), expanded=False)
        st.markdown("**Why this priority?**")
        st.dataframe(an.explain(r, w), hide_index=True, use_container_width=True)
    with d2:
        with st.form("status_form"):
            new = st.selectbox("Status", sc.STATUSES, index=sc.STATUSES.index(r.status))
            note = st.text_input("Note (optional)")
            if st.form_submit_button("Update status", type="primary"):
                try:
                    store.update_status(r.report_id, new, note); st.rerun()
                except StoreError as e: st.error(str(e))
        if st.button("➕ Another citizen reported this"):
            try: store.add_support(r.report_id); st.rerun()
            except StoreError as e: st.error(str(e))
        for h in reversed(doc.get("status_history", [])[-5:]):
            st.caption(f"{h['at'][:16].replace('T', ' ')} · {h['status']} · {h.get('note') or ''}")


def page_analytics(df, hot, store):
    st.subheader("Infrastructure analytics")
    t1, t2, t3, t4 = st.tabs(["🔥 Hotspots", "🏙️ Areas", "📈 Trends", "📍 Nearby search"])
    with t1:
        st.caption("Hotspot = grid cell (size set in sidebar) with at least N active reports. Ranked by summed priority.")
        if hot.empty: st.info("No hotspots with the current settings.")
        else:
            st.plotly_chart(make_map(df[df.status != "Resolved"], hot, 420), use_container_width=True)
            st.dataframe(hot, hide_index=True, use_container_width=True)
    with t2:
        a = an.area_summary(df)
        st.plotly_chart(style(px.bar(a, x="area", y=["active", "resolved"], barmode="stack", color_discrete_sequence=["#F43F5E", "#4ADE80"])), use_container_width=True)
        st.dataframe(a, hide_index=True, use_container_width=True)
    with t3:
        wk = an.weekly_by_category(df)
        st.plotly_chart(style(px.line(wk, x="week", y="reports", color="category_label", color_discrete_map=COLORS, markers=True), 360), use_container_width=True)
        c = an.category_summary(df)
        x, y = st.columns(2)
        x.plotly_chart(style(px.bar(c, x="median_resolution_h", y="category_label", orientation="h", title="Median resolution time (hours)", color_discrete_sequence=["#22D3EE"])), use_container_width=True)
        y.dataframe(c, hide_index=True, use_container_width=True)
    with t4:
        st.caption("Uses MongoDB `$geoNear` on the 2dsphere index (haversine in demo mode).")
        n1, n2, n3 = st.columns(3)
        area = n1.selectbox("Start from area centre", list(sc.AREAS), key="nb_area")
        lng0, lat0 = sc.AREAS[area]
        lat = n2.number_input("Latitude", value=float(lat0), format="%.6f", step=0.001, key=f"nb_lat_{area}")
        lng = n3.number_input("Longitude", value=float(lng0), format="%.6f", step=0.001, key=f"nb_lng_{area}")
        r1, r2 = st.columns([3, 1])
        radius = r1.slider("Radius (m)", 100, 3000, 500, 50)
        inc = r2.checkbox("Include resolved", False)
        try: res = store.nearby(lng, lat, radius, inc)
        except StoreError as e: return st.error(str(e))
        st.metric("Reports within radius", len(res))
        dist = {x["report_id"]: x["distance_m"] for x in res}
        m = df[df.report_id.isin(dist)].copy()
        if not m.empty:
            m["distance_m"] = m.report_id.map(dist).round(0)
            ctr = go.Scattermap(lat=[lat], lon=[lng], mode="markers", name="Search centre", marker=dict(size=16, color="#FFFFFF"))
            st.plotly_chart(make_map(m, None, 380, ctr), use_container_width=True)
            st.dataframe(m[["report_id", "distance_m", "category_label", "severity", "status", "priority"]].sort_values("distance_m"), hide_index=True, use_container_width=True)


# ---------------------------------------------------------------- main
try:
    store, notice = _store()
    with st.sidebar:
        st.markdown("## 📡 CivicPulse")
        page = st.radio("Workspace", ["City overview", "Report an issue", "Municipal work queue", "Infrastructure analytics"], label_visibility="collapsed")
        st.caption(f"Storage: **{store.name}**")
        with st.expander("⚖️ Priority weights"):
            w = an.Weights(st.slider("Severity", 0, 100, 40), st.slider("Supporting reports", 0, 100, 20),
                           st.slider("Public exposure", 0, 100, 20), st.slider("Unresolved age", 0, 100, 20),
                           st.slider("Supporting reports cap", 1, 50, 10), st.slider("Exposure cap (people/day)", 500, 50000, 5000, 500),
                           st.slider("Age cap (days)", 3, 90, 30))
            st.caption("Weights are relative and normalised. The score is a transparent triage aid, not an automated safety decision.")
        with st.expander("🔥 Hotspot settings"):
            cell = st.slider("Cell size (m)", 300, 1500, 600, 100)
            min_n = st.slider("Min active reports", 2, 10, 3)
        with st.expander("🧪 Sample data"):
            st.caption("Synthetic records tagged `source: sample`.")
            if st.button("Reload sample data"):
                store.seed_sample(); st.rerun()
            if st.button("Remove sample data"):
                store.clear_sample(); st.rerun()
    mode = "DEMO MODE · sample data" if store.is_demo else "Connected to MongoDB Atlas"
    st.markdown(f'<div class="hero"><div><h1>Civic<span>Pulse</span></h1><p>Urban Infrastructure Intelligence System</p></div>'
                f'{pill(mode, "yellow" if store.is_demo else "green")}</div>', unsafe_allow_html=True)
    if notice: st.markdown(f'<div class="notice">⚠️ {html.escape(notice)}</div>', unsafe_allow_html=True)
    if page == "Report an issue":
        page_report(store)
    else:
        df = an.build_frame(store.list_reports(), w)
        if df.empty:
            st.info("No reports yet. Add one, or load sample data from the sidebar.")
        else:
            hot = an.hotspots(df, cell, min_n)
            {"City overview": lambda: page_overview(df, hot), "Municipal work queue": lambda: page_queue(df, w, store),
             "Infrastructure analytics": lambda: page_analytics(df, hot, store)}[page]()
except StoreError as e:
    st.error(f"Storage problem: {e}")
except Exception as e:  # last-resort guard so users see a message, not a stack trace
    st.error(f"Unexpected error: {type(e).__name__}: {e}")
