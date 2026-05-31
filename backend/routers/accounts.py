"""
Account management endpoints.

Supabase handles login/signup on the client. The backend stores the matching
application profile in the public.profiles table from the Supabase schema.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import AppUser, Building
from schemas import UserOut, UserRegister, BuildingOut
from auth import require_auth, require_org_user

router = APIRouter(tags=["accounts"])


@router.post("/auth/register", response_model=UserOut, status_code=201)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    """Create or return the profile row for a Supabase auth user."""
    if payload.role in ("org_member", "org_admin"):
        if not payload.org_name:
            raise HTTPException(status_code=422, detail="org_name is required for organization accounts")
        role = "org_admin" if payload.role == "org_admin" else "org_member"
    else:
        role = "public"

    existing = db.query(AppUser).filter(AppUser.id == uuid.UUID(payload.id)).first()
    if not existing:
        existing = db.query(AppUser).filter(AppUser.email == payload.email).first()
    if existing:
        existing.email = payload.email
        existing.role = role
        existing.company_name = payload.org_name
        existing.full_name = payload.full_name or existing.full_name
        existing.avatar_url = payload.avatar_url or existing.avatar_url
        db.commit()
        db.refresh(existing)
        return _user_to_out(existing)

    user = AppUser(
        id=uuid.UUID(payload.id),
        email=payload.email,
        role=role,
        company_name=payload.org_name,
        full_name=payload.full_name,
        avatar_url=payload.avatar_url,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_to_out(user)


@router.get("/auth/me", response_model=UserOut)
def get_me(current_user: AppUser = Depends(require_auth)):
    """Return the authenticated user's Supabase profile."""
    return _user_to_out(current_user)


@router.get("/organizations/me/buildings", response_model=list[BuildingOut])
def get_org_buildings(
    current_user: AppUser = Depends(require_org_user),
    db: Session = Depends(get_db),
):
    """Return submissions created by users from the same company."""
    if not current_user.company_name:
        return []
    company_user_ids = [
        row.id for row in db.query(AppUser.id).filter(AppUser.company_name == current_user.company_name).all()
    ]
    submissions = db.query(Building).filter(Building.user_id.in_(company_user_ids)).all()
    return [_submission_to_building_out(s) for s in submissions]


def _user_to_out(user: AppUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role or "public",
        "org_id": None,
        "org_name": user.company_name,
        "company_name": user.company_name,
        "full_name": user.full_name,
    }


def _submission_to_building_out(s: Building) -> dict:
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
