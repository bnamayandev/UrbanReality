from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID

from database import get_db
from models import Building, Impact
from schemas import BuildingCreate, BuildingOut, ImpactOut, ImpactDimension
from spatial import get_spatial_context
from agents.impact_agent import run_impact_analysis, fallback_impact
from xgb_models import predict_energy, predict_traffic, predict_economic

router = APIRouter(prefix="/building", tags=["buildings"])


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


@router.get("/{building_id}/impact", response_model=ImpactOut)
async def get_impact(building_id: int, db: Session = Depends(get_db)):
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")

    # Return cached impact if it exists
    existing = db.query(Impact).filter(Impact.building_id == building_id).first()
    if existing:
        return _impact_row_to_schema(existing)

    # Run fresh analysis
    building_spec = {
        "type": building.type,
        "material": building.material,
        "floors": building.floors,
        "footprint_m2": building.footprint_m2,
        "units_per_floor": building.units_per_floor,
        "lat": building.lat,
        "lng": building.lng,
    }
    spatial_context = get_spatial_context(building.lat, building.lng, db)

    # --- XGBoost predictions (fast, local, no GPU needed) ---
    xgb_energy   = predict_energy(building_spec)
    xgb_traffic  = predict_traffic(building_spec)
    xgb_economic = predict_economic(building_spec)

    # --- NeMoTron for richer narrative + dimensions XGB doesn't cover ---
    try:
        result = await run_impact_analysis(building_spec, spatial_context)
        # Blend: XGBoost scores override NeMoTron where available (more reliable)
        if xgb_energy:
            result["environmental"]["score"] = xgb_energy["score"]
            result["environmental"]["description"] += f" | XGB: {xgb_energy['description']}"
        if xgb_traffic:
            result["traffic"]["score"] = xgb_traffic["score"]
            result["traffic"]["description"] += f" | XGB: {xgb_traffic['description']}"
        if xgb_economic:
            result["economic"]["score"] = xgb_economic["score"]
            result["economic"]["description"] += f" | XGB: {xgb_economic['description']}"
    except Exception:
        # NeMoTron unavailable — build result entirely from XGB + rule-based fallback
        fallback = fallback_impact(building_spec)
        result = {
            "environmental": {
                "score": xgb_energy["score"] if xgb_energy else fallback["environmental"]["score"],
                "description": (xgb_energy["description"] if xgb_energy
                                else fallback["environmental"]["description"]),
            },
            "traffic": {
                "score": xgb_traffic["score"] if xgb_traffic else fallback["traffic"]["score"],
                "description": (xgb_traffic["description"] if xgb_traffic
                                else fallback["traffic"]["description"]),
            },
            "economic": {
                "score": xgb_economic["score"] if xgb_economic else fallback["economic"]["score"],
                "description": (xgb_economic["description"] if xgb_economic
                                else fallback["economic"]["description"]),
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
