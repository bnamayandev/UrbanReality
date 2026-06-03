import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AppUser:
    id: uuid.UUID
    email: str
    role: str = "org_admin"
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    avatar_url: Optional[str] = None


@dataclass
class Building:
    id: uuid.UUID
    user_id: uuid.UUID
    project_name: Optional[str] = None
    site_lat: Optional[float] = None
    site_lng: Optional[float] = None
    building_type: Optional[str] = None
    proposed_height_m: Optional[float] = None
    proposed_floor_area_sqm: Optional[float] = None
    proposed_units: Optional[int] = None
    notes: Optional[str] = None
    status: str = "submitted"
    error_message: Optional[str] = None


@dataclass
class Impact:
    id: uuid.UUID
    submission_id: uuid.UUID
    overall_score: Optional[int] = None
    est_construction_jobs: Optional[float] = None
    est_annual_utility_cost: Optional[float] = None
    est_daily_trips_added: Optional[float] = None
    transit_access_score: Optional[int] = None
    narrative_headline: Optional[str] = None
    narrative_summary: Optional[str] = None


@dataclass
class AnalysisModule:
    id: uuid.UUID
    result_id: uuid.UUID
    module_name: str
    score: Optional[int] = None
    summary: Optional[str] = None
    details: Optional[dict] = None


# Aliases used elsewhere
Submission = Building
AnalysisResult = Impact
