"""Data access: one interface, two backends (local JSON demo store, MongoDB Atlas via PyMongo)."""
from __future__ import annotations
import json, math, os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from . import sample_data

load_dotenv()
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "demo_reports.json"
DT_FIELDS = ("created_at", "updated_at", "resolved_at")


class StoreError(Exception):
    """Raised for any storage problem, with a message safe to show users."""


def setting(name, default=None):
    """Read from Streamlit secrets first (Cloud), then environment / .env."""
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name, default) or default


def haversine_m(lng1, lat1, lng2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def status_fields(doc, status, now):
    """Fields to set on a status change. Tracks resolution time when marking Resolved."""
    f = {"status": status, "updated_at": now}
    if status == "Resolved":
        f["resolved_at"] = now
        f["resolution_hours"] = round((now - doc["created_at"]).total_seconds() / 3600, 1)
    else:  # re-opened
        f["resolved_at"], f["resolution_hours"] = None, None
    return f


class DemoStore:
    name, is_demo = "Local demo storage (JSON file)", True

    def __init__(self, path=DATA_FILE):
        self.path = Path(path)
        if not self.path.exists():
            self.seed_sample()

    def _read(self):
        try:
            docs = json.loads(self.path.read_text())
            for d in docs:
                for k in DT_FIELDS:
                    if d.get(k): d[k] = datetime.fromisoformat(d[k])
            return docs
        except Exception as e:
            raise StoreError(f"Could not read demo data file ({e}). Delete {self.path.name} to regenerate it.") from e

    def _write(self, docs):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            out = [{**d, **{k: d[k].isoformat() for k in DT_FIELDS if d.get(k)}} for d in docs]
            self.path.write_text(json.dumps(out))
        except OSError as e:
            raise StoreError(f"Could not write demo data: {e}") from e

    def list_reports(self): return sorted(self._read(), key=lambda d: d["created_at"], reverse=True)

    def insert(self, doc): self._write(self._read() + [doc]); return doc

    def update_status(self, rid, status, note=""):
        docs, now = self._read(), datetime.now(timezone.utc)
        for d in docs:
            if d["report_id"] == rid:
                d.update(status_fields(d, status, now))
                d.setdefault("status_history", []).append({"status": status, "at": now.isoformat(), "note": note})
                return self._write(docs)
        raise StoreError(f"Report {rid} not found.")

    def add_support(self, rid):
        docs = self._read()
        for d in docs:
            if d["report_id"] == rid: d["supporting_reports"] += 1
        self._write(docs)

    def nearby(self, lng, lat, radius_m, include_resolved=True):
        out = []
        for d in self._read():
            dist = haversine_m(lng, lat, *d["location"]["coordinates"])
            if dist <= radius_m and (include_resolved or d["status"] != "Resolved"):
                out.append({**d, "distance_m": round(dist, 1)})
        return sorted(out, key=lambda d: d["distance_m"])

    def seed_sample(self):
        keep = [d for d in self._read() if d.get("source") != "sample"] if self.path.exists() else []
        self._write(keep + sample_data.generate())

    def clear_sample(self): self._write([d for d in self._read() if d.get("source") != "sample"])


class MongoStore:
    is_demo = False

    def __init__(self, uri, db="civicpulse", collection="reports"):
        try:
            from pymongo import MongoClient
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)
            self.client.admin.command("ping")
            self.col = self.client[db][collection]
            self.ensure_indexes()
        except Exception as e:
            raise StoreError(f"Could not connect to MongoDB ({type(e).__name__}). Check MONGODB_URI, the database user, "
                             "and Atlas Network Access.") from e
        self.name = f"MongoDB Atlas · {db}.{collection}"

    def ensure_indexes(self):
        from pymongo import ASCENDING, DESCENDING, GEOSPHERE
        c = self.col
        c.create_index([("location", GEOSPHERE)], name="geo_2dsphere")
        c.create_index("report_id", unique=True, name="report_id_unique")
        c.create_index("category", name="category")
        c.create_index("status", name="status")
        c.create_index([("created_at", DESCENDING)], name="created_at_desc")
        c.create_index("severity", name="severity")
        c.create_index([("status", ASCENDING), ("severity", DESCENDING)], name="status_severity")

    def _run(self, fn):
        try: return fn()
        except StoreError: raise
        except Exception as e: raise StoreError(f"MongoDB operation failed: {type(e).__name__}: {e}") from e

    def list_reports(self): return self._run(lambda: list(self.col.find({}, {"_id": 0}).sort("created_at", -1).limit(5000)))

    def insert(self, doc): self._run(lambda: self.col.insert_one(dict(doc))); return doc

    def update_status(self, rid, status, note=""):
        def go():
            doc = self.col.find_one({"report_id": rid}, {"_id": 0, "created_at": 1})
            if not doc: raise StoreError(f"Report {rid} not found.")
            now = datetime.now(timezone.utc)
            self.col.update_one({"report_id": rid}, {"$set": status_fields(doc, status, now),
                                "$push": {"status_history": {"status": status, "at": now.isoformat(), "note": note}}})
        self._run(go)

    def add_support(self, rid): self._run(lambda: self.col.update_one({"report_id": rid}, {"$inc": {"supporting_reports": 1}}))

    def nearby(self, lng, lat, radius_m, include_resolved=True):
        query = {} if include_resolved else {"status": {"$ne": "Resolved"}}
        pipe = [{"$geoNear": {"near": {"type": "Point", "coordinates": [lng, lat]}, "distanceField": "distance_m",
                              "maxDistance": radius_m, "spherical": True, "query": query}}, {"$project": {"_id": 0}}]
        return self._run(lambda: list(self.col.aggregate(pipe)))

    def seed_sample(self):
        def go():
            self.col.delete_many({"source": "sample"})
            self.col.insert_many(sample_data.generate())
        self._run(go)

    def clear_sample(self): self._run(lambda: self.col.delete_many({"source": "sample"}))


def get_store():
    """Return (store, notice). Falls back to demo storage with a notice if MongoDB is unavailable."""
    backend, uri = (setting("STORAGE_BACKEND", "") or "").lower(), setting("MONGODB_URI")
    if backend == "mongodb" or (not backend and uri):
        if not uri:
            return DemoStore(), "STORAGE_BACKEND is 'mongodb' but MONGODB_URI is empty. Using demo storage."
        try:
            return MongoStore(uri, setting("MONGODB_DB", "civicpulse"), setting("MONGODB_COLLECTION", "reports")), None
        except StoreError as e:
            return DemoStore(), f"{e} Falling back to demo storage."
    return DemoStore(), None
