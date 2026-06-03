import uuid
from fastapi import APIRouter, Depends

from database import _users
from models import AppUser
from schemas import UserOut, UserRegister, BuildingOut
from auth import require_auth, require_org_user
from database import _buildings

router = APIRouter(tags=["accounts"])


@router.post("/auth/register", response_model=UserOut, status_code=201)
def register_user(payload: UserRegister):
    uid = uuid.UUID(payload.id)
    user = _users.get(str(uid))
    if not user:
        role = payload.role if payload.role in ("org_member", "org_admin") else "public"
        user = AppUser(
            id=uid,
            email=payload.email,
            role=role,
            full_name=payload.full_name,
            company_name=payload.org_name,
            avatar_url=payload.avatar_url,
        )
        _users[str(uid)] = user
    return _user_to_out(user)


@router.get("/auth/me", response_model=UserOut)
def get_me(current_user: AppUser = Depends(require_auth)):
    return _user_to_out(current_user)


@router.get("/organizations/me/buildings", response_model=list[BuildingOut])
def get_org_buildings(current_user: AppUser = Depends(require_org_user)):
    buildings = [
        b for b in _buildings.values()
        if b.user_id == current_user.id
    ]
    return [_building_to_out(b) for b in buildings]


def _user_to_out(user: AppUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "org_id": None,
        "org_name": user.company_name,
        "company_name": user.company_name,
        "full_name": user.full_name,
    }


def _building_to_out(b) -> dict:
    floors = max(1, int(round(float(b.proposed_height_m or 3.5) / 3.5)))
    footprint_m2 = float(b.proposed_floor_area_sqm or 0) / floors if b.proposed_floor_area_sqm else 0.0
    return {
        "id": b.id,
        "name": b.project_name,
        "type": b.building_type or "unknown",
        "floors": floors,
        "footprint_m2": footprint_m2,
        "units_per_floor": b.proposed_units,
        "lat": b.site_lat,
        "lng": b.site_lng,
        "status": b.status,
        "org_id": None,
        "org_name": None,
    }
