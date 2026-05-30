"""
Train XGBoost models on Toronto Open Data.
Run after data_pipeline.py has downloaded all datasets.

    python ml/train_models.py

Saves three models to ml/models/:
  - energy_model.json     predicts kWh/m² energy intensity (rule-based + XGB)
  - traffic_model.json    predicts daily vehicle trips (ITE-calibrated XGB)
  - economic_model.json   predicts construction jobs via StatsCan I-O multipliers
"""

import json
import sys
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


# ── MODEL 1: Energy / Utility (kWh/m² intensity proxy) ───────────────────────

def train_energy(df: pd.DataFrame):
    print("\n=== Model 1: Energy / Utility ===")

    ewrb_path = DATA_DIR / "ewrb_energy.parquet"
    if not ewrb_path.exists():
        print("  SKIP: ewrb_energy.parquet not found — run data_pipeline.py first")
        return

    rows = pd.read_parquet(ewrb_path)
    rows["floor_area_m2"]          = pd.to_numeric(rows["floor_area_m2"],          errors="coerce")
    rows["annual_electricity_kwh"] = pd.to_numeric(rows["annual_electricity_kwh"], errors="coerce")
    rows = rows.dropna(subset=["floor_area_m2", "annual_electricity_kwh"])
    rows = rows[(rows["floor_area_m2"] > 0) & (rows["annual_electricity_kwh"] > 0)].copy()

    if len(rows) < 50:
        print(f"  SKIP: only {len(rows)} rows after filtering")
        return

    le = LabelEncoder()
    rows["building_type_enc"] = le.fit_transform(
        rows["building_type"].fillna("Unknown").astype(str)
    )
    rows["kwh_per_m2"] = rows["annual_electricity_kwh"] / rows["floor_area_m2"]

    X = rows[["floor_area_m2", "building_type_enc"]].fillna(0)
    y = np.log1p(rows["annual_electricity_kwh"])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = xgb.XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.1,
                              random_state=42, verbosity=0)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    mae, r2 = mean_absolute_error(y_test, preds), r2_score(y_test, preds)
    print(f"  n={len(rows):,}  MAE(log-kWh)={mae:.3f}  R²={r2:.3f}")

    _save_model(model, "energy_model", {
        "features": list(X.columns),
        "target": "log1p_annual_electricity_kwh",
        "source": "Toronto EWRB real measurements",
        "building_type_classes": list(le.classes_),
        "mae": round(mae, 4), "r2": round(r2, 4),
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
        "mae": round(mae, 4), "r2": round(r2, 4),
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
    train_traffic(df)
    train_economic(df)
    print("\n=== Done ===")
    print(f"  {len(list(MODEL_DIR.glob('*.json')))} model files in {MODEL_DIR}")
