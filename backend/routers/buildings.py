import os
import re
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID, ST_DWithin
from openai import AsyncOpenAI
from dotenv import load_dotenv

from database import get_db
from models import Building, Impact, AnalysisModule, AppUser
from schemas import BuildingCreate, BuildingOut, ImpactOut, ImpactDimension
from spatial import get_spatial_context
from xgb_models import predict_energy, predict_traffic, predict_economic
from auth import require_org_user

load_dotenv()

router = APIRouter(prefix="/building", tags=["buildings"])

# ── NeMoTron client — created lazily so MODEL_URL changes take effect ─────────
def _get_client() -> AsyncOpenAI:
    load_dotenv(override=True)
    return AsyncOpenAI(
        base_url=os.getenv("MODEL_URL", "http://localhost:11434/v1"),
        api_key=os.getenv("NGC_API_KEY", "not-needed"),
    )

def _get_model() -> str:
    return os.getenv("MODEL_NAME", "nemotron-3-super:latest")

_IMPACT_SYSTEM = """You are an urban planning AI analyst for the city of Toronto.
Given a proposed building's specifications and nearby geospatial context,
produce a structured impact assessment across five dimensions.

Respond ONLY with valid JSON in exactly this format:
{
  "environmental": { "score": <0-100>, "description": "<2 sentences>" },
  "traffic":       { "score": <0-100>, "description": "<2 sentences>" },
  "economic":      { "score": <0-100>, "description": "<2 sentences>" },
  "infrastructure":{ "score": <0-100>, "description": "<2 sentences>" },
  "housing":       { "score": <0-100>, "description": "<2 sentences>" }
}
Score: 0 = minimal impact, 100 = extreme impact. Cite real numbers where possible."""


async def _run_nemotron(building: dict, spatial: dict) -> dict:
    traffic = spatial.get("traffic_intersections", [])
    trees = spatial.get("street_trees", [])
    stops = spatial.get("ttc_stops", [])
    bizs = spatial.get("businesses", [])
    parks = spatial.get("parks", [])
    zoning = spatial.get("zoning", [])
    zh = spatial.get("zoning_height")
    hood = spatial.get("neighbourhood")

    total_v = sum(t.get("total_vehicle", 0) or 0 for t in traffic)
    am_peak = sum(t.get("am_peak_vehicle", 0) or 0 for t in traffic)
    pm_peak = sum(t.get("pm_peak_vehicle", 0) or 0 for t in traffic)

    prompt = f"""
Building: {json.dumps(building, indent=2)}
Neighbourhood: {json.dumps(hood) if hood else "n/a"}
Zoning: {json.dumps(zoning[:1])}  Height overlay: {json.dumps(zh) if zh else "none"}
Traffic ({len(traffic)} intersections within 500m):
  Daily vehicles: {total_v:,}  AM peak: {am_peak:,}  PM peak: {pm_peak:,}
  Sample: {json.dumps(traffic[:3])}
Transit: {len(stops)} TTC stops within 500m - {json.dumps(stops[:3])}
Trees: {len(trees)} within 500m - species: {[t.get('common_name') for t in trees[:5]]}
Parks: {json.dumps(parks[:2])}
Businesses: {len(bizs)} active ({list(set(b.get('Category','') for b in bizs[:20] if b.get('Category')))})
Produce the JSON impact assessment."""

    resp = await _get_client().chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": _IMPACT_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=1024,
        extra_body={"think": False},
    )
    msg = resp.choices[0].message
    # Thinking models may return null content with response in reasoning field
    content = (msg.content or "").strip()
    if not content:
        content = (getattr(msg, "reasoning", None) or "").strip()
    # Strip any remaining <think>...</think> blocks
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    raw = None
    if "```" in content:
        for part in content.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                try:
                    raw = json.loads(part)
                    break
                except json.JSONDecodeError:
                    continue
    if raw is None:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        raw = json.loads(m.group() if m else content)
    return _sanitize_impact(raw)


def _sanitize_impact(data: dict) -> dict:
    result = {}
    for dim in ["environmental", "traffic", "economic", "infrastructure", "housing"]:
        d = data.get(dim, {})
        try:
            score = max(0, min(100, int(float(d.get("score", 50)))))
        except (TypeError, ValueError):
            score = 50
        desc = str(d.get("description", "")).strip()[:900] or f"Impact analysis for {dim} dimension."
        result[dim] = {"score": score, "description": desc}
    return result


def _fallback_impact(building: dict) -> dict:
    floors = building.get("floors", 20)
    fp = building.get("footprint_m2", 2000)
    units = building.get("units_per_floor", 10)
    total = floors * units
    return {
        "environmental": {"score": min(90, int(fp / 100)), "description": f"Estimated {int(fp / 10)} trees displaced."},
        "traffic": {"score": min(90, floors * 2), "description": f"Estimated +{floors * 14} daily vehicle trips."},
        "economic": {"score": min(95, 50 + floors), "description": f"~{total} new residents add local economic demand."},
        "infrastructure": {"score": min(85, floors * 2), "description": f"Water demand: +{total * 220} L/day."},
        "housing": {"score": max(10, 80 - floors), "description": f"Adds {total} units against tight vacancy."},
    }


def _submission_to_out(s: Building) -> dict:
    floors = max(1, int(round(float(s.proposed_height_m or 3.5) / 3.5)))
    footprint_m2 = float(s.proposed_floor_area_sqm or 0) / floors if s.proposed_floor_area_sqm else 0.0
    return {
        "id": s.id,
        "name": s.project_name,
        "type": s.building_type or "unknown",
        "floors": floors,
        "footprint_m2": footprint_m2,
        "units_per_floor": s.proposed_units,
        "lat": s.site_lat,
        "lng": s.site_lng,
        "status": s.status,
        "org_id": None,
        "org_name": None,
    }


def _submission_spec(s: Building) -> dict:
    out = _submission_to_out(s)
    return {
        "type": out["type"],
        "material": None,
        "floors": out["floors"],
        "footprint_m2": out["footprint_m2"],
        "units_per_floor": out["units_per_floor"],
        "lat": out["lat"],
        "lng": out["lng"],
    }


@router.post("", response_model=BuildingOut, status_code=201)
def create_building(
    payload: BuildingCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_org_user),
):
    submission = Building(
        user_id=current_user.id,
        project_name=payload.name,
        site_lat=payload.lat,
        site_lng=payload.lng,
        building_type=payload.type,
        proposed_height_m=payload.floors * 3.5,
        proposed_floor_area_sqm=payload.footprint_m2 * payload.floors,
        proposed_units=(payload.units_per_floor or 0) * payload.floors,
        notes=payload.material,
        status=(payload.status or "submitted"),
        geom=ST_SetSRID(ST_MakePoint(payload.lng, payload.lat), 4326),
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return _submission_to_out(submission)


@router.get("s", response_model=list[BuildingOut])
def list_buildings(db: Session = Depends(get_db)):
    submissions = db.query(Building).all()
    return [_submission_to_out(s) for s in submissions]


@router.get("s/nearby", response_model=list[BuildingOut])
def list_nearby_buildings(
    lat: float,
    lng: float,
    radius_km: float = 2.0,
    db: Session = Depends(get_db),
):
    submissions = (
        db.query(Building)
        .filter(
            ST_DWithin(
                Building.geom,
                ST_SetSRID(ST_MakePoint(lng, lat), 4326),
                radius_km * 1000,
            )
        )
        .all()
    )
    return [_submission_to_out(s) for s in submissions]


@router.get("/{building_id}", response_model=BuildingOut)
def get_building(building_id: uuid.UUID, db: Session = Depends(get_db)):
    submission = db.query(Building).filter(Building.id == building_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return _submission_to_out(submission)


@router.delete("/{building_id}", status_code=204)
def delete_building(building_id: uuid.UUID, db: Session = Depends(get_db)):
    submission = db.query(Building).filter(Building.id == building_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    result = db.query(Impact).filter(Impact.submission_id == building_id).first()
    if result:
        db.query(AnalysisModule).filter(AnalysisModule.result_id == result.id).delete()
        db.delete(result)
    db.delete(submission)
    db.commit()


@router.delete("/{building_id}/impact", status_code=204)
def clear_impact_cache(building_id: uuid.UUID, db: Session = Depends(get_db)):
    result = db.query(Impact).filter(Impact.submission_id == building_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="No cached analysis for this submission")
    db.query(AnalysisModule).filter(AnalysisModule.result_id == result.id).delete()
    db.delete(result)
    db.commit()


@router.get("/{building_id}/impact", response_model=ImpactOut)
async def get_impact(building_id: uuid.UUID, db: Session = Depends(get_db)):
    submission = db.query(Building).filter(Building.id == building_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    existing = db.query(Impact).filter(Impact.submission_id == building_id).first()
    if existing:
        return _result_row_to_schema(existing, db)

    spec = _submission_spec(submission)
    spatial = get_spatial_context(spec["lat"], spec["lng"], db)
    xgb_energy = predict_energy(spec)
    xgb_traffic = predict_traffic(spec)
    xgb_economic = predict_economic(spec)

    try:
        result = await _run_nemotron(spec, spatial)
    except Exception as e:
        print(f"[impact] NeMoTron error: {type(e).__name__}: {e}")
        result = _fallback_impact(spec)

    if xgb_energy:
        result["environmental"].update({
            "score": xgb_energy["score"],
            "description": xgb_energy["description"],
            "annual_kwh": xgb_energy.get("annual_kwh"),
            "intensity_kwh_per_m2": xgb_energy.get("intensity_kwh_per_m2"),
        })
    if xgb_traffic:
        result["traffic"].update({
            "score": xgb_traffic["score"],
            "description": xgb_traffic["description"],
            "transit_tier": xgb_traffic.get("transit_tier"),
            "daily_trips": xgb_traffic.get("daily_trips"),
            "daily_trips_base": xgb_traffic.get("daily_trips_base"),
        })
    if xgb_economic:
        result["economic"].update({
            "score": xgb_economic["score"],
            "description": xgb_economic["description"],
            "construction_jobs": xgb_economic.get("construction_jobs"),
        })

    scores = [v["score"] for v in result.values()]
    row = Impact(
        submission_id=building_id,
        overall_score=int(round(sum(scores) / len(scores))),
        est_construction_jobs=(xgb_economic or {}).get("construction_jobs"),
        est_annual_utility_cost=(xgb_energy or {}).get("annual_cost"),
        est_daily_trips_added=(xgb_traffic or {}).get("daily_trips"),
        transit_access_score=result["traffic"].get("score"),
        narrative_headline=f"{submission.project_name or 'Submission'} impact analysis",
        narrative_summary=" ".join(v["description"] for v in result.values()),
    )
    db.add(row)
    db.flush()
    for module_name, module in result.items():
        db.add(AnalysisModule(
            result_id=row.id,
            module_name=module_name,
            score=module["score"],
            summary=module["description"],
            details=module,
        ))
    db.commit()
    db.refresh(row)
    return _result_row_to_schema(row, db)


def _result_row_to_schema(row: Impact, db: Session) -> ImpactOut:
    modules = {
        m.module_name: {"score": m.score or 50, "description": m.summary or "", **(m.details or {})}
        for m in db.query(AnalysisModule).filter(AnalysisModule.result_id == row.id).all()
    }
    fallback = _fallback_impact({"floors": 10, "footprint_m2": 1000, "units_per_floor": 10})
    data = {dim: modules.get(dim, fallback[dim]) for dim in ["environmental", "traffic", "economic", "infrastructure", "housing"]}
    return ImpactOut(
        building_id=row.submission_id,
        environmental=ImpactDimension(**data["environmental"]),
        traffic=ImpactDimension(**data["traffic"]),
        economic=ImpactDimension(**data["economic"]),
        infrastructure=ImpactDimension(**data["infrastructure"]),
        housing=ImpactDimension(**data["housing"]),
    )
