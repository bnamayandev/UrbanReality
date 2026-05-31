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
    """Decode Supabase JWT and return the user UUID string, or None if no token."""
    if not credentials:
        return None
    if not SUPABASE_JWT_SECRET:
        raise HTTPException(status_code=500, detail="SUPABASE_JWT_SECRET not configured")
    try:
        payload = jwt.decode(
            credentials.credentials,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_optional_user(
    user_id: str | None = Depends(_verify_token),
    db: Session = Depends(get_db),
) -> AppUser | None:
    """Returns the AppUser for the token, or None if unauthenticated."""
    if not user_id:
        return None
    return db.query(AppUser).filter(AppUser.id == uuid.UUID(user_id)).first()


def require_org_user(user: AppUser | None = Depends(get_optional_user)) -> AppUser:
    """Raises 403 unless the caller is a logged-in org member or admin."""
    if not user or user.role not in ("org_member", "org_admin"):
        raise HTTPException(status_code=403, detail="Organization account required")
    return user


def require_auth(user: AppUser | None = Depends(get_optional_user)) -> AppUser:
    """Raises 401 unless the caller is any authenticated user."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user
