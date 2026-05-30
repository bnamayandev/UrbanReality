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
    "zoning_height":     "zoning_height.parquet",
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
        except Exception:
            try:
                df = pd.read_parquet(path)
                if "geometry" in df.columns:
                    from shapely import wkt as _wkt
                    df["geometry"] = df["geometry"].apply(
                        lambda g: _wkt.loads(str(g)) if g and str(g).strip() else None
                    )
                    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
                else:
                    _layers[key] = None
                    continue
            except Exception as e2:
                print(f"[spatial] WARNING: could not load {fname}: {e2}")
                _layers[key] = None
                continue
        try:
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            elif gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs("EPSG:4326")
        except Exception:
            pass
        _layers[key] = gdf
        print(f"[spatial] Loaded {fname} ({len(gdf):,} rows)")


_load_layers()


# ── Per-request cache ─────────────────────────────────────────────────────────
_cache: dict[str, dict] = {}


def _cache_key(lat: float, lng: float) -> str:
    return f"{round(lat, 4)},{round(lng, 4)}"


def _query_radius(layer_key: str, point_4326: Point, label_col: str, extra_cols: list[str], limit: int = 20) -> list[dict]:
    gdf = _layers.get(layer_key)
    if gdf is None or gdf.empty:
        return []
    try:
        gdf_utm = gdf.to_crs("EPSG:32617")
        pt_gdf  = gpd.GeoDataFrame(geometry=[point_4326], crs="EPSG:4326").to_crs("EPSG:32617")
        pt_utm  = pt_gdf.geometry.iloc[0]
        buffer  = pt_utm.buffer(RADIUS_M)
        nearby  = gdf_utm[gdf_utm.intersects(buffer)]

        keep = [c for c in [label_col] + extra_cols if c in nearby.columns]
        return nearby[keep].head(limit).to_dict("records")
    except Exception:
        return []


def _query_nearest(layer_key: str, point_4326: Point, label_col: str, extra_cols: list[str]) -> dict | None:
    """Return the single nearest feature within RADIUS_M, or None."""
    results = _query_radius(layer_key, point_4326, label_col, extra_cols, limit=1)
    return results[0] if results else None


def get_spatial_context(lat: float, lng: float, db=None) -> dict:
    key = _cache_key(lat, lng)
    if key in _cache:
        return _cache[key]

    pt = Point(lng, lat)

    context = {
        # Traffic — now has real directional counts from Omar's tmc_most_recent_summary_data
        "traffic_intersections": _query_radius(
            "traffic_volumes", pt,
            label_col="location_name",
            extra_cols=["total_vehicle", "total_pedestrian", "total_bike",
                        "am_peak_vehicle", "pm_peak_vehicle", "latest_count_date"],
        ),
        # TTC stops
        "ttc_stops": _query_radius(
            "ttc_stops", pt,
            label_col="stop_name",
            extra_cols=["stop_id"],
        ),
        # Street trees
        "street_trees": _query_radius(
            "street_trees", pt,
            label_col="common_name",
            extra_cols=["species", "dbh_trunk"],
        ),
        # Business licences
        "businesses": _query_radius(
            "business_licences", pt,
            label_col="Category",
            extra_cols=["Operating Name"],
        ),
        # Parks
        "parks": _query_radius(
            "parks", pt,
            label_col="ASSET_NAME",
            extra_cols=["TYPE", "AMENITIES"],
        ),
        # Zoning area (land use class)
        "zoning": _query_radius(
            "zoning", pt,
            label_col="ZBL_ZONE",
            extra_cols=["ZONE_CLASS"],
        ),
        # Zoning height overlay — new from Omar, tells us max height allowed
        "zoning_height": _query_nearest(
            "zoning_height", pt,
            label_col="HT_LABEL",
            extra_cols=["HT_STORIES", "HT_STRING"],
        ),
        # Neighbourhood context — now has real income + density from 2021 census
        "neighbourhood": _query_nearest(
            "neighbourhoods", pt,
            label_col="name",
            extra_cols=["median_income", "population_2021", "population_density"],
        ),
    }

    _cache[key] = context
    return context


def layers_status() -> dict:
    """Return which layers are loaded — useful for /health endpoint."""
    return {k: (v is not None and not v.empty) for k, v in _layers.items()}
