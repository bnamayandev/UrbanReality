"""Auth — always returns a demo user (no Supabase / DB required)."""
import uuid
from models import AppUser

DEMO_USER = AppUser(
    id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    email="demo@urbanforge.local",
    full_name="Demo Builder",
    company_name="UrbanForge Demo",
    role="org_admin",
)


def get_optional_user() -> AppUser:
    return DEMO_USER


def require_auth() -> AppUser:
    return DEMO_USER


def require_org_user() -> AppUser:
    return DEMO_USER
