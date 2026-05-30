import os
import re
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from openai import AsyncOpenAI
from dotenv import load_dotenv

from database import get_db
from models import Building, Impact
from schemas import BuildingCreate, BuildingOut, ImpactOut, ImpactDimension
from spatial import get_spatial_context
from xgb_models import predict_energy, predict_traffic, predict_economic

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
    """Call NeMoTron with building spec + spatial context. Raises on failure."""
    traffic = spatial.get("traffic_intersections", [])
    trees   = spatial.get("street_trees", [])
    stops   = spatial.get("ttc_stops", [])
    bizs    = spatial.get("businesses", [])
    parks   = spatial.get("parks", [])
    zoning  = spatial.get("zoning", [])
    zh      = spatial.get("zoning_height")
    hood    = spatial.get("neighbourhood")

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
Transit: {len(stops)} TTC stops within 500m — {json.dumps(stops[:3])}
Trees: {len(trees)} within 500m — species: {[t.get('common_name') for t in trees[:5]]}
Parks: {json.dumps(parks[:2])}
Businesses: {len(bizs)} active ({list(set(b.get('Category','') for b in bizs[:20] if b.get('Category')))})
Produce the JSON impact assessment."""

    resp = await _get_client().chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": _IMPACT_SYSTEM},
            {"role": "user",   "content": prompt},
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

    # Extract JSON — handle markdown fences or leading prose
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
    """Clamp scores to [0, 100] and trim descriptions so validation passes."""
    DIMS = ["environmental", "traffic", "economic", "infrastructure", "housing"]
    result = {}
    for dim in DIMS:
        d = data.get(dim, {})
        try:
            score = max(0, min(100, int(float(d.get("score", 50)))))
        except (TypeError, ValueError):
            score = 50
        desc = str(d.get("description", "")).strip()[:900]
        if not desc:
            desc = f"Impact analysis for {dim} dimension."
        result[dim] = {"score": score, "description": desc}
    return result


def _fallback_impact(building: dict) -> dict:
    """Rule-based fallback when NeMoTron is offline."""
    floors = building.get("floors", 20)
    fp     = building.get("footprint_m2", 2000)
    units  = building.get("units_per_floor", 10)
    total  = floors * units
    return {
        "environmental": {
            "score": min(90, int(fp / 100)),
            "description": f"Estimated {int(fp / 10)} trees displaced. Shadow cast across ~{int(fp * floors * 0.0003):.0f}k m².",
        },
        "traffic": {
            "score": min(90, floors * 2),
            "description": f"Estimated +{floors * 14} daily vehicle trips to nearby intersections.",
        },
        "economic": {
            "score": min(95, 50 + floors),
            "description": f"~{total} new residents add ~${total * 3200 // 1000}K/yr to local retail. Property values +4–9% over 5 years.",
        },
        "infrastructure": {
            "score": min(85, floors * 2),
            "description": f"Water demand: +{total * 220} L/day. TTC boardings: +{floors * 3}/day.",
        },
        "housing": {
            "score": max(10, 80 - floors),
            "description": f"Adds {total} units against 0.7% vacancy rate. Addresses ~{int(total * 0.8)} units of unmet demand.",
        },
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=BuildingOut, status_code=201)
def create_building(payload: BuildingCreate, db: Session = Depends(get_db)):
    building = Building(
        **payload.model_dump(),
        geom=ST_SetSRID(ST_MakePoint(payload.lng, payload.lat), 4326),
    )
    db.add(building)
    db.commit()
    db.refresh(building)
    return building


@router.get("s", response_model=list[BuildingOut])
def list_buildings(db: Session = Depends(get_db)):
    return db.query(Building).all()


@router.get("/{building_id}", response_model=BuildingOut)
def get_building(building_id: int, db: Session = Depends(get_db)):
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")
    return building


@router.delete("/{building_id}", status_code=204)
def delete_building(building_id: int, db: Session = Depends(get_db)):
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")
    db.query(Impact).filter(Impact.building_id == building_id).delete()
    db.delete(building)
    db.commit()


@router.delete("/{building_id}/impact", status_code=204)
def clear_impact_cache(building_id: int, db: Session = Depends(get_db)):
    """Force a fresh NeMoTron analysis on next GET /impact."""
    deleted = db.query(Impact).filter(Impact.building_id == building_id).delete()
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="No cached impact for this building")


@router.get("/{building_id}/impact", response_model=ImpactOut)
async def get_impact(building_id: int, db: Session = Depends(get_db)):
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")

    existing = db.query(Impact).filter(Impact.building_id == building_id).first()
    if existing:
        return _impact_row_to_schema(existing)

    spec = {
        "type": building.type, "material": building.material,
        "floors": building.floors, "footprint_m2": building.footprint_m2,
        "units_per_floor": building.units_per_floor,
        "lat": building.lat, "lng": building.lng,
    }
    spatial = get_spatial_context(building.lat, building.lng, db)

    xgb_energy   = predict_energy(spec)
    xgb_traffic  = predict_traffic(spec)
    xgb_economic = predict_economic(spec)

    try:
        result = await _run_nemotron(spec, spatial)
        # XGBoost scores are more reliable — override NeMoTron where available.
        if xgb_energy:
            result["environmental"]["score"]             = xgb_energy["score"]
            result["environmental"]["description"]       = xgb_energy["description"]
            result["environmental"]["annual_kwh"]        = xgb_energy.get("annual_kwh")
            result["environmental"]["intensity_kwh_per_m2"] = xgb_energy.get("intensity_kwh_per_m2")
        if xgb_traffic:
            result["traffic"]["score"]            = xgb_traffic["score"]
            result["traffic"]["description"]      = xgb_traffic["description"]
            result["traffic"]["transit_tier"]     = xgb_traffic.get("transit_tier")
            result["traffic"]["daily_trips"]      = xgb_traffic.get("daily_trips")
            result["traffic"]["daily_trips_base"] = xgb_traffic.get("daily_trips_base")
        if xgb_economic:
            result["economic"]["score"]             = xgb_economic["score"]
            result["economic"]["description"]       = xgb_economic["description"]
            result["economic"]["construction_jobs"] = xgb_economic.get("construction_jobs")
    except Exception as e:
        print(f"[impact] NeMoTron error: {type(e).__name__}: {e}")
        fallback = _fallback_impact(spec)
        result = {
            "environmental": {
                "score": xgb_energy["score"] if xgb_energy else fallback["environmental"]["score"],
                "description": xgb_energy["description"] if xgb_energy else fallback["environmental"]["description"],
            },
            "traffic": {
                "score":            xgb_traffic["score"]       if xgb_traffic else fallback["traffic"]["score"],
                "description":      xgb_traffic["description"] if xgb_traffic else fallback["traffic"]["description"],
                "transit_tier":     xgb_traffic.get("transit_tier")     if xgb_traffic else None,
                "daily_trips":      xgb_traffic.get("daily_trips")      if xgb_traffic else None,
                "daily_trips_base": xgb_traffic.get("daily_trips_base") if xgb_traffic else None,
            },
            "economic": {
                "score":             xgb_economic["score"]       if xgb_economic else fallback["economic"]["score"],
                "description":       xgb_economic["description"] if xgb_economic else fallback["economic"]["description"],
                "construction_jobs": xgb_economic.get("construction_jobs") if xgb_economic else None,
            },
            "infrastructure": fallback["infrastructure"],
            "housing":        fallback["housing"],
        }

    impact = Impact(
        building_id=building_id,
        environmental_score=result["environmental"]["score"],
        traffic_score=result["traffic"]["score"],
        economic_score=result["economic"]["score"],
        infrastructure_score=result["infrastructure"]["score"],
        housing_score=result["housing"]["score"],
        summary_json=result,
    )
    db.add(impact)
    db.commit()
    db.refresh(impact)
    return _impact_row_to_schema(impact)


def _impact_row_to_schema(row: Impact) -> ImpactOut:
    data = row.summary_json
    return ImpactOut(
        building_id=row.building_id,
        environmental=ImpactDimension(**data["environmental"]),
        traffic=ImpactDimension(**data["traffic"]),
        economic=ImpactDimension(**data["economic"]),
        infrastructure=ImpactDimension(**data["infrastructure"]),
        housing=ImpactDimension(**data["housing"]),
    )
