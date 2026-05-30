from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID

from database import get_db
from models import Building, Impact
from schemas import BuildingCreate, BuildingOut, ImpactOut, ImpactDimension
from spatial import get_spatial_context
from agents.impact_agent import run_impact_analysis, fallback_impact

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

    try:
        result = await run_impact_analysis(building_spec, spatial_context)
    except Exception:
        result = fallback_impact(building_spec)

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
