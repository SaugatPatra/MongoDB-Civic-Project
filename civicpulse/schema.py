"""Report schema: shared fields + category-specific `details` sub-document."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

STATUSES = ["Open", "In progress", "Resolved"]
SEVERITY_LABELS = {1: "Minor", 2: "Low", 3: "Moderate", 4: "High", 5: "Critical"}

# Fictional wards: name -> (lng, lat). Replace with your city's wards.
AREAS = {
    "Old Market": (75.8243, 26.9239), "Riverside": (75.7920, 26.9120),
    "Tech Park": (75.8600, 26.8900), "Station Quarter": (75.7870, 26.9200),
    "Hillcrest": (75.8330, 26.9560), "Lakeview": (75.8050, 26.9400),
    "Mill District": (75.8450, 26.9050), "Garden Colony": (75.8000, 26.8850),
}

def S(key, label, *options): return {"key": key, "label": label, "kind": "select", "options": list(options)}
def N(key, label, default, max_=10000): return {"key": key, "label": label, "kind": "number", "default": default, "max": max_}
def B(key, label): return {"key": key, "label": label, "kind": "bool"}
def T(key, label): return {"key": key, "label": label, "kind": "text"}

CATEGORIES = {
    "pothole": {"label": "Pothole", "icon": "🕳️", "color": "#F59E0B", "fields": [
        N("width_cm", "Approx. width (cm)", 40, 500), N("depth_cm", "Approx. depth (cm)", 8, 100),
        S("lane", "Where on the road", "Kerb side", "Middle of lane", "Multiple lanes", "Junction")]},
    "streetlight": {"label": "Broken streetlight", "icon": "💡", "color": "#FACC15", "fields": [
        T("pole_id", "Pole ID (if visible)"), S("fault", "Fault", "Not working", "Flickering", "Damaged pole", "Exposed wiring")]},
    "garbage": {"label": "Garbage accumulation", "icon": "🗑️", "color": "#84CC16", "fields": [
        S("volume", "Volume", "Small", "Medium", "Large", "Overflowing"),
        S("waste_type", "Waste type", "Household", "Construction debris", "Mixed", "Possibly hazardous")]},
    "water_leak": {"label": "Water leak", "icon": "💧", "color": "#38BDF8", "fields": [
        S("flow", "Flow", "Seepage", "Steady flow", "Burst / gushing"),
        S("water_type", "Water type", "Drinking water", "Sewage", "Unknown")]},
    "sidewalk": {"label": "Damaged sidewalk", "icon": "🚶", "color": "#A78BFA", "fields": [
        N("length_m", "Damaged length (m)", 3, 500), S("hazard", "Hazard", "Cracked", "Uplifted slabs", "Missing slabs", "Blocked")]},
    "manhole": {"label": "Open manhole", "icon": "⚠️", "color": "#F43F5E", "fields": [
        S("cover_status", "Cover status", "Missing", "Displaced", "Broken"), B("barrier_placed", "Cone / barrier already placed")]},
    "drainage": {"label": "Drainage problem", "icon": "🌊", "color": "#2DD4BF", "fields": [
        S("blockage", "Blockage", "Partial", "Full", "Overflowing"), N("standing_water_cm", "Standing water (cm)", 5, 200)]},
    "tree": {"label": "Fallen tree", "icon": "🌳", "color": "#22C55E", "fields": [
        S("blocking", "Blocking", "Road", "Footpath", "Power lines", "Nothing"), S("tree_size", "Tree size", "Small", "Medium", "Large")]},
    "sign": {"label": "Damaged traffic sign", "icon": "🚧", "color": "#FB923C", "fields": [
        S("sign_type", "Sign type", "Stop", "Speed limit", "Warning", "Direction", "Other"),
        S("condition", "Condition", "Missing", "Bent / fallen", "Faded", "Obstructed")]},
}

def build_report(category, area, severity, description, lat, lng, exposure, details,
                 reporter_name="", reporter_contact="", source="user", now=None):
    """Validate input and return a report document (GeoJSON Point is [lng, lat])."""
    if category not in CATEGORIES: raise ValueError("Unknown issue category.")
    if area not in AREAS: raise ValueError("Unknown area.")
    if not 1 <= int(severity) <= 5: raise ValueError("Severity must be between 1 and 5.")
    if len((description or "").strip()) < 10: raise ValueError("Please describe the issue in at least 10 characters.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180): raise ValueError("Coordinates are out of range.")
    if exposure < 0: raise ValueError("Public exposure cannot be negative.")
    now = now or datetime.now(timezone.utc)
    doc = {
        "report_id": "CP-" + uuid.uuid4().hex[:6].upper(), "category": category, "area": area,
        "severity": int(severity), "description": description.strip(),
        "location": {"type": "Point", "coordinates": [float(lng), float(lat)]},
        "exposure": int(exposure), "supporting_reports": 0, "status": "Open",
        "created_at": now, "updated_at": now, "resolved_at": None, "resolution_hours": None,
        "details": details, "source": source,
        "status_history": [{"status": "Open", "at": now.isoformat(), "note": "Report received"}],
    }
    if reporter_name.strip() or reporter_contact.strip():
        doc["reporter"] = {"name": reporter_name.strip() or None, "contact": reporter_contact.strip() or None}
    return doc
