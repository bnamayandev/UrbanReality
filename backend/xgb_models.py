"""
XGBoost model loader and inference for the impact analysis pipeline.
Models are loaded once at startup from ml/models/.
If model files don't exist, all predict_* functions return None and the
caller falls back to NeMoTron or the rule-based fallback.
"""

import json
import joblib
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

# GFA column → Ontario EWRB building type name used during training.
# These are PrimPropTypCalc values from the Ontario public EWRB release.
_GFA_TO_EWRB = {
    "RESIDENTIAL":                    "Multifamily Housing",
    "BUSINESS_AND_PERSONAL_SERVICES":  "Office",
    "MERCANTILE":                      "Retail Store",
    "INDUSTRIAL":                      "Distribution Center",
    "ASSEMBLY":                        "Other",
    "INSTITUTIONAL":                   "Other",
}


class _Models:
    energy:         "xgb.XGBRegressor | None" = None
    energy_gas:     "xgb.XGBRegressor | None" = None
    economic:       "xgb.XGBRegressor | None" = None
    energy_encoder: object = None   # sklearn LabelEncoder loaded from .pkl
    meta: dict = {}


_m = _Models()


def load_models():
    if not _XGB_AVAILABLE:
        return
    # Traffic is handled by the ITE calculator — no model file needed.
    for name in ("energy_model", "economic_model"):
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

    # Gas model (same feature schema as electricity model)
    gas_path = MODEL_DIR / "energy_gas_model.json"
    if gas_path.exists():
        try:
            model = xgb.XGBRegressor()
            model.load_model(str(gas_path))
            _m.energy_gas = model
            gas_meta_path = MODEL_DIR / "energy_gas_model_meta.json"
            if gas_meta_path.exists():
                _m.meta["energy_gas_model"] = json.loads(gas_meta_path.read_text())
            print("[xgb] Loaded energy_gas_model.json")
        except Exception as e:
            print(f"[xgb] WARNING: could not load energy_gas_model: {e}")

    enc_path = MODEL_DIR / "energy_building_type_encoder.pkl"
    if enc_path.exists():
        try:
            _m.energy_encoder = joblib.load(str(enc_path))
            print(f"[xgb] Loaded energy_building_type_encoder.pkl")
        except Exception as e:
            print(f"[xgb] WARNING: could not load energy encoder: {e}")


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
    """
    Predicts electricity and gas intensity (kWh/m²) then scales by GFA.
    Trained on Ontario EWRB (private buildings) + Toronto EWRB (municipal).
    Score: 0 = low energy use (good), 100 = high energy use (bad).
    """
    if _m.energy is None:
        return None
    try:
        meta = _m.meta.get("energy_model", {})
        row  = _build_feature_row(building)
        gfa  = row["total_gfa_m2"]

        btype        = building.get("type", "residential").lower()
        dominant_col = TYPE_TO_GFA.get(btype, "RESIDENTIAL")
        ewrb_type    = _GFA_TO_EWRB.get(dominant_col, "Other")

        if _m.energy_encoder is not None:
            enc      = _m.energy_encoder
            classes  = list(enc.classes_)
            target   = ewrb_type if ewrb_type in classes else "Office"
            type_enc = float(enc.transform([target])[0])
        else:
            classes  = meta.get("building_type_classes", [])
            target   = ewrb_type if ewrb_type in classes else (classes[0] if classes else "Other")
            type_enc = float(classes.index(target)) if target in classes else 0.0

        # Model predicts log1p(kWh/m²); multiply intensity × GFA for annual total
        feature_row = {"building_type_enc": type_enc}
        features    = meta.get("features", ["building_type_enc"])
        X = _row_to_array(feature_row, features)

        elec_intensity = float(np.expm1(float(_m.energy.predict(X)[0])))  # kWh/m²
        kwh = elec_intensity * gfa

        # Gas intensity prediction (same feature schema, no sanity gate needed)
        gas_kwh_eq = 0.0
        if _m.energy_gas is not None:
            try:
                gas_meta      = _m.meta.get("energy_gas_model", {})
                Xg            = _row_to_array(feature_row, gas_meta.get("features", list(feature_row.keys())))
                gas_intensity = float(np.expm1(float(_m.energy_gas.predict(Xg)[0])))  # kWh/m²
                gas_kwh_eq    = gas_intensity * gfa
            except Exception:
                pass

        total_kwh       = kwh + gas_kwh_eq
        total_intensity = total_kwh / max(gfa, 1)
        gas_gj          = gas_kwh_eq / 277.78 if gas_kwh_eq > 0 else None

        # Score: ~800 kWh/m² total → 100 (high-energy industrial); typical office ~400 → 50
        environmental_impact_score = min(100, int(total_intensity / 8))

        gas_note = (
            f" + {gas_gj:,.0f} GJ gas ({gas_kwh_eq / 1_000:.0f} MWh equiv.)"
            if gas_gj else ""
        )
        return {
            "score": environmental_impact_score,
            "score_meaning": "0 = low energy use (good), 100 = high energy use (bad)",
            "annual_kwh": round(kwh),
            "annual_gas_gj": round(gas_gj) if gas_gj else None,
            "total_energy_kwh": round(total_kwh),
            "intensity_kwh_per_m2": round(total_intensity, 1),
            "description": (
                f"Predicted annual electricity: {kwh / 1_000:.0f} MWh{gas_note}. "
                f"Total energy intensity: {total_intensity:.0f} kWh/m² "
                f"({'above' if total_intensity > 300 else 'within'} typical Toronto benchmark). "
                f"Environmental impact: {environmental_impact_score}/100 — higher means greater energy use."
            ),
        }
    except Exception as e:
        print(f"[xgb] energy predict error: {e}")
        return None


def predict_traffic(building: dict) -> dict | None:
    """Returns ITE-estimated daily vehicle trips and a 0-100 traffic impact score."""
    from calculators.traffic import estimate_daily_trips
    return estimate_daily_trips(building)


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
        if not np.isfinite(jobs) or jobs < 0:
            jobs = 100.0  # safe fallback if model returns NaN/inf
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
