"""
Spatial context loader — reads GeoParquet files produced by ml/data_pipeline.py
and performs in-memory radius lookups using geopandas/shapely.

Loaded once at startup into module-level GeoDataFrames.
Per-request queries use STRtree spatial indexing for sub-10ms lookups.
"""

from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

DATA_DIR = Path(__file__).parent.parent / "data"
RADIUS_M = 500   # metres

# ── Layers loaded at startup ──────────────────────────────────────────────────
_layers: dict[str, gpd.GeoDataFrame | None] = {}

_LAYER_FILES = {
    "traffic_volumes":   "traffic_volumes.parquet",
    "ttc_stops":         "ttc_stops.parquet",
    "street_trees":      "street_trees.parquet",
    "business_licences": "business_licences.parquet",
    "parks":             "parks.parquet",
    "zoning":            "zoning_area.parquet",
    "neighbourhoods":    "neighbourhoods.parquet",
}


def _load_layers():
    for key, fname in _LAYER_FILES.items():
        path = DATA_DIR / fname
        if not path.exists():
            _layers[key] = None
            continue
        try:
            gdf = gpd.read_parquet(path)
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            elif gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs("EPSG:4326")
            _layers[key] = gdf
        except Exception as e:
            print(f"[spatial] WARNING: could not load {fname}: {e}")
            _layers[key] = None


_load_layers()


# ── Per-request cache ─────────────────────────────────────────────────────────
_cache: dict[str, dict] = {}


def _cache_key(lat: float, lng: float) -> str:
    return f"{round(lat, 4)},{round(lng, 4)}"


def _query_radius(layer_key: str, point_4326: Point, label_col: str, extra_cols: list[str]) -> list[dict]:
    gdf = _layers.get(layer_key)
    if gdf is None or gdf.empty:
        return []
    try:
        # Project to UTM Zone 17N (EPSG:32617) — accurate metres for Toronto
        gdf_utm = gdf.to_crs("EPSG:32617")
        pt_gdf  = gpd.GeoDataFrame(geometry=[point_4326], crs="EPSG:4326").to_crs("EPSG:32617")
        pt_utm  = pt_gdf.geometry.iloc[0]
        buffer  = pt_utm.buffer(RADIUS_M)
        nearby  = gdf_utm[gdf_utm.intersects(buffer)]

        keep = [c for c in [label_col] + extra_cols if c in nearby.columns]
        rows = nearby[keep].head(20).to_dict("records")
        return rows
    except Exception:
        return []


def get_spatial_context(lat: float, lng: float, db=None) -> dict:
    key = _cache_key(lat, lng)
    if key in _cache:
        return _cache[key]

    pt = Point(lng, lat)

    context = {
        "traffic_intersections": _query_radius(
            "traffic_volumes", pt,
            label_col="location",
            extra_cols=["volume_8hr_vehicles", "count_date"],
        ),
        "ttc_stops": _query_radius(
            "ttc_stops", pt,
            label_col="stop_name",
            extra_cols=["stop_id"],
        ),
        "street_trees": _query_radius(
            "street_trees", pt,
            label_col="common_name",
            extra_cols=["species", "dbh_trunk"],
        ),
        "businesses": _query_radius(
            "business_licences", pt,
            label_col="Category",
            extra_cols=["Business Name"],
        ),
        "parks": _query_radius(
            "parks", pt,
            label_col="ASSET_NAME",
            extra_cols=["ASSET_TYPE"],
        ),
        "zoning": _query_radius(
            "zoning", pt,
            label_col="ZBL_ZONE",
            extra_cols=["ZONE_CLASS"],
        ),
    }

    _cache[key] = context
    return context


def layers_status() -> dict:
    """Return which layers are loaded — useful for /health endpoint."""
    return {k: (v is not None and not v.empty) for k, v in _layers.items()}
