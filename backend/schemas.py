from pydantic import BaseModel
from typing import Optional
import uuid


# ── Organization ──────────────────────────────────────────────────────────────

class OrgOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


# ── User ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    id: str                       # Supabase auth UID (UUID string)
    email: str
    role: str = "public"          # "public" | "org_member" | "org_admin"
    org_name: Optional[str] = None  # stored as company_name in Supabase profiles
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    org_id: Optional[uuid.UUID] = None
    org_name: Optional[str] = None
    full_name: Optional[str] = None
    company_name: Optional[str] = None

    model_config = {"from_attributes": True}


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
    id: uuid.UUID
    name: Optional[str]
    type: str
    floors: int
    footprint_m2: float
    units_per_floor: Optional[int]
    lat: float
    lng: float
    status: str
    org_id: Optional[uuid.UUID] = None
    org_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Impact ────────────────────────────────────────────────────────────────────

class ImpactDimension(BaseModel):
    score: int
    description: str
    model_config = {"extra": "allow"}  # transit_tier, daily_trips, annual_kwh, etc. pass through


class ImpactOut(BaseModel):
    building_id: uuid.UUID
    environmental: ImpactDimension
    traffic: ImpactDimension
    economic: ImpactDimension
    infrastructure: ImpactDimension
    housing: ImpactDimension


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str
    building_id: Optional[uuid.UUID] = None
    session_id: Optional[str] = None
