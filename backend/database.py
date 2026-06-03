"""In-memory store — replaces the PostgreSQL/SQLAlchemy backend."""
import uuid

# ── Stores ────────────────────────────────────────────────────────────────────
_users: dict[str, object] = {}          # str(uuid) → AppUser
_buildings: dict[str, object] = {}      # str(uuid) → Building
_impacts: dict[str, object] = {}        # str(submission_uuid) → Impact
_impact_modules: dict[str, list] = {}   # str(result_uuid) → [AnalysisModule]
