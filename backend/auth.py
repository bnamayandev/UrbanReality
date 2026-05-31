"""
Supabase JWT verification + FastAPI auth dependencies.

Supabase issues HS256 JWTs signed with the project's JWT secret.
Set SUPABASE_JWT_SECRET in backend/.env (Settings > API > JWT Secret).
"""

import os
import uuid
from dotenv import load_dotenv
from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db
from models import AppUser

load_dotenv()

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

_bearer = HTTPBearer(auto_error=False)


def _verify_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str | None:
    """Decode Supabase JWT and return the user UUID, or None if absent/invalid."""
    if not credentials or not SUPABASE_JWT_SECRET:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload.get("sub")
    except JWTError:
        # Stale/invalid token — fall through to optional/demo handling
        return None


def get_optional_user(
    user_id: str | None = Depends(_verify_token),
    db: Session = Depends(get_db),
) -> AppUser | None:
    """Returns the AppUser for the token, or None if unauthenticated."""
    if not user_id:
        return None
    return db.query(AppUser).filter(AppUser.id == uuid.UUID(user_id)).first()


DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
# Default ON so unauthenticated requests fall back to a demo user.
# Set DEMO_MODE=false in backend/.env to enforce real auth in production.
_DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() not in ("0", "false", "no", "off")


def _get_or_create_demo_user(db: Session) -> AppUser:
    user = db.query(AppUser).filter(AppUser.id == DEMO_USER_ID).first()
    if user:
        return user
    user = AppUser(
        id=DEMO_USER_ID,
        email="demo@urbanforge.local",
        full_name="Demo Builder",
        company_name="UrbanForge Demo",
        role="org_admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def require_org_user(
    user: AppUser | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> AppUser:
    """Auth-gated for org users. In demo mode, auto-provides a demo user."""
    if user and user.role in ("org_member", "org_admin"):
        return user
    if _DEMO_MODE:
        return _get_or_create_demo_user(db)
    raise HTTPException(status_code=403, detail="Organization account required")


def require_auth(
    user: AppUser | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> AppUser:
    """Auth-gated. In demo mode, auto-provides a demo user."""
    if user:
        return user
    if _DEMO_MODE:
        return _get_or_create_demo_user(db)
    raise HTTPException(status_code=401, detail="Authentication required")
