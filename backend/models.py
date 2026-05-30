from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey, DateTime, func
from geoalchemy2 import Geometry
from database import Base


class Building(Base):
    __tablename__ = "buildings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    type = Column(String, nullable=False)           # e.g. "Residential (High-rise)"
    material = Column(String, nullable=True)
    floors = Column(Integer, nullable=False)
    footprint_m2 = Column(Float, nullable=False)
    units_per_floor = Column(Integer, nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    geom = Column(Geometry("POINT", srid=4326))
    status = Column(String, default="Under Review")
    created_at = Column(DateTime, server_default=func.now())


class Impact(Base):
    __tablename__ = "impacts"

    id = Column(Integer, primary_key=True, index=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False, unique=True)
    environmental_score = Column(Integer)
    traffic_score = Column(Integer)
    economic_score = Column(Integer)
    infrastructure_score = Column(Integer)
    housing_score = Column(Integer)
    summary_json = Column(JSON)     # full structured response from NeMoTron
    created_at = Column(DateTime, server_default=func.now())


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    messages_json = Column(JSON, default=list)
    created_at = Column(DateTime, server_default=func.now())
