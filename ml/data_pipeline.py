"""
Download all Toronto Open Data datasets and save to data/ as GeoParquet / Parquet.

Run once before model training:
    pip install -r ml/requirements.txt
    python ml/data_pipeline.py

Everything is cached - re-running skips already-downloaded files.
Set FORCE_REFRESH=1 to re-download everything.
"""

import os
import re
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
from fetch import fetch, fetch_resource, fetch_gtfs_stops, fetch_csv_with_latlon, download_raster


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
    gdf, lm = fetch_csv_with_latlon(
        "street-tree-data",
        lat_col="LATITUDE", lon_col="LONGITUDE",
        extra_cols=["DBH_TRUNK", "COMMON_NAME", "SPECIES_DESC"],
    )
    gdf = gdf.rename(columns={"DBH_TRUNK": "dbh_trunk", "COMMON_NAME": "common_name", "SPECIES_DESC": "species"})
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
        profiles_raw, _ = fetch_resource(
            "neighbourhood-profiles",
            "neighbourhood-profiles-2021-158-model",
            sheet_name="hd2021_census_profile",
        )
        profiles_raw.columns = [str(c).strip() for c in profiles_raw.columns]
        var_col = profiles_raw.columns[0]

        variables = profiles_raw[var_col].astype(str)
        income_mask = variables.str.contains("Median after-tax income in 2020 among recipients", na=False, case=False)
        population_mask = variables.str.contains("Total - Age groups of the population", na=False, case=False)

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
        population_series = extract_row(population_mask)

        profile = pd.DataFrame({"profile_name": profiles_raw.columns[1:]})

        if income_series is not None:
            profile["median_income"] = profile["profile_name"].map(income_series)
        if population_series is not None:
            profile["population_2021"] = profile["profile_name"].map(population_series)

        hoods = hoods.merge(profile, left_on=name_col, right_on="profile_name", how="left")
        hoods = hoods.drop(columns=["profile_name"])
        if "population_2021" in hoods.columns:
            area_km2 = hoods.to_crs("EPSG:3347").area / 1_000_000
            hoods["population_density"] = hoods["population_2021"] / area_km2
    except Exception as e:
        print(f"    WARNING: neighbourhood profiles join failed ({e}) - saving polygons only")

    hoods = hoods.rename(columns={name_col: "name"})
    _save("neighbourhoods", hoods, lm)


def dl_zoning():
    """Save the two most useful zoning layers: base area and height overlay."""
    for out_name, resource_name in [
        ("zoning_area", "Zoning Area"),
        ("zoning_height", "Zoning Height Overlay"),
    ]:
        if cached(out_name):
            continue
        try:
            gdf, lm = fetch_resource("zoning-by-law", resource_name, as_geo=True)
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
        df, lm = fetch_resource(
            "traffic-volumes-at-intersections-for-all-modes",
            "tmc_most_recent_summary_data",
        )
        df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        df = df.dropna(subset=["latitude", "longitude"])
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
            crs="EPSG:4326",
        )
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


def dl_ewrb():
    if cached("ewrb_energy"):
        return
    try:
        resource = "annual-energy-consumption-data-2024.xlsx"
        props, lm = fetch_resource("annual-energy-consumption", resource, sheet_name="Properties")
        meters, _ = fetch_resource("annual-energy-consumption", resource, sheet_name="Meter Entries")

        props = props.rename(columns={
            "Property Name": "property_name",
            "Portfolio Manager ID": "portfolio_manager_id",
            "Street Address": "street_address",
            "City/Municipality": "city",
            "State/Province": "province",
            "Postal Code": "postal_code",
            "Country": "country",
            "Property Type - Self-Selected": "building_type",
            "Gross Floor Area": "floor_area_sqft",
            "GFA Units": "floor_area_units",
        })
        props["floor_area_sqft"] = pd.to_numeric(props["floor_area_sqft"], errors="coerce")

        meters = meters.rename(columns={
            "Portfolio Manager ID": "portfolio_manager_id",
            "Meter Type": "meter_type",
            "Usage/Quantity": "usage_quantity",
            "Cost ($)": "cost_usd",
        })
        meters["usage_quantity"] = pd.to_numeric(meters["usage_quantity"], errors="coerce")
        meters["cost_usd"] = pd.to_numeric(meters["cost_usd"], errors="coerce")
        meters["meter_type_key"] = meters["meter_type"].astype(str).apply(
            lambda value: re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        )

        usage = meters.pivot_table(
            index="portfolio_manager_id",
            columns="meter_type_key",
            values="usage_quantity",
            aggfunc="sum",
        ).add_prefix("usage_").reset_index()
        costs = meters.pivot_table(
            index="portfolio_manager_id",
            columns="meter_type_key",
            values="cost_usd",
            aggfunc="sum",
        ).add_prefix("cost_").reset_index()
        meter_counts = meters.pivot_table(
            index="portfolio_manager_id",
            columns="meter_type_key",
            values="meter_type",
            aggfunc="count",
        ).add_prefix("meter_records_").reset_index()

        df = (
            props
            .merge(usage, on="portfolio_manager_id", how="left")
            .merge(costs, on="portfolio_manager_id", how="left")
            .merge(meter_counts, on="portfolio_manager_id", how="left")
        )
        df["reporting_year"] = 2024
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
