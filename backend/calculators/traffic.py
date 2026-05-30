"""
ITE-based daily trip calculator with TTC transit proximity modifier.

Replaces the XGBoost traffic model. The ITE formula is deterministic and
more accurate for new buildings than fitting XGBoost on ITE-derived labels.
Reference: ITE Trip Generation Manual, 11th edition.
"""

from __future__ import annotations
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"

# ITE Trip Generation Manual 11th edition rates.
# "per": "unit"      → rate × total_dwelling_units  (floors × units_per_floor)
# "per": "1000sqft"  → rate × (total_sqft / 1000)
_ITE_RATES: dict[str, dict] = {
    # Residential — ITE 220/221/222. High-rise has lower car ownership → fewer trips/unit.
    "residential":             {"rate": 6.65, "per": "unit"},   # ITE 221 mid-rise
    "residential (mid-rise)":  {"rate": 6.65, "per": "unit"},   # ITE 221
    "residential (high-rise)": {"rate": 4.20, "per": "unit"},   # ITE 222 urban high-rise
    # Mixed-use: residential tower above ground-floor retail.
    # Blended ~80% residential / 20% retail with 15% internal-capture discount.
    "mixed-use":               {"rate": 12.0, "per": "1000sqft"},
    # Commercial
    "commercial office":       {"rate": 11.03, "per": "1000sqft"},  # ITE 710
    # Retail
    "retail / podium":         {"rate": 42.70, "per": "1000sqft"},  # ITE 820
    "retail":                  {"rate": 42.70, "per": "1000sqft"},
    # Industrial
    "industrial":              {"rate": 6.97,  "per": "1000sqft"},  # ITE 110
    # Institutional — separate from office (ITE 610 hospital, ITE 520 school)
    "institutional":           {"rate": 13.22, "per": "1000sqft"},
    "hospital":                {"rate": 13.22, "per": "1000sqft"},  # ITE 610
    "school":                  {"rate": 14.30, "per": "1000sqft"},  # ITE 520
    # Assembly
    "assembly":                {"rate": 9.11,  "per": "1000sqft"},  # ITE 560 place of worship
    "place of worship":        {"rate": 9.11,  "per": "1000sqft"},  # ITE 560
}
_DEFAULT_RATE = {"rate": 11.03, "per": "1000sqft"}  # office as fallback

# Transit proximity discounts applied to base ITE trips.
# All TTC stops treated equally; higher tiers for closer proximity.
_TRANSIT_DISCOUNTS: dict[str, float] = {
    "transit_within_400m": 0.30,
    "transit_within_800m": 0.15,
    "none":                0.00,
}

_ttc_stops = None  # lazy-loaded GeoDataFrame; None if parquet is missing


def _load_ttc() -> None:
    global _ttc_stops
    if _ttc_stops is not None:
        return
    path = DATA_DIR / "ttc_stops.parquet"
    if not path.exists():
        return
    try:
        import geopandas as gpd
        _ttc_stops = gpd.read_parquet(path)
    except Exception as exc:
        print(f"[traffic] WARNING: could not load ttc_stops: {exc}")


def _transit_tier(lat: float, lng: float) -> str:
    """Return the transit discount tier for a lat/lng coordinate."""
    _load_ttc()
    if _ttc_stops is None:
        return "none"
    try:
        import geopandas as gpd
        from shapely.geometry import Point
        # Reproject to UTM zone 17N (metres) for accurate distance
        pt_m = gpd.GeoSeries([Point(lng, lat)], crs="EPSG:4326").to_crs("EPSG:26917").iloc[0]
        nearest_m = float(_ttc_stops.to_crs("EPSG:26917").distance(pt_m).min())
        if nearest_m < 400:
            return "transit_within_400m"
        if nearest_m < 800:
            return "transit_within_800m"
        return "none"
    except Exception as exc:
        print(f"[traffic] transit tier error: {exc}")
        return "none"


def estimate_daily_trips(building: dict) -> dict | None:
    """
    Estimate daily vehicle trips for a proposed building.

    Returns a dict with keys: score, daily_trips, daily_trips_base,
    transit_tier, description.  Returns None on unexpected error.
    """
    try:
        btype = (building.get("type") or "residential").lower().strip()
        ite = _ITE_RATES.get(btype, _DEFAULT_RATE)

        floors        = building.get("floors")        or 10
        footprint_m2  = building.get("footprint_m2")  or 2000
        units_per_floor = building.get("units_per_floor") or 10

        if ite["per"] == "unit":
            size = floors * units_per_floor
        else:
            total_sqft = footprint_m2 * floors * 10.764  # m² → sqft
            size = total_sqft / 1000

        base_trips = ite["rate"] * size

        lat = building.get("lat")
        lng = building.get("lng")
        tier = _transit_tier(lat, lng) if (lat and lng) else "none"
        discount = _TRANSIT_DISCOUNTS[tier]
        trips = base_trips * (1 - discount)

        # Impact score: 0 = minimal, 100 = extreme (2 000 trips → 100)
        score = min(100, int(trips / 20))

        transit_note = (
            f" TTC access within {'400' if '400' in tier else '800'}m"
            f" reduces vehicle trips by {int(discount * 100)}%."
            if tier != "none" else ""
        )
        severity = "significant" if trips > 500 else "moderate" if trips > 200 else "low"

        return {
            "score": score,
            "daily_trips": round(trips),
            "daily_trips_base": round(base_trips),
            "transit_tier": tier,
            "description": (
                f"Estimated {trips:.0f} daily vehicle trips "
                f"(ITE {ite['rate']}/{'unit' if ite['per'] == 'unit' else '1,000 sqft'})."
                f"{transit_note} "
                f"Peak-hour intersection impact: {severity}."
            ),
        }
    except Exception as exc:
        print(f"[traffic] estimate error: {exc}")
        return None
