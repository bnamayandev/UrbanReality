"""
UrbanForge backend test suite.
Run from the backend/ directory:
    pytest tests/ -v
"""

import sys
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)

# ── /health ───────────────────────────────────────────────────────────────────

def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_includes_spatial_layers():
    r = client.get("/health")
    assert "spatial_layers" in r.json()
    assert isinstance(r.json()["spatial_layers"], dict)


# ── POST /building ─────────────────────────────────────────────────────────────

SAMPLE_BUILDING = {
    "name": "Test Tower",
    "type": "Residential (High-rise)",
    "material": "Concrete & Glass",
    "floors": 30,
    "footprint_m2": 2000,
    "units_per_floor": 12,
    "lat": 43.6445,
    "lng": -79.3795,
    "status": "Under Review",
}


def test_create_building_returns_201():
    r = client.post("/building", json=SAMPLE_BUILDING)
    assert r.status_code == 201


def test_create_building_returns_id():
    r = client.post("/building", json=SAMPLE_BUILDING)
    body = r.json()
    assert "id" in body
    assert isinstance(body["id"], int)
    assert body["id"] > 0


def test_create_building_reflects_fields():
    r = client.post("/building", json=SAMPLE_BUILDING)
    body = r.json()
    assert body["floors"] == SAMPLE_BUILDING["floors"]
    assert body["lat"] == SAMPLE_BUILDING["lat"]
    assert body["lng"] == SAMPLE_BUILDING["lng"]


def test_create_building_missing_required_field():
    bad = {k: v for k, v in SAMPLE_BUILDING.items() if k != "floors"}
    r = client.post("/building", json=bad)
    assert r.status_code == 422


def test_create_building_optional_name_none():
    payload = {**SAMPLE_BUILDING, "name": None}
    r = client.post("/building", json=payload)
    assert r.status_code == 201


# ── GET /buildings ─────────────────────────────────────────────────────────────

def test_list_buildings_returns_200():
    r = client.get("/buildings")
    assert r.status_code == 200


def test_list_buildings_returns_list():
    r = client.get("/buildings")
    assert isinstance(r.json(), list)


def test_list_buildings_contains_created():
    r = client.post("/building", json=SAMPLE_BUILDING)
    bid = r.json()["id"]
    buildings = client.get("/buildings").json()
    ids = [b["id"] for b in buildings]
    assert bid in ids


def test_list_buildings_schema():
    client.post("/building", json=SAMPLE_BUILDING)
    buildings = client.get("/buildings").json()
    assert len(buildings) > 0
    b = buildings[0]
    for field in ["id", "type", "floors", "lat", "lng", "status"]:
        assert field in b, f"Missing field: {field}"


# ── GET /building/{id}/impact ──────────────────────────────────────────────────

def _create_building() -> int:
    r = client.post("/building", json=SAMPLE_BUILDING)
    assert r.status_code == 201
    return r.json()["id"]


def test_impact_returns_200():
    bid = _create_building()
    r = client.get(f"/building/{bid}/impact")
    assert r.status_code == 200


def test_impact_404_for_unknown_building():
    r = client.get("/building/999999/impact")
    assert r.status_code == 404


def test_impact_has_all_dimensions():
    bid = _create_building()
    r = client.get(f"/building/{bid}/impact")
    body = r.json()
    for dim in ["environmental", "traffic", "economic", "infrastructure", "housing"]:
        assert dim in body, f"Missing dimension: {dim}"


def test_impact_dimension_has_score_and_description():
    bid = _create_building()
    r = client.get(f"/building/{bid}/impact")
    body = r.json()
    for dim in ["environmental", "traffic", "economic", "infrastructure", "housing"]:
        assert "score" in body[dim]
        assert "description" in body[dim]
        assert isinstance(body[dim]["score"], int)
        assert 0 <= body[dim]["score"] <= 100


def test_impact_scores_are_bounded():
    bid = _create_building()
    r = client.get(f"/building/{bid}/impact")
    for dim_data in r.json().values():
        if isinstance(dim_data, dict) and "score" in dim_data:
            assert 0 <= dim_data["score"] <= 100


def test_impact_cached_on_second_call():
    bid = _create_building()
    r1 = client.get(f"/building/{bid}/impact")
    r2 = client.get(f"/building/{bid}/impact")
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()


# ── XGBoost model predictions ─────────────────────────────────────────────────

def test_xgb_energy_predict():
    from xgb_models import predict_energy
    result = predict_energy({"type": "Residential (High-rise)", "floors": 30, "footprint_m2": 2000})
    if result is None:
        pytest.skip("XGBoost energy model not trained yet")
    assert "score" in result
    assert "annual_kwh" in result
    assert 0 <= result["score"] <= 100
    assert result["annual_kwh"] > 0


def test_xgb_traffic_predict():
    from xgb_models import predict_traffic
    result = predict_traffic({"type": "Residential (High-rise)", "floors": 30, "footprint_m2": 2000})
    if result is None:
        pytest.skip("XGBoost traffic model not trained yet")
    assert "score" in result
    assert "daily_trips" in result
    assert 0 <= result["score"] <= 100
    assert result["daily_trips"] >= 0


def test_xgb_economic_predict():
    from xgb_models import predict_economic
    result = predict_economic({"type": "Residential (High-rise)", "floors": 30, "footprint_m2": 2000})
    if result is None:
        pytest.skip("XGBoost economic model not trained yet")
    assert "score" in result
    assert "construction_jobs" in result
    assert 0 <= result["score"] <= 100
    assert result["construction_jobs"] >= 0


def test_xgb_commercial_vs_residential_traffic():
    from xgb_models import predict_traffic
    r1 = predict_traffic({"type": "Retail / Podium",          "floors": 5,  "footprint_m2": 3000})
    r2 = predict_traffic({"type": "Residential (High-rise)", "floors": 30, "footprint_m2": 2000})
    if r1 is None or r2 is None:
        pytest.skip("XGBoost traffic model not trained yet")
    # Retail has much higher ITE trip rate than residential
    assert r1["daily_trips"] > r2["daily_trips"]


# ── Image generation ──────────────────────────────────────────────────────────

def test_generate_image_endpoint_exists():
    # Route moved to /generate/building-image (Rehan's router)
    # Supports direct params — bypasses NeMoTron entirely, fully deterministic
    r = client.post("/generate/building-image", json={
        "building_type": "skyscraper",
        "style": "modern_glass_tower",
        "floors": 30,
        "size": "medium",
    })
    assert r.status_code == 200
    body = r.json()
    assert "image_b64" in body
    assert "metadata" in body
    assert len(body["image_b64"]) > 100   # non-empty base64


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_create_building_extreme_floors():
    payload = {**SAMPLE_BUILDING, "floors": 1}
    r = client.post("/building", json=payload)
    assert r.status_code == 201


def test_create_building_large_footprint():
    payload = {**SAMPLE_BUILDING, "footprint_m2": 50000}
    r = client.post("/building", json=payload)
    assert r.status_code == 201


def test_create_building_invalid_lat_lng_type():
    payload = {**SAMPLE_BUILDING, "lat": "not-a-number"}
    r = client.post("/building", json=payload)
    assert r.status_code == 422
