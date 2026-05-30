"""
Spatial query helpers — pull Toronto Open Data context within a radius of a point.
All queries use PostGIS ST_DWithin on SRID 4326 (degrees). 500m ≈ 0.0045 degrees.
Results are cached in memory to avoid repeated DB round-trips for the same location.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

RADIUS_DEG = 0.0045   # ~500m at Toronto's latitude
_cache: dict = {}


def _cache_key(lat: float, lng: float) -> str:
    return f"{round(lat, 4)},{round(lng, 4)}"


def get_spatial_context(lat: float, lng: float, db: Session) -> dict:
    key = _cache_key(lat, lng)
    if key in _cache:
        return _cache[key]

    point = f"ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)"

    def query(table: str, label_col: str, extra_cols: str = "") -> list:
        cols = f"{label_col}{', ' + extra_cols if extra_cols else ''}"
        sql = text(f"""
            SELECT {cols}
            FROM {table}
            WHERE ST_DWithin(geom, {point}, :radius)
            LIMIT 20
        """)
        try:
            rows = db.execute(sql, {"radius": RADIUS_DEG}).mappings().all()
            return [dict(r) for r in rows]
        except Exception:
            return []

    context = {
        "traffic_intersections": query("traffic_volumes", "intersection_id", "volume_daily"),
        "ttc_stops": query("ttc_stops", "stop_name", "routes"),
        "street_trees": query("street_trees", "tree_id", "species, diameter_cm"),
        "businesses": query("business_licences", "business_name", "category"),
        "parks": query("parks", "park_name", "area_m2"),
        "zoning": query("zoning_bylaws", "zone_code", "zone_description, max_height_m"),
    }

    _cache[key] = context
    return context
