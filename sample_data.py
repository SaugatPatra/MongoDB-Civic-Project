"""Deterministic, clearly synthetic sample data (source='sample'). No real people or credentials."""
from __future__ import annotations
import random
from datetime import datetime, timedelta, timezone
from .schema import AREAS, CATEGORIES, build_report

BIAS = {"Old Market": ["garbage", "sidewalk", "pothole"], "Riverside": ["drainage", "water_leak", "tree"],
        "Tech Park": ["streetlight", "sign", "pothole"], "Station Quarter": ["pothole", "manhole", "garbage"],
        "Hillcrest": ["tree", "drainage", "sign"], "Lakeview": ["drainage", "tree", "streetlight"],
        "Mill District": ["water_leak", "manhole", "pothole"], "Garden Colony": ["streetlight", "garbage", "sidewalk"]}
BASE_SEV = {"manhole": 4, "tree": 3.5, "water_leak": 3.2, "pothole": 3.3, "drainage": 3, "streetlight": 2.8,
            "sidewalk": 2.6, "garbage": 2.3, "sign": 2.4}
EXPOSURE = {"pothole": (300, 4000), "streetlight": (100, 1500), "garbage": (80, 1500), "water_leak": (150, 2500),
            "sidewalk": (100, 2000), "manhole": (200, 3000), "drainage": (150, 2500), "tree": (100, 2500), "sign": (300, 3500)}
TEXT = {"pothole": "Deep pothole on the carriageway; two-wheelers swerving around it.",
        "streetlight": "Streetlight out for several nights; the stretch is very dark.",
        "garbage": "Waste pile growing beside the road, attracting strays and smell.",
        "water_leak": "Water leaking from a pipe joint and pooling on the road.",
        "sidewalk": "Footpath slabs broken; pedestrians forced onto the road.",
        "manhole": "Manhole cover missing, opening is a hazard at night.",
        "drainage": "Drain blocked; water stands after light rain.",
        "tree": "Large branch/tree fallen across part of the road.",
        "sign": "Traffic sign bent and facing the wrong way."}

def _details(cat, rng):
    out = {}
    for f in CATEGORIES[cat]["fields"]:
        k = f["kind"]
        out[f["key"]] = (rng.choice(f["options"]) if k == "select" else rng.randint(1, max(2, f["default"] * 2)) if k == "number"
                         else rng.random() < .4 if k == "bool" else f"SL-{rng.randint(100, 999)}")
    return out

def generate(n=170, seed=7, now=None):
    rng = random.Random(seed)
    now = now or datetime.now(timezone.utc)
    cores = {a: (lng + rng.gauss(0, .004), lat + rng.gauss(0, .004)) for a, (lng, lat) in AREAS.items()}
    areas = list(AREAS)
    docs = []
    for _ in range(n):
        area = rng.choices(areas, weights=[3, 2.5, 1.5, 3, 1.2, 1.5, 2.2, 1.3])[0]
        cat = rng.choice(BIAS[area]) if rng.random() < .7 else rng.choice(list(CATEGORIES))
        near_core = rng.random() < .6
        clng, clat = cores[area] if near_core else AREAS[area]
        sig = .0012 if near_core else .008
        lng, lat = clng + rng.gauss(0, sig), clat + rng.gauss(0, sig)
        sev = max(1, min(5, round(rng.gauss(BASE_SEV[cat], .9))))
        days = min(rng.expovariate(1 / 22), 75)
        created = now - timedelta(days=days, hours=rng.uniform(0, 12))
        doc = build_report(cat, area, sev, TEXT[cat], lat, lng, int(rng.uniform(*EXPOSURE[cat])), _details(cat, rng),
                           "Sample reporter" if rng.random() < .3 else "", "", source="sample", now=created)
        doc["supporting_reports"] = rng.choice([0, 0, 1, 1, 2, 3, 5, 8])
        p_res = .8 if days > 35 else .45 if days > 10 else .15
        roll = rng.random()
        if roll < p_res:
            age_h = (now - created).total_seconds() / 3600
            hrs = rng.uniform(8, 24 * 12)
            hrs = hrs if hrs < age_h else age_h * rng.uniform(.3, .9)
            done = created + timedelta(hours=hrs)
            doc.update(status="Resolved", resolved_at=done, resolution_hours=round(hrs, 1), updated_at=done)
            doc["status_history"].append({"status": "Resolved", "at": done.isoformat(), "note": "Resolved (sample)"})
        elif roll < p_res + (1 - p_res) * .3:
            t = created + timedelta(hours=rng.uniform(2, 48))
            if t < now:
                doc.update(status="In progress", updated_at=t)
                doc["status_history"].append({"status": "In progress", "at": t.isoformat(), "note": "Crew assigned (sample)"})
        docs.append(doc)
    return docs
