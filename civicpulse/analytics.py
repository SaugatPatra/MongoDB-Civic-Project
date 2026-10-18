"""Transparent analytics: priority score, hotspots, area/category/time summaries. Pure pandas, no hidden models."""
from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .schema import CATEGORIES


@dataclass
class Weights:
    """Relative weights (any scale; normalised to 100) and saturation caps. Adjustable by city teams."""
    severity: float = 40
    support: float = 20
    exposure: float = 20
    age: float = 20
    support_cap: int = 10          # supporting reports at which the factor saturates
    exposure_cap: int = 5000       # people/day at which the (log-scaled) factor saturates
    age_cap_days: int = 30         # unresolved days at which the factor saturates


COLS = ["report_id", "category", "category_label", "area", "severity", "status", "description", "supporting_reports",
        "exposure", "lat", "lng", "created_at", "resolved_at", "resolution_hours", "age_days", "source",
        "c_sev", "c_sup", "c_exp", "c_age", "priority", "band"]


def score(df, w: Weights):
    """priority = 100 * sum(weight_i * factor_i) / sum(weight_i); each factor is scaled to 0..1. Resolved = 0."""
    df = df.copy()
    df["c_sev"] = df.severity / 5
    df["c_sup"] = (df.supporting_reports / w.support_cap).clip(0, 1)
    df["c_exp"] = (np.log1p(df.exposure) / math.log1p(w.exposure_cap)).clip(0, 1)
    df["c_age"] = (df.age_days / w.age_cap_days).clip(0, 1)
    tot = (w.severity + w.support + w.exposure + w.age) or 1
    df["priority"] = (100 * (w.severity * df.c_sev + w.support * df.c_sup + w.exposure * df.c_exp + w.age * df.c_age) / tot).round(1)
    df.loc[df.status == "Resolved", "priority"] = 0.0
    df["band"] = np.select([df.status == "Resolved", df.priority >= 70, df.priority >= 50, df.priority >= 30],
                           ["Closed", "Top", "High", "Elevated"], "Routine")
    return df


def build_frame(reports, w: Weights):
    if not reports:
        return pd.DataFrame(columns=COLS)
    df = pd.DataFrame([{
        "report_id": r["report_id"], "category": r["category"], "category_label": CATEGORIES[r["category"]]["label"],
        "area": r["area"], "severity": r["severity"], "status": r["status"], "description": r["description"],
        "supporting_reports": r.get("supporting_reports", 0), "exposure": r.get("exposure", 0),
        "lng": r["location"]["coordinates"][0], "lat": r["location"]["coordinates"][1],
        "created_at": r["created_at"], "resolved_at": r.get("resolved_at"), "resolution_hours": r.get("resolution_hours"),
        "source": r.get("source", "user")} for r in reports if r["category"] in CATEGORIES])
    for c in ("created_at", "resolved_at"):
        df[c] = pd.to_datetime(df[c], utc=True)
    now = pd.Timestamp.now(tz="UTC")
    df["age_days"] = np.where(df.status == "Resolved", 0.0, (now - df.created_at).dt.total_seconds() / 86400)
    return score(df, w)


def explain(row, w: Weights):
    """Per-report breakdown of the score, so every number can be audited."""
    tot = (w.severity + w.support + w.exposure + w.age) or 1
    rows = [("Severity", f"{row.severity} / 5", row.c_sev, w.severity), ("Supporting reports", f"{row.supporting_reports} (cap {w.support_cap})", row.c_sup, w.support),
            ("Public exposure", f"{row.exposure:,}/day (log scale, cap {w.exposure_cap:,})", row.c_exp, w.exposure),
            ("Unresolved age", f"{row.age_days:.1f} d (cap {w.age_cap_days})", row.c_age, w.age)]
    return pd.DataFrame([{"Factor": f, "Input": i, "Scaled 0–1": round(c, 2), "Weight %": round(100 * wt / tot, 1),
                          "Points": round(100 * wt * c / tot, 1)} for f, i, c, wt in rows])


def hotspots(df, cell_m=600, min_reports=3):
    """Grid-cell clustering of active reports. A hotspot = a cell with >= min_reports active reports."""
    a = df[df.status != "Resolved"]
    cols = ["hotspot", "area", "reports", "avg_severity", "top_category", "total_priority", "lat", "lng"]
    if a.empty: return pd.DataFrame(columns=cols)
    dlat = cell_m / 111_320
    dlng = cell_m / (111_320 * math.cos(math.radians(a.lat.mean())))
    a = a.assign(cx=(a.lng // dlng).astype(int), cy=(a.lat // dlat).astype(int))
    g = a.groupby(["cx", "cy"]).agg(reports=("report_id", "count"), lat=("lat", "mean"), lng=("lng", "mean"),
                                    avg_severity=("severity", "mean"), total_priority=("priority", "sum"),
                                    top_category=("category_label", lambda s: s.mode().iat[0]),
                                    area=("area", lambda s: s.mode().iat[0])).reset_index()
    g = g[g.reports >= min_reports].sort_values("total_priority", ascending=False).reset_index(drop=True)
    g["hotspot"] = [f"H{i + 1}" for i in g.index]
    g[["avg_severity", "total_priority"]] = g[["avg_severity", "total_priority"]].round(1)
    return g[cols]


def area_summary(df):
    act = df[df.status != "Resolved"]
    g = df.groupby("area").agg(total=("report_id", "count"), resolved=("status", lambda s: (s == "Resolved").sum()),
                               median_resolution_h=("resolution_hours", "median")).join(
        act.groupby("area").agg(active=("report_id", "count"), high_severity=("severity", lambda s: (s >= 4).sum()),
                                avg_active_priority=("priority", "mean"), oldest_open_days=("age_days", "max")), how="left")
    return g.fillna(0).round(1).sort_values("avg_active_priority", ascending=False).reset_index()


def category_summary(df):
    g = df.groupby("category_label").agg(reports=("report_id", "count"), avg_severity=("severity", "mean"),
                                         median_resolution_h=("resolution_hours", "median"),
                                         active=("status", lambda s: (s != "Resolved").sum()))
    return g.round(1).sort_values("reports", ascending=False).reset_index()


def weekly_flow(df):
    o = df.set_index("created_at").resample("W").size().rename("Opened")
    r = df.dropna(subset=["resolved_at"]).set_index("resolved_at").resample("W").size().rename("Resolved")
    return pd.concat([o, r], axis=1).fillna(0).astype(int).rename_axis("week").reset_index()


def weekly_by_category(df):
    return (df.set_index("created_at").groupby("category_label").resample("W").size()
            .rename("reports").reset_index().rename(columns={"created_at": "week"}))
