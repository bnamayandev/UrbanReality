from pydantic import BaseModel
from typing import Optional


# ── Building ──────────────────────────────────────────────────────────────────

class BuildingCreate(BaseModel):
    name: Optional[str] = None
    type: str
    material: Optional[str] = None
    floors: int
    footprint_m2: float
    units_per_floor: Optional[int] = 10
    lat: float
    lng: float
    status: Optional[str] = "Under Review"


class BuildingOut(BaseModel):
    id: int
    name: Optional[str]
    type: str
    floors: int
    footprint_m2: float
    units_per_floor: Optional[int]
    lat: float
    lng: float
    status: str

    model_config = {"from_attributes": True}


# ── Impact ────────────────────────────────────────────────────────────────────

class ImpactDimension(BaseModel):
    score: int
    description: str
    model_config = {"extra": "allow"}  # transit_tier, daily_trips, annual_kwh, etc. pass through


class ImpactOut(BaseModel):
    building_id: int
    environmental: ImpactDimension
    traffic: ImpactDimension
    economic: ImpactDimension
    infrastructure: ImpactDimension
    housing: ImpactDimension


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str
    building_id: Optional[int] = None
    session_id: Optional[int] = None
