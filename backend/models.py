import uuid
from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey, DateTime, Text, BigInteger, func
from sqlalchemy.dialects.postgresql import UUID, NUMERIC
from geoalchemy2 import Geography
from database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True)
    email = Column(Text, nullable=False, unique=True)
    full_name = Column(Text, nullable=True)
    company_name = Column(Text, nullable=True)
    role = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    project_name = Column(Text, nullable=True)
    site_address = Column(Text, nullable=True)
    site_lat = Column(Float, nullable=True)
    site_lng = Column(Float, nullable=True)
    building_type = Column(Text, nullable=True)
    proposed_height_m = Column(NUMERIC, nullable=True)
    proposed_floor_area_sqm = Column(NUMERIC, nullable=True)
    proposed_units = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="submitted")
    error_message = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    geom = Column(Geography("POINT", srid=4326), nullable=True)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=False, unique=True)
    overall_score = Column(Integer, nullable=True)
    est_construction_jobs = Column(NUMERIC, nullable=True)
    est_permanent_jobs = Column(NUMERIC, nullable=True)
    est_annual_tax_revenue = Column(NUMERIC, nullable=True)
    est_annual_utility_cost = Column(NUMERIC, nullable=True)
    est_trees_removed = Column(Integer, nullable=True)
    est_annual_ghg_tons = Column(NUMERIC, nullable=True)
    est_pm25_delta = Column(NUMERIC, nullable=True)
    est_daily_trips_added = Column(NUMERIC, nullable=True)
    transit_access_score = Column(Integer, nullable=True)
    narrative_headline = Column(Text, nullable=True)
    narrative_summary = Column(Text, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class AnalysisModule(Base):
    __tablename__ = "analysis_modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id = Column(UUID(as_uuid=True), ForeignKey("analysis_results.id"), nullable=False)
    module_name = Column(Text, nullable=False)
    score = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SubmissionFile(Base):
    __tablename__ = "submission_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=False)
    storage_path = Column(Text, nullable=False)
    file_name = Column(Text, nullable=False)
    file_type = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())


# Compatibility aliases for the rest of the app's current vocabulary.
AppUser = Profile
Building = Submission
Impact = AnalysisResult
