"""
XGBoost model loader and inference for the impact analysis pipeline.
Models are loaded once at startup from ml/models/.
If model files don't exist, all predict_* functions return None and the
caller falls back to NeMoTron or the rule-based fallback.
"""

import json
import numpy as np
from pathlib import Path

try:
    import xgboost as xgb
    _XGB_AVAILABLE = True
except ImportError:
    _XGB_AVAILABLE = False

MODEL_DIR = Path(__file__).parent.parent / "ml" / "models"

GFA_COLS = ["ASSEMBLY", "INSTITUTIONAL", "RESIDENTIAL",
            "BUSINESS_AND_PERSONAL_SERVICES", "MERCANTILE", "INDUSTRIAL"]

# Building type → permit GFA column
TYPE_TO_GFA = {
    "residential (high-rise)":  "RESIDENTIAL",
    "residential (mid-rise)":   "RESIDENTIAL",
    "residential":              "RESIDENTIAL",
    "mixed-use":                "BUSINESS_AND_PERSONAL_SERVICES",
    "commercial office":        "BUSINESS_AND_PERSONAL_SERVICES",
    "retail / podium":          "MERCANTILE",
    "retail":                   "MERCANTILE",
    "industrial":               "INDUSTRIAL",
}

# Rough structure type encoding (matches LabelEncoder order from training)
# Mapping is approximate — unseen values default to 0
STRUCTURE_ENC = {
    "sfd - detached": 0, "sfd - semi-detached": 1, "duplex": 2,
    "triplex": 3, "fourplex": 4, "townhouse": 5,
    "apartment": 6, "condo": 7, "commercial": 8, "mixed": 9, "other": 10,
}
WORK_ENC = {
    "new": 0, "addition": 1, "alteration": 2, "demolition": 3,
    "repair": 4, "renovation": 5, "other": 6,
}


class _Models:
    energy:   "xgb.XGBRegressor | None" = None
    traffic:  "xgb.XGBRegressor | None" = None
    economic: "xgb.XGBRegressor | None" = None
    meta: dict = {}


_m = _Models()


def load_models():
    if not _XGB_AVAILABLE:
        return
    for name in ("energy_model", "traffic_model", "economic_model"):
        path = MODEL_DIR / f"{name}.json"
        meta_path = MODEL_DIR / f"{name}_meta.json"
        if not path.exists():
            continue
        try:
            model = xgb.XGBRegressor()
            model.load_model(str(path))
            setattr(_m, name.replace("_model", ""), model)
            if meta_path.exists():
                _m.meta[name] = json.loads(meta_path.read_text())
            print(f"[xgb] Loaded {name}.json")
        except Exception as e:
            print(f"[xgb] WARNING: could not load {name}: {e}")


def _build_feature_row(building: dict) -> dict:
    """Convert a building spec dict → feature dict matching training columns."""
    gfa_m2 = building.get("footprint_m2", 2000)
    floors = building.get("floors", 10)
    total_gfa = gfa_m2 * floors

    btype = building.get("type", "residential").lower()
    dominant_col = TYPE_TO_GFA.get(btype, "RESIDENTIAL")

    gfa_row = {c: 0.0 for c in GFA_COLS}
    gfa_row[dominant_col] = float(total_gfa)

    # Cost proxy: ~$3,000/m² construction cost for mid-rise residential
    cost_per_m2 = {"RESIDENTIAL": 3000, "BUSINESS_AND_PERSONAL_SERVICES": 4500,
                   "MERCANTILE": 3500, "INDUSTRIAL": 2000,
                   "ASSEMBLY": 5000, "INSTITUTIONAL": 5500}
    est_cost = total_gfa * cost_per_m2.get(dominant_col, 3000)

    structure_str = "apartment" if "residential" in btype else "commercial"
    work_str = "new"

    return {
        "total_gfa_m2": float(total_gfa),
        "structure_type_enc": float(STRUCTURE_ENC.get(structure_str, 0)),
        "work_enc": float(WORK_ENC.get(work_str, 0)),
        "EST_CONST_COST": float(est_cost),
        **{c: float(v) for c, v in gfa_row.items()},
    }


def _row_to_array(row: dict, feature_list: list) -> np.ndarray:
    return np.array([[row.get(f, 0.0) for f in feature_list]], dtype=np.float32)


def predict_energy(building: dict) -> dict | None:
    """Returns predicted annual kWh from real EWRB data and a 0-100 environmental score."""
    if _m.energy is None:
        return None
    try:
        meta = _m.meta.get("energy_model", {})
        row  = _build_feature_row(building)

        # Energy model uses only floor_area_m2 + building_type_enc
        btype = building.get("type", "residential").lower()
        dominant_col = TYPE_TO_GFA.get(btype, "RESIDENTIAL")
        type_enc_map = {"RESIDENTIAL": 0, "BUSINESS_AND_PERSONAL_SERVICES": 1,
                        "MERCANTILE": 2, "INDUSTRIAL": 3, "ASSEMBLY": 4, "INSTITUTIONAL": 5}
        feature_row = {
            "floor_area_m2":     row["total_gfa_m2"],
            "building_type_enc": float(type_enc_map.get(dominant_col, 0)),
        }
        features = meta.get("features", ["floor_area_m2", "building_type_enc"])
        X = _row_to_array(feature_row, features)

        log_kwh = float(_m.energy.predict(X)[0])
        kwh = np.expm1(log_kwh)
        gfa = row["total_gfa_m2"]
        intensity = kwh / max(gfa, 1)
        score = min(100, int(intensity / 3))   # ~300 kWh/m² → score 100
        return {
            "score": score,
            "annual_kwh": round(kwh),
            "intensity_kwh_per_m2": round(intensity, 1),
            "description": (
                f"Predicted annual electricity: {kwh/1000:.0f} MWh "
                f"({intensity:.0f} kWh/m²) — trained on {meta.get('source', 'Toronto EWRB')} data. "
                f"{'Above' if intensity > 200 else 'Within'} Toronto benchmark for this building type."
            ),
        }
    except Exception as e:
        print(f"[xgb] energy predict error: {e}")
        return None


def predict_traffic(building: dict) -> dict | None:
    """Returns predicted daily vehicle trips and a 0-100 traffic impact score."""
    if _m.traffic is None:
        return None
    try:
        meta  = _m.meta.get("traffic_model", {})
        row   = _build_feature_row(building)
        X     = _row_to_array(row, meta.get("features", list(row.keys())))
        trips = max(0.0, float(_m.traffic.predict(X)[0]))
        score = min(100, int(trips / 20))   # 2000 trips → score 100
        return {
            "score": score,
            "daily_trips": round(trips),
            "description": (
                f"Estimated +{trips:.0f} daily vehicle trips generated. "
                f"Peak-hour impact on surrounding intersections: "
                f"{'significant' if trips > 500 else 'moderate' if trips > 200 else 'low'}."
            ),
        }
    except Exception as e:
        print(f"[xgb] traffic predict error: {e}")
        return None


def predict_economic(building: dict) -> dict | None:
    """Returns predicted construction jobs and a 0-100 economic impact score."""
    if _m.economic is None:
        return None
    try:
        meta    = _m.meta.get("economic_model", {})
        row     = _build_feature_row(building)
        X       = _row_to_array(row, meta.get("features", list(row.keys())))
        log_jobs = float(_m.economic.predict(X)[0])
        jobs    = np.expm1(log_jobs)
        score   = min(95, max(30, int(50 + jobs / 10)))
        return {
            "score": score,
            "construction_jobs": round(jobs),
            "description": (
                f"Estimated {jobs:.0f} person-years of construction employment "
                f"(StatsCan I-O multiplier). "
                f"Permanent operational jobs depend on building type and tenancy."
            ),
        }
    except Exception as e:
        print(f"[xgb] economic predict error: {e}")
        return None


load_models()
