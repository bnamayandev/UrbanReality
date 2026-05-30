"""
UrbanForge — end-to-end validation suite.

Tests XGBoost predictions, ITE traffic calculator, and the full
impact analysis pipeline (LLM output validation + hallucination checks).

Run from the backend directory:
    python tests/validate.py

Or against the live server (skip model unit tests):
    python tests/validate.py --api-only
"""

import sys
import os
import json
import time
import argparse
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

API_BASE = os.getenv("API_BASE", "http://localhost:8001")

PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"
WARN = "\033[93m WARN\033[0m"

_results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = ""):
    tag = PASS if condition else FAIL
    print(f"  [{tag}] {name}" + (f"  — {detail}" if detail else ""))
    _results.append((name, condition, detail))
    return condition


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── 1. XGBoost unit tests (no server needed) ──────────────────────────────────

def test_xgb_models():
    section("XGBoost / Calculator Unit Tests")

    try:
        from xgb_models import predict_energy, predict_traffic, predict_economic
    except ImportError as e:
        check("xgb_models import", False, str(e))
        return

    buildings = [
        {
            "name": "High-rise residential",
            "spec": {"type": "residential (high-rise)", "floors": 40,
                     "footprint_m2": 2000, "units_per_floor": 10,
                     "lat": 43.6532, "lng": -79.3832},
            "expected_trips_range": (500, 3000),
            "expected_jobs_range":  (100, 5000),
        },
        {
            "name": "Mid-rise residential",
            "spec": {"type": "residential (mid-rise)", "floors": 12,
                     "footprint_m2": 1500, "units_per_floor": 8,
                     "lat": 43.6532, "lng": -79.3832},
            "expected_trips_range": (200, 2000),
            "expected_jobs_range":  (50, 3000),
        },
        {
            "name": "Commercial office",
            "spec": {"type": "commercial office", "floors": 20,
                     "footprint_m2": 3000, "units_per_floor": 10,
                     "lat": 43.6532, "lng": -79.3832},
            "expected_trips_range": (500, 10000),
            "expected_jobs_range":  (100, 5000),
        },
        {
            "name": "Retail podium",
            "spec": {"type": "retail / podium", "floors": 3,
                     "footprint_m2": 5000, "units_per_floor": 1,
                     "lat": 43.6532, "lng": -79.3832},
            "expected_trips_range": (1000, 30000),
            "expected_jobs_range":  (10, 2000),
        },
    ]

    for b in buildings:
        print(f"\n  Building: {b['name']}")
        spec = b["spec"]

        # Traffic
        t = predict_traffic(spec)
        if t is None:
            check(f"traffic — {b['name']}", False, "returned None")
        else:
            trips = t["daily_trips"]
            lo, hi = b["expected_trips_range"]
            check(f"traffic score in 0-100",     0 <= t["score"] <= 100,      f"score={t['score']}")
            check(f"daily_trips in [{lo}, {hi}]", lo <= trips <= hi,          f"trips={trips}")
            check(f"description non-empty",       len(t["description"]) > 20, f"len={len(t['description'])}")
            check(f"transit_tier present",        "transit_tier" in t,        t.get("transit_tier", "missing"))

        # Energy
        e = predict_energy(spec)
        if e is None:
            check(f"energy — {b['name']}", False, "returned None (model missing?)")
        else:
            kwh = e["annual_kwh"]
            check(f"energy score in 0-100",   0 <= e["score"] <= 100,    f"score={e['score']}")
            check(f"annual_kwh > 0",          kwh > 0,                   f"kwh={kwh:,}")
            check(f"annual_kwh < 1B",         kwh < 1_000_000_000,       f"kwh={kwh:,}")
            check(f"intensity_kwh_per_m2 > 0", e["intensity_kwh_per_m2"] > 0,
                  f"intensity={e['intensity_kwh_per_m2']}")
            check(f"description non-empty",   len(e["description"]) > 20, f"len={len(e['description'])}")

        # Economic
        eco = predict_economic(spec)
        if eco is None:
            check(f"economic — {b['name']}", False, "returned None")
        else:
            jobs = eco["construction_jobs"]
            lo, hi = b["expected_jobs_range"]
            check(f"economic score in 0-100",      0 <= eco["score"] <= 100, f"score={eco['score']}")
            check(f"construction_jobs in [{lo}, {hi}]", lo <= jobs <= hi,    f"jobs={jobs}")
            check(f"description non-empty",        len(eco["description"]) > 20)


# ── 2. Traffic calculator specific checks ─────────────────────────────────────

def test_traffic_calculator():
    section("Traffic Calculator — ITE Sanity Checks")

    from calculators.traffic import estimate_daily_trips

    cases = [
        # (building_spec, expected_trips_approx, tolerance_pct)
        # 40-floor high-rise: 400 units × 4.20 = 1680 base, ~30% transit discount near downtown
        ({"type": "residential (high-rise)", "floors": 40, "footprint_m2": 2000,
          "units_per_floor": 10, "lat": 43.6532, "lng": -79.3832},
         1176, 40),   # 1680 × 0.70 transit discount ± 40%
        # Mid-rise: 120 units × 6.65 = 798 base
        ({"type": "residential (mid-rise)", "floors": 15, "footprint_m2": 1000,
          "units_per_floor": 8, "lat": 43.65, "lng": -79.38},
         798, 50),
        # Retail: large footprint, high ITE rate
        ({"type": "retail / podium", "floors": 2, "footprint_m2": 4000,
          "units_per_floor": 1, "lat": 43.65, "lng": -79.38},
         3000, 60),
    ]

    for spec, expected, tol_pct in cases:
        result = estimate_daily_trips(spec)
        if result is None:
            check(f"ITE calc — {spec['type']}", False, "returned None")
            continue
        trips = result["daily_trips"]
        lo = expected * (1 - tol_pct / 100)
        hi = expected * (1 + tol_pct / 100)
        check(
            f"ITE {spec['type']} trips in [{lo:.0f}, {hi:.0f}]",
            lo <= trips <= hi,
            f"got {trips} (expected ~{expected})"
        )
        check(f"transit_tier not None", result["transit_tier"] in
              ("transit_within_400m", "transit_within_800m", "none"))


# ── 3. API connectivity ────────────────────────────────────────────────────────

def test_api_health():
    section("API Health Check")
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        check("GET /health → 200",   r.status_code == 200, f"status={r.status_code}")
        data = r.json()
        check("spatial_layers key present", "spatial_layers" in data)
        loaded = [k for k, v in data.get("spatial_layers", {}).items() if v]
        check(f"spatial layers loaded ({len(loaded)})", len(loaded) >= 5,
              f"loaded: {loaded}")
    except Exception as e:
        check("GET /health reachable", False, str(e))


# ── 4. Full impact analysis — LLM output validation ───────────────────────────

def test_impact_analysis():
    section("Impact Analysis — LLM Output Validation")

    # Create a fresh test building
    payload = {
        "name":          "Validation Tower",
        "type":          "residential (high-rise)",
        "floors":        35,
        "footprint_m2":  1800,
        "units_per_floor": 10,
        "lat":           43.6510,
        "lng":           -79.3820,
    }
    try:
        r = requests.post(f"{API_BASE}/building",
                          json=payload, timeout=10)
        check("POST /building → 201", r.status_code == 201, f"status={r.status_code}")
        if r.status_code != 201:
            return
        building_id = r.json()["id"]
    except Exception as e:
        check("POST /building reachable", False, str(e))
        return

    print(f"\n  Created building id={building_id}. Fetching impact (may take up to 60s)...")
    t0 = time.time()
    try:
        r = requests.get(f"{API_BASE}/building/{building_id}/impact", timeout=120)
        elapsed = time.time() - t0
        check(f"GET /impact → 200 (took {elapsed:.0f}s)", r.status_code == 200,
              f"status={r.status_code}")
        if r.status_code != 200:
            print(f"  Response: {r.text[:300]}")
            return
    except Exception as e:
        check("GET /impact reachable", False, str(e))
        return

    impact = r.json()
    _validate_impact_json(impact)

    # Clean up
    try:
        requests.delete(f"{API_BASE}/building/{building_id}", timeout=5)
    except Exception:
        pass


def _validate_impact_json(impact: dict):
    """Validate structure, value ranges, and basic hallucination checks."""
    DIMENSIONS = ["environmental", "traffic", "economic", "infrastructure", "housing"]

    check("building_id present", "building_id" in impact)

    for dim in DIMENSIONS:
        d = impact.get(dim, {})
        score = d.get("score")
        desc  = d.get("description", "")

        check(f"{dim}.score present",       score is not None,      f"got: {score}")
        check(f"{dim}.score is int/float",  isinstance(score, (int, float)), f"type={type(score)}")
        check(f"{dim}.score in [0, 100]",   score is not None and 0 <= score <= 100, f"score={score}")
        check(f"{dim}.description non-empty", len(desc) > 20,        f"len={len(desc)}")
        check(f"{dim}.description < 1000 chars", len(desc) < 1000,   f"len={len(desc)}")

        # Hallucination / refusal checks
        red_flags = ["i cannot", "i don't know", "i'm not able", "as an ai",
                     "i apologize", "i'm sorry", "undefined", "null", "nan"]
        flagged = [f for f in red_flags if f in desc.lower()]
        check(f"{dim}.description no refusal phrases",
              len(flagged) == 0, f"found: {flagged}" if flagged else "")

        # Sanity: descriptions shouldn't be identical across dimensions
    descs = [impact.get(d, {}).get("description", "") for d in DIMENSIONS]
    unique = len(set(descs))
    check("all 5 descriptions are unique", unique == 5, f"unique count={unique}")

    # Score diversity — all 5 shouldn't be identical
    scores = [impact.get(d, {}).get("score", -1) for d in DIMENSIONS]
    check("scores are not all identical", len(set(scores)) > 1, f"scores={scores}")

    # Print summary
    print(f"\n  Impact scores:")
    for dim in DIMENSIONS:
        s = impact.get(dim, {}).get("score", "?")
        bar = "█" * (s // 10) if isinstance(s, int) else ""
        print(f"    {dim:<16} {str(s):>4}/100  {bar}")


# ── 5. Chat endpoint ───────────────────────────────────────────────────────────

def test_chat():
    section("Chat WebSocket — Basic Connectivity")
    try:
        import websocket as ws_lib
    except ImportError:
        print("  [SKIP] websocket-client not installed — skipping chat test")
        return

    ws_url = API_BASE.replace("http", "ws") + "/chat/9999"
    try:
        ws = ws_lib.create_connection(ws_url, timeout=5)
        ws.send(json.dumps({"message": "What is UrbanForge?"}))
        result = ws.recv()
        data = json.loads(result)
        check("WS /chat → response key present", "response" in data,
              f"keys={list(data.keys())}")
        check("WS response non-empty", len(data.get("response", "")) > 10)
        ws.close()
    except Exception as e:
        check("WS /chat reachable", False, str(e))


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-only", action="store_true",
                        help="Skip model unit tests (run API tests only)")
    args = parser.parse_args()

    print(f"\nUrbanForge Validation Suite")
    print(f"API base: {API_BASE}")

    if not args.api_only:
        test_xgb_models()
        test_traffic_calculator()

    test_api_health()
    test_impact_analysis()
    test_chat()

    # Summary
    total  = len(_results)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = total - passed

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  |  {failed} FAILED:")
        for name, ok, detail in _results:
            if not ok:
                print(f"    ✗ {name}" + (f" — {detail}" if detail else ""))
    else:
        print("  — all green")
    print(f"{'='*60}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
