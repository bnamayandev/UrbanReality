"""
Toronto Open Data download helpers.
All functions return a GeoDataFrame (spatial) or DataFrame (tabular).
Results are NOT cached here - caching is handled in data_pipeline.py.
"""

import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import geopandas as gpd
import requests
import urllib3
from shapely.geometry import shape
from shapely import wkt

# Windows (Python 3.13) does not include the city's CA cert in its bundle.
# All requests to the Toronto Open Data API use verify=False.
# This is safe: we're reading public government data, not transmitting secrets.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/"
_SSL = False  # set to True if you install the cert chain manually


def _package(ckan_id: str) -> dict:
    r = requests.get(BASE + "package_show", params={"id": ckan_id}, timeout=30, verify=_SSL)
    r.raise_for_status()
    return r.json()["result"]


def _last_modified(pkg: dict) -> str:
    dates = [r.get("last_modified", "") for r in pkg["resources"] if r.get("last_modified")]
    return max(dates) if dates else "unknown"


def list_formats(ckan_id: str) -> list[tuple[str, str]]:
    """Debug helper: print available resource formats for a dataset."""
    pkg = _package(ckan_id)
    return [(r.get("format", "?"), r.get("name", "?"), r.get("url", "?")[:80])
            for r in pkg["resources"]]


def _read_geo_bytes(content: bytes) -> gpd.GeoDataFrame:
    """
    Try to parse raw bytes as a geodataframe.
    Handles GeoJSON directly, or ZIP containing a shapefile.
    """
    # Check if it's a ZIP (shapefile archive)
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            shp_files = [n for n in z.namelist() if n.lower().endswith(".shp")]
            if shp_files:
                with tempfile.TemporaryDirectory() as tmpdir:
                    z.extractall(tmpdir)
                    return gpd.read_file(os.path.join(tmpdir, shp_files[0]))
            # ZIP without .shp - try the first file as GeoJSON
            first = z.namelist()[0]
            return gpd.read_file(io.BytesIO(z.read(first)))
    # Otherwise pass bytes directly (GeoJSON, etc.)
    try:
        return gpd.read_file(io.BytesIO(content))
    except Exception:
        df = pd.read_csv(io.BytesIO(content), encoding="latin-1", on_bad_lines="skip", low_memory=False)
        geom_col = next((c for c in df.columns if c.lower() == "geometry"), None)
        if geom_col is None:
            raise

        def parse_geometry(value):
            if pd.isna(value):
                return None
            text = str(value).strip()
            if not text:
                return None
            if text.startswith("{"):
                return shape(json.loads(text))
            return wkt.loads(text)

        geometry = df[geom_col].apply(parse_geometry)
        df = df.drop(columns=[geom_col])
        return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")


def fetch(ckan_id: str, prefer: str = "geojson") -> tuple[gpd.GeoDataFrame | pd.DataFrame, str]:
    """
    Download the first resource matching `prefer` from a CKAN package.
    prefer="geojson" -> tries geojson, then shp/zip (NOT bare "json" - that matches
                       the CKAN datastore API endpoint, not a real GeoJSON file).
    prefer="csv"     -> tries csv, then xlsx.
    Returns (GeoDataFrame|DataFrame, last_modified_string).
    """
    pkg = _package(ckan_id)

    geo_formats = ["geojson", "shp", "shapefile", "zip"]
    csv_formats = ["csv", "xlsx"]

    if prefer.lower() == "geojson":
        candidates = geo_formats
        is_geo = True
    elif prefer.lower() == "csv":
        candidates = csv_formats
        is_geo = False
    else:
        candidates = [prefer.lower()]
        is_geo = prefer.lower() in geo_formats

    for candidate in candidates:
        for res in pkg["resources"]:
            if res.get("format", "").lower() == candidate and res.get("url"):
                resp = requests.get(res["url"], timeout=300, verify=_SSL)
                resp.raise_for_status()
                lm = _last_modified(pkg)
                if is_geo:
                    return _read_geo_bytes(resp.content), lm
                elif candidate == "xlsx":
                    return pd.read_excel(io.BytesIO(resp.content)), lm
                else:
                    return (
                        pd.read_csv(io.BytesIO(resp.content), encoding="latin-1", on_bad_lines="skip", low_memory=False),
                        lm,
                    )

    raise ValueError(
        f"No {prefer!r} resource found for {ckan_id!r}. "
        f"Available: {[(r.get('format'), r.get('name')) for r in pkg['resources']]}"
    )


def fetch_csv_as_geo(
    ckan_id: str,
    lat_col: str,
    lon_col: str,
    extra_cols: list[str] | None = None,
) -> tuple[gpd.GeoDataFrame, str]:
    """
    Download a CSV with lat/lng columns and return as GeoDataFrame.
    Column name matching is case-insensitive.
    Used for point datasets: street trees, traffic volumes, business licences.
    """
    df, last_mod = fetch(ckan_id, prefer="csv")

    # Case-insensitive column lookup
    col_map = {c.lower(): c for c in df.columns}
    lat = col_map.get(lat_col.lower())
    lon = col_map.get(lon_col.lower())
    if lat is None or lon is None:
        raise ValueError(
            f"Lat/lon columns {lat_col!r}/{lon_col!r} not found in {ckan_id!r}. "
            f"Available: {list(df.columns[:20])}"
        )

    df[lat] = pd.to_numeric(df[lat], errors="coerce")
    df[lon] = pd.to_numeric(df[lon], errors="coerce")
    df = df.dropna(subset=[lat, lon])

    keep_lower = {c.lower() for c in (extra_cols or [])}
    keep = [lat, lon] + [col_map[c] for c in keep_lower if c in col_map and col_map[c] not in (lat, lon)]

    gdf = gpd.GeoDataFrame(
        df[keep],
        geometry=gpd.points_from_xy(df[lon], df[lat]),
        crs="EPSG:4326",
    )
    return gdf, last_mod


# Keep old name as alias so data_pipeline.py doesn't need a rename
fetch_csv_with_latlon = fetch_csv_as_geo


def fetch_gtfs_stops(ckan_id: str = "ttc-routes-and-schedules") -> tuple[gpd.GeoDataFrame, str]:
    """Download GTFS zip, extract stops.txt, return GeoDataFrame of stop points."""
    pkg = _package(ckan_id)
    last_mod = _last_modified(pkg)

    for res in pkg["resources"]:
        if res.get("format", "").lower() == "zip" and res.get("url"):
            raw = requests.get(res["url"], timeout=120, verify=_SSL).content
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                stops_name = next((n for n in z.namelist() if n.lower().endswith("stops.txt")), None)
                if stops_name is None:
                    raise ValueError("stops.txt not found in GTFS zip")
                stops = pd.read_csv(z.open(stops_name))

            gdf = gpd.GeoDataFrame(
                stops[["stop_id", "stop_name"]],
                geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
                crs="EPSG:4326",
            )
            return gdf, last_mod

    raise ValueError(f"No zip resource found for {ckan_id!r}")


def download_raster(ckan_id: str, out_path: Path) -> str:
    """Download a GeoTIFF raster from a CKAN package to out_path."""
    pkg = _package(ckan_id)
    last_mod = _last_modified(pkg)

    for res in pkg["resources"]:
        fmt = res.get("format", "").lower()
        if fmt in ("tiff", "geotiff", "tif") and res.get("url"):
            resp = requests.get(res["url"], stream=True, timeout=300, verify=_SSL)
            resp.raise_for_status()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
            return last_mod

    raise ValueError(f"No TIFF resource found for {ckan_id!r}")
