"""
Train XGBoost models on Toronto Open Data.
Run after data_pipeline.py has downloaded all datasets.

    python ml/train_models.py

Saves to ml/models/:
  - energy_model.json                    predicts annual kWh from EWRB measurements
  - energy_building_type_encoder.pkl     LabelEncoder for building_type (required at inference)
  - economic_model.json                  predicts construction jobs via StatsCan I-O multipliers

Traffic is handled by the ITE calculator in backend/calculators/traffic.py — no model file needed.
"""

import json
import sys
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score
import xgboost as xgb

DATA_DIR  = Path(__file__).parent.parent / "data"
MODEL_DIR = Path(__file__).parent / "models"
COEFF_DIR = DATA_DIR / "coefficients"
MODEL_DIR.mkdir(exist_ok=True)

# GFA columns in the permits dataset (m²)
GFA_COLS = ["ASSEMBLY", "INSTITUTIONAL", "RESIDENTIAL",
            "BUSINESS_AND_PERSONAL_SERVICES", "MERCANTILE", "INDUSTRIAL"]


def _save_model(model: xgb.XGBRegressor, name: str, meta: dict):
    path = MODEL_DIR / f"{name}.json"
    model.save_model(str(path))
    (MODEL_DIR / f"{name}_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"  Saved {path.name}  meta={meta}")


def _load_permits() -> pd.DataFrame:
    path = DATA_DIR / "building_permits_cleared.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["EST_CONST_COST"] = pd.to_numeric(df["EST_CONST_COST"], errors="coerce")
    for c in GFA_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["total_gfa_m2"] = df[GFA_COLS].sum(axis=1)
    le = LabelEncoder()
    df["structure_type_enc"] = le.fit_transform(df["STRUCTURE_TYPE"].fillna("Unknown").astype(str))
    df["work_enc"] = le.fit_transform(df["WORK"].fillna("Unknown").astype(str))
    return df


# ── MODEL 1: Energy / Utility ────────────────────────────────────────────────

def _load_ewrb_combined() -> pd.DataFrame:
    """
    Load Ontario EWRB (primary: private buildings) + Toronto EWRB (supplementary:
    municipal buildings), normalise both to kWh/m² intensity, and return combined.

    Returned columns: building_type, elec_intensity_kwh_m2, gas_intensity_kwh_m2
    """
    frames = []

    # 1. Ontario provincial data — real commercial / multi-residential buildings
    ontario_path = DATA_DIR / "ewrb_ontario.parquet"
    if ontario_path.exists():
        ont = pd.read_parquet(ontario_path)
        ont["elec_intensity_kwh_m2"] = (
            pd.to_numeric(ont["elec_intensity_gj_m2"], errors="coerce") * 277.78
        )
        if "gas_intensity_gj_m2" in ont.columns:
            ont["gas_intensity_kwh_m2"] = (
                pd.to_numeric(ont["gas_intensity_gj_m2"], errors="coerce") * 277.78
            )
        else:
            ont["gas_intensity_kwh_m2"] = np.nan
        frames.append(
            ont[["building_type", "elec_intensity_kwh_m2", "gas_intensity_kwh_m2"]].copy()
        )
        print(f"  Ontario EWRB : {len(ont):,} rows")

    # 2. Toronto municipal data — supplementary (fire stations, water plants, etc.)
    toronto_path = DATA_DIR / "ewrb_energy.parquet"
    if toronto_path.exists():
        tor = pd.read_parquet(toronto_path)
        tor["floor_area_m2"] = pd.to_numeric(tor["floor_area_sqft"], errors="coerce") / 10.764
        tor["annual_kwh"]    = pd.to_numeric(tor["usage_electric_grid"], errors="coerce")
        tor = tor[(tor["floor_area_m2"] > 0) & (tor["annual_kwh"] > 0)].copy()
        tor["elec_intensity_kwh_m2"] = tor["annual_kwh"] / tor["floor_area_m2"]
        if "usage_natural_gas" in tor.columns:
            tor["gas_intensity_kwh_m2"] = (
                pd.to_numeric(tor["usage_natural_gas"], errors="coerce")
                * 277.78 / tor["floor_area_m2"]
            )
        else:
            tor["gas_intensity_kwh_m2"] = np.nan
        frames.append(
            tor[["building_type", "elec_intensity_kwh_m2", "gas_intensity_kwh_m2"]].copy()
        )
        print(f"  Toronto EWRB : {len(tor):,} rows")

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["elec_intensity_kwh_m2"])
    combined = combined[combined["elec_intensity_kwh_m2"] > 0].copy()

    # Cap per-column outliers at 99th percentile (data-entry errors / corner cases)
    for col in ["elec_intensity_kwh_m2", "gas_intensity_kwh_m2"]:
        p99 = combined[col].quantile(0.99)
        combined[col] = combined[col].where(combined[col] <= p99)

    return combined


def train_energy(df: pd.DataFrame):
    """
    Train electricity-intensity and gas-intensity models.
    Target is kWh/m²; at inference multiply by GFA to get annual absolute kWh.
    Training data: Ontario EWRB (private buildings) + Toronto EWRB (municipal).
    """
    print("\n=== Model 1: Energy / Utility ===")

    rows = _load_ewrb_combined()
    if rows.empty or len(rows) < 50:
        print(f"  SKIP: insufficient data ({len(rows)} rows)")
        return

    print(f"  Combined     : {len(rows):,} rows total")

    le_building = LabelEncoder()
    rows["building_type_enc"] = le_building.fit_transform(
        rows["building_type"].fillna("Other").astype(str)
    )

    # ── Electricity intensity model ───────────────────────────────────────────
    elec_rows = rows.dropna(subset=["elec_intensity_kwh_m2"])
    X = elec_rows[["building_type_enc"]].fillna(0)
    y = np.log1p(elec_rows["elec_intensity_kwh_m2"])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = xgb.XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05,
                              random_state=42, verbosity=0)
    model.fit(X_train, y_train)
    mae, r2 = (mean_absolute_error(y_test, model.predict(X_test)),
               r2_score(y_test, model.predict(X_test)))
    print(f"  Electricity  : n={len(elec_rows):,}  MAE={mae:.3f} log(kWh/m²)  R²={r2:.3f}")

    enc_path = MODEL_DIR / "energy_building_type_encoder.pkl"
    joblib.dump(le_building, str(enc_path))
    print(f"  Saved {enc_path.name}  ({len(le_building.classes_)} classes)")

    _save_model(model, "energy_model", {
        "features": ["building_type_enc"],
        "target": "log1p_elec_intensity_kwh_per_m2",
        "source": "Ontario EWRB (private) + Toronto EWRB (municipal)",
        "building_type_classes": list(le_building.classes_),
        "mae": round(float(mae), 4), "r2": round(float(r2), 4),
    })

    # ── Gas intensity model ───────────────────────────────────────────────────
    gas_rows = rows.dropna(subset=["gas_intensity_kwh_m2"])
    gas_rows = gas_rows[gas_rows["gas_intensity_kwh_m2"] > 0].copy()

    if len(gas_rows) < 50:
        print(f"  Gas SKIP: only {len(gas_rows)} rows with gas data")
        return

    Xg = gas_rows[["building_type_enc"]].fillna(0)
    yg = np.log1p(gas_rows["gas_intensity_kwh_m2"])

    Xg_train, Xg_test, yg_train, yg_test = train_test_split(Xg, yg, test_size=0.2, random_state=42)
    gas_model = xgb.XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05,
                                  random_state=42, verbosity=0)
    gas_model.fit(Xg_train, yg_train)
    gmae, gr2 = (mean_absolute_error(yg_test, gas_model.predict(Xg_test)),
                 r2_score(yg_test, gas_model.predict(Xg_test)))
    print(f"  Gas          : n={len(gas_rows):,}  MAE={gmae:.3f} log(kWh/m²)  R²={gr2:.3f}")

    _save_model(gas_model, "energy_gas_model", {
        "features": ["building_type_enc"],
        "target": "log1p_gas_intensity_kwh_per_m2",
        "source": "Ontario EWRB (private) + Toronto EWRB (municipal)",
        "building_type_classes": list(le_building.classes_),
        "mae": round(float(gmae), 4), "r2": round(float(gr2), 4),
    })


# ── MODEL 2: Traffic Generation (ITE-calibrated) ─────────────────────────────

def train_traffic(df: pd.DataFrame):
    print("\n=== Model 2: Traffic (ITE-calibrated) ===")
    ite_path = COEFF_DIR / "ite_trip_rates.csv"
    if not ite_path.exists():
        print("  SKIP: ite_trip_rates.csv not found")
        return

    ite = pd.read_csv(ite_path).set_index("building_type")["daily_trips_per_1000sqft"].to_dict()

    # Map permit use columns to ITE types
    ite_weights = {
        "RESIDENTIAL": ite.get("residential", 6.65),
        "ASSEMBLY": ite.get("commercial_office", 11.03),
        "INSTITUTIONAL": ite.get("commercial_office", 11.03),
        "BUSINESS_AND_PERSONAL_SERVICES": ite.get("commercial_office", 11.03),
        "MERCANTILE": ite.get("retail_general", 42.70),
        "INDUSTRIAL": ite.get("industrial_general", 6.97),
    }

    rows = df[df["total_gfa_m2"] > 50].copy()
    if len(rows) < 100:
        print("  SKIP: insufficient data")
        return

    def _trips(row):
        total = row["total_gfa_m2"] or 1
        # GFA is in m²; ITE rates are per 1,000 sqft → convert: 1 m² = 10.764 sqft
        sqft_total = total * 10.764
        weighted_rate = sum(ite_weights[c] * (row[c] / total) for c in GFA_COLS)
        return weighted_rate * sqft_total / 1000

    rows["daily_trips_est"] = rows.apply(_trips, axis=1)

    X = rows[["total_gfa_m2", "structure_type_enc", "work_enc"] + GFA_COLS].fillna(0)
    y = rows["daily_trips_est"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = xgb.XGBRegressor(n_estimators=150, max_depth=4, learning_rate=0.1,
                              random_state=42, verbosity=0)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    mae, r2 = mean_absolute_error(y_test, preds), r2_score(y_test, preds)
    print(f"  n={len(rows):,}  MAE={mae:.1f} trips  R²={r2:.3f}")

    _save_model(model, "traffic_model", {
        "features": list(X.columns),
        "target": "daily_trips_est",
        "ite_rates_used": ite_weights,
        "mae": round(mae, 2), "r2": round(r2, 4),
    })


# ── MODEL 3: Economic — construction jobs ─────────────────────────────────────

def train_economic(df: pd.DataFrame):
    print("\n=== Model 3: Economic / Jobs ===")
    io_path = COEFF_DIR / "statscan_io_multipliers.csv"

    jobs_per_1m = 7.0   # default: StatsCan ~7 person-years per $1M construction
    if io_path.exists():
        try:
            io = pd.read_csv(io_path)
            res = io[io["sector"].str.lower().str.contains("residential", na=False)]
            if not res.empty:
                jobs_per_1m = float(res["employment_per_1M_CAD"].iloc[0])
        except Exception:
            pass

    rows = df[df["EST_CONST_COST"].notna() & (df["EST_CONST_COST"] > 10_000)].copy()
    if len(rows) < 100:
        print("  SKIP: insufficient data")
        return

    rows["est_jobs"] = (rows["EST_CONST_COST"] / 1_000_000) * jobs_per_1m
    rows = rows[rows["est_jobs"] > 0]

    X = rows[["total_gfa_m2", "EST_CONST_COST", "structure_type_enc", "work_enc"] + GFA_COLS].fillna(0)
    y = np.log1p(rows["est_jobs"])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = xgb.XGBRegressor(n_estimators=150, max_depth=4, learning_rate=0.1,
                              random_state=42, verbosity=0)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    mae, r2 = mean_absolute_error(y_test, preds), r2_score(y_test, preds)
    print(f"  n={len(rows):,}  MAE(log-jobs)={mae:.3f}  R²={r2:.3f}")

    _save_model(model, "economic_model", {
        "features": list(X.columns),
        "target": "log1p_est_jobs",
        "statscan_jobs_per_1M_CAD": jobs_per_1m,
        "mae": round(float(mae), 4), "r2": round(float(r2), 4),
    })


if __name__ == "__main__":
    print(f"Data dir : {DATA_DIR}")
    print(f"Model dir: {MODEL_DIR}")
    df = _load_permits()
    if df.empty:
        print("ERROR: no permit data found - run data_pipeline.py first")
        sys.exit(1)
    print(f"Loaded {len(df):,} permits\n")
    train_energy(df)
    # Traffic uses the ITE calculator in backend/calculators/traffic.py — no model needed.
    train_economic(df)
    print("\n=== Done ===")
    print(f"  {len(list(MODEL_DIR.glob('*.json')))} model files in {MODEL_DIR}")
    print(f"  {len(list(MODEL_DIR.glob('*.pkl')))} encoder files in {MODEL_DIR}")
