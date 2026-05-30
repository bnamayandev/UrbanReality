"""
Download all Toronto Open Data datasets and save to data/ as GeoParquet / Parquet.

Run once before model training:
    pip install -r ml/requirements.txt
    python ml/data_pipeline.py

Everything is cached - re-running skips already-downloaded files.
Set FORCE_REFRESH=1 to re-download everything.
"""

import io
import os
import sys
from pathlib import Path

import pandas as pd
import geopandas as gpd
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "coefficients").mkdir(exist_ok=True)

PERMITS_FILTER_DATE = os.getenv("PERMITS_FILTER_DATE", "2020-01-01")
FORCE = os.getenv("FORCE_REFRESH", "0") == "1"

# Add ml/ to path so fetch.py is importable
sys.path.insert(0, str(Path(__file__).parent))
from fetch import fetch, fetch_gtfs_stops, fetch_csv_with_latlon, download_raster, _package, _last_modified, _SSL


def _save(name: str, data: gpd.GeoDataFrame | pd.DataFrame, last_mod: str):
    out = DATA_DIR / f"{name}.parquet"
    data.to_parquet(out)
    print(f"  [{name}] {len(data):,} rows -> {out.name}  (source: {last_mod})")


def cached(name: str) -> bool:
    if FORCE:
        return False
    exists = (DATA_DIR / f"{name}.parquet").exists()
    if exists:
        print(f"  [{name}] already exists - skipping (set FORCE_REFRESH=1 to re-download)")
    return exists


# ---------------------------------------------------------------------------
# 1. SPATIAL LAYERS  (GeoJSON -> GeoParquet)
# ---------------------------------------------------------------------------

def dl_street_trees():
    if cached("street_trees"):
        return
    # Dataset has a WKT geometry column — use fetch() directly
    gdf, lm = fetch("street-tree-data", prefer="geojson")
    rename = {}
    col_upper = {c.upper(): c for c in gdf.columns}
    for src, dst in [("DBH_TRUNK", "dbh_trunk"), ("COMMON_NAME", "common_name"),
                     ("BOTANICAL_NAME", "species"), ("SPECIES_DESC", "species")]:
        if src in col_upper:
            rename[col_upper[src]] = dst
    gdf = gdf.rename(columns=rename)
    _save("street_trees", gdf, lm)


def dl_neighbourhoods():
    """Download neighbourhood polygons AND profiles CSV, then join income + density."""
    if cached("neighbourhoods"):
        return

    # Polygon boundaries
    hoods, lm = fetch("neighbourhoods", prefer="geojson")
    hoods.columns = [c.upper() for c in hoods.columns]
    if "GEOMETRY" in hoods.columns:
        hoods = hoods.rename(columns={"GEOMETRY": "geometry"}).set_geometry("geometry")
    name_col = next((c for c in hoods.columns if c != "geometry" and ("NAME" in c or "HOOD" in c)), hoods.columns[0])

    # Wide-format profiles CSV (columns = neighbourhood names, rows = variables)
    try:
        profiles_raw, _ = fetch("neighbourhood-profiles", prefer="csv")
        profiles_raw.columns = [str(c).strip() for c in profiles_raw.columns]
        var_col = profiles_raw.columns[0]

        variables = profiles_raw[var_col].astype(str)
        income_mask = variables.str.contains("Median after-tax income", na=False, case=False)
        density_mask = variables.str.contains("Population density", na=False, case=False)

        def extract_row(mask):
            rows = profiles_raw[mask]
            if rows.empty:
                return None
            return (
                rows.iloc[0, 1:]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
                .apply(pd.to_numeric, errors="coerce")
            )

        income_series = extract_row(income_mask)
        density_series = extract_row(density_mask)

        if income_series is not None:
            income_series.name = "median_income"
            hoods = hoods.set_index(name_col).join(income_series, how="left").reset_index()
        if density_series is not None:
            density_series.name = "population_density"
            hoods = hoods.set_index(name_col).join(density_series, how="left").reset_index()
    except Exception as e:
        print(f"    WARNING: neighbourhood profiles join failed ({e}) - saving polygons only")

    hoods = hoods.rename(columns={name_col: "name"})
    _save("neighbourhoods", hoods, lm)


def dl_zoning():
    """Save the two most useful zoning layers: base area and height overlay."""
    for out_name, keywords in [
        ("zoning_area",   ["zoning area", "general zoning", "zoning bylaw area"]),
        ("zoning_height", ["height", "height overlay"]),
    ]:
        if cached(out_name):
            continue
        try:
            gdf, lm = fetch("zoning-by-law", prefer="geojson")
            # The GeoJSON may already be the right layer, or may have a 'layer' property
            if "ZONE_CLASS" in gdf.columns or "ZBL_ZONE" in gdf.columns:
                _save(out_name, gdf, lm)
            else:
                print(f"    [{out_name}] downloaded but could not identify layer columns - saving raw")
                _save(out_name, gdf, lm)
        except Exception as e:
            print(f"    WARNING: {out_name} failed ({e})")


def dl_centreline():
    if cached("street_centreline"):
        return
    gdf, lm = fetch("toronto-centreline-tcl", prefer="geojson")
    _save("street_centreline", gdf, lm)


def dl_traffic_volumes():
    if cached("traffic_volumes"):
        return
    try:
        # Traffic volumes has lat/lng columns
        gdf, lm = fetch_csv_with_latlon(
            "traffic-volumes-at-intersections-for-all-modes",
            lat_col="latitude", lon_col="longitude",
            extra_cols=["location_id", "location", "8_hr_vehicle_volume",
                        "8_hr_pedestrian_volume", "count_date"],
        )
        # Normalise the volume column name
        vol_col = next((c for c in gdf.columns if "vehicle" in c.lower() and "volume" in c.lower()), None)
        if vol_col:
            gdf = gdf.rename(columns={vol_col: "volume_8hr_vehicles"})
        _save("traffic_volumes", gdf, lm)
    except Exception as e:
        print(f"    WARNING: traffic_volumes failed ({e})")


def dl_parks():
    for name, ckan_id in [
        ("parks", "parks-and-recreation-facilities"),
        ("green_spaces", "green-spaces"),
    ]:
        if cached(name):
            continue
        try:
            gdf, lm = fetch(ckan_id, prefer="geojson")
            _save(name, gdf, lm)
        except Exception as e:
            print(f"    WARNING: {name} failed ({e})")


def dl_cycling_network():
    if cached("cycling_network"):
        return
    try:
        gdf, lm = fetch("cycling-network", prefer="geojson")
        _save("cycling_network", gdf, lm)
    except Exception as e:
        print(f"    WARNING: cycling_network failed ({e})")


def dl_development_applications():
    if cached("development_applications"):
        return
    try:
        gdf, lm = fetch("development-applications", prefer="geojson")
        _save("development_applications", gdf, lm)
    except Exception as e:
        print(f"    WARNING: development_applications failed ({e})")


def dl_heritage():
    if cached("heritage_properties"):
        return
    try:
        gdf, lm = fetch("heritage-properties", prefer="geojson")
        _save("heritage_properties", gdf, lm)
    except Exception as e:
        print(f"    WARNING: heritage_properties failed ({e})")


# ---------------------------------------------------------------------------
# 2. TABULAR TRAINING DATA  (CSV -> Parquet)
# ---------------------------------------------------------------------------

EWRB_RENAME = {
    "Property GFA - Self-Reported (ft²)": "floor_area_sqft",
    "Electricity Use - Grid Purchase (kWh)": "annual_electricity_kwh",
    "Natural Gas Use (GJ)": "annual_gas_gj",
    "Water Use (m³)": "annual_water_m3",
    "GHG Emissions Intensity (kg CO2e/ft²)": "ghg_intensity",
    "Total GHG Emissions (kg CO2e)": "total_ghg_kg",
    "Property Type": "building_type",
    "Year Built": "year_built",
    "Number of Floors": "num_floors",
    "City": "city",
    "Postal Code": "postal_code",
    "Ward": "ward",
}


def _parse_ewrb_xlsx(raw: bytes) -> pd.DataFrame | None:
    """Parse one EWRB Excel file — handles both the multi-level older format and the newer flat format."""
    try:
        # Try multi-level header (2015–2020 format)
        df = pd.read_excel(io.BytesIO(raw), engine="openpyxl", header=[5, 6, 7])
        cols = df.columns.tolist()

        floor_col  = next((c for c in cols if "Total Floor Area" in str(c[0])), None)
        type_col   = next((c for c in cols if "Operation Type"   in str(c[0])), None)
        elec_col   = next((c for c in cols if "Electricity" in str(c) and "Quantity" in str(c)), None)
        gas_col    = next((c for c in cols if "Natural Gas"  in str(c) and "Quantity" in str(c)), None)

        if elec_col is None or floor_col is None:
            return None

        out = pd.DataFrame({
            "building_type":        df[type_col].values  if type_col  else "Unknown",
            "floor_area_m2":        pd.to_numeric(df[floor_col], errors="coerce"),
            "annual_electricity_kwh": pd.to_numeric(df[elec_col],  errors="coerce"),
            "annual_gas_m3":        pd.to_numeric(df[gas_col],   errors="coerce") if gas_col else None,
        })
        out = out.dropna(subset=["floor_area_m2", "annual_electricity_kwh"])
        out = out[(out["floor_area_m2"] > 0) & (out["annual_electricity_kwh"] > 0)]
        return out
    except Exception:
        return None


def dl_ewrb():
    if cached("ewrb_energy"):
        return
    try:
        import requests as _req
        pkg = _package("annual-energy-consumption")
        lm  = _last_modified(pkg)
        frames = []
        for res in pkg["resources"]:
            name = res.get("name", "")
            fmt  = res.get("format", "").lower()
            url  = res.get("url", "")
            if fmt == "xlsx" and "data" in name.lower() and url:
                try:
                    raw   = _req.get(url, timeout=120, verify=_SSL).content
                    parsed = _parse_ewrb_xlsx(raw)
                    if parsed is not None and len(parsed) > 0:
                        frames.append(parsed)
                        print(f"    [ewrb] {name}: {len(parsed)} usable rows")
                    else:
                        print(f"    [ewrb] {name}: skipped (no parseable energy data)")
                except Exception as e2:
                    print(f"    [ewrb] WARNING skipping {name}: {e2}")

        if not frames:
            raise ValueError("No usable EWRB data found across all years")

        df = pd.concat(frames, ignore_index=True)
        _save("ewrb_energy", df, lm)
    except Exception as e:
        print(f"    WARNING: ewrb_energy failed ({e})")


def dl_building_permits():
    for name, ckan_id in [
        ("building_permits_cleared", "building-permits-cleared-permits"),
        ("building_permits_active",  "building-permits-active-permits"),
    ]:
        if cached(name):
            continue
        try:
            df, lm = fetch(ckan_id, prefer="csv")
            # Normalise date column name (varies between datasets)
            date_col = next(
                (c for c in df.columns if "issue" in c.lower() and "date" in c.lower()), None
            )
            if date_col and name == "building_permits_cleared":
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
                df = df[df[date_col] >= PERMITS_FILTER_DATE]
                print(f"    [{name}] filtered to {PERMITS_FILTER_DATE}+ -> {len(df):,} rows")
            _save(name, df, lm)
        except Exception as e:
            print(f"    WARNING: {name} failed ({e})")


def dl_business_licences():
    if cached("business_licences"):
        return
    try:
        df, lm = fetch(
            "municipal-licensing-and-standards-business-licences-and-permits",
            prefer="csv",
        )
        _save("business_licences", df, lm)
    except Exception as e:
        print(f"    WARNING: business_licences failed ({e})")


def dl_property_tax():
    for name, ckan_id in [
        ("property_tax", "property-tax-collection"),
        ("cva_residential", "current-value-assessment-cva-information-residential-property-types"),
    ]:
        if cached(name):
            continue
        try:
            df, lm = fetch(ckan_id, prefer="csv")
            _save(name, df, lm)
        except Exception as e:
            print(f"    WARNING: {name} failed ({e})")


# ---------------------------------------------------------------------------
# 3. SPECIAL CASES
# ---------------------------------------------------------------------------

def dl_ttc_stops():
    if cached("ttc_stops"):
        return
    try:
        gdf, lm = fetch_gtfs_stops("ttc-routes-and-schedules")
        _save("ttc_stops", gdf, lm)
    except Exception as e:
        print(f"    WARNING: ttc_stops failed ({e})")


def dl_forest_cover():
    out = DATA_DIR / "forest_cover.tif"
    if not FORCE and out.exists():
        print("  [forest_cover] already exists - skipping")
        return
    try:
        lm = download_raster("forest-and-land-cover", out)
        size_mb = out.stat().st_size / 1_048_576
        print(f"  [forest_cover] {size_mb:.1f} MB -> {out.name}  (source: {lm})")
    except Exception as e:
        print(f"    WARNING: forest_cover failed ({e})")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print(f"=== UrbanForge Data Pipeline ===")
    print(f"Output dir : {DATA_DIR}")
    print(f"Permit cut : {PERMITS_FILTER_DATE}")
    print(f"Force      : {FORCE}\n")

    print("-- Spatial layers ----------------------------------")
    dl_street_trees()
    dl_neighbourhoods()
    dl_zoning()
    dl_centreline()
    dl_traffic_volumes()
    dl_parks()
    dl_cycling_network()
    dl_development_applications()
    dl_heritage()

    print("\n-- Tabular training data ---------------------------")
    dl_ewrb()
    dl_building_permits()
    dl_business_licences()
    dl_property_tax()

    print("\n-- Special cases -----------------------------------")
    dl_ttc_stops()
    dl_forest_cover()

    print("\n=== Done ===")
    parquet_files = list(DATA_DIR.glob("*.parquet"))
    tif_files = list(DATA_DIR.glob("*.tif"))
    print(f"  {len(parquet_files)} parquet files")
    print(f"  {len(tif_files)} raster files")
    print(f"  Total: {sum(f.stat().st_size for f in parquet_files + tif_files) / 1_048_576:.0f} MB")


if __name__ == "__main__":
    main()
