"""Quick smoke-test for all three inference paths. Run from project root:
    python data/test.py
"""
import sys
sys.path.insert(0, "backend")

import xgb_models as xm
from calculators.traffic import estimate_daily_trips

print("=== Fix 1: LabelEncoder encoding per building type ===")
buildings = [
    {"type": "commercial office",       "footprint_m2": 2000, "floors": 10},
    {"type": "retail",                   "footprint_m2": 2000, "floors": 10},
    {"type": "residential (high-rise)",  "footprint_m2": 2000, "floors": 10},
]
for b in buildings:
    btype  = b["type"].lower()
    col    = xm.TYPE_TO_GFA.get(btype, "RESIDENTIAL")
    ewrb   = xm._GFA_TO_EWRB.get(col, "Other")
    enc    = int(xm._m.energy_encoder.transform([ewrb])[0])
    result = xm.predict_energy(b)
    print(f"  {b['type']:30s}  ewrb={ewrb:40s}  enc={enc:2d}  kwh={result['annual_kwh']:>12,}  score={result['score']}")

print()
print("=== Fix 2: ITE calculator — transit discount + correct residential unit ===")
cases = [
    ("downtown residential", {"type": "residential (high-rise)", "floors": 30, "footprint_m2": 1200, "units_per_floor": 8,  "lat": 43.6532, "lng": -79.3832}),
    ("suburban residential", {"type": "residential (high-rise)", "floors": 30, "footprint_m2": 1200, "units_per_floor": 8,  "lat": 43.780,  "lng": -79.560}),
    ("suburban retail",      {"type": "retail",                  "floors": 1,  "footprint_m2": 5000, "units_per_floor": 0,  "lat": 43.780,  "lng": -79.560}),
]
for label, b in cases:
    r = estimate_daily_trips(b)
    print(f"  {label:25s}  tier={r['transit_tier']:25s}  base={r['daily_trips_base']:5d}  final={r['daily_trips']:5d}  score={r['score']}")

print()
print("=== Integration: all three models together ===")
b = {"type": "residential (high-rise)", "floors": 30, "footprint_m2": 1200,
     "units_per_floor": 8, "lat": 43.6532, "lng": -79.3832}
print("  Energy  :", xm.predict_energy(b))
print("  Traffic :", xm.predict_traffic(b))
print("  Economic:", xm.predict_economic(b))
