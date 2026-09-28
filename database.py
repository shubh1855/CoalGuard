# database.py
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    DateTime, Text, ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/safesight"
)

# Only pass check_same_thread for SQLite connections
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Site(Base):
    __tablename__ = "sites"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    subsidiary = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    compliance_items = relationship("ComplianceItem", back_populates="site")
    inspections = relationship("Inspection", back_populates="site")
    violations = relationship("Violation", back_populates="site")


class ComplianceItem(Base):
    __tablename__ = "compliance_items"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"))
    category = Column(String)
    regulation = Column(String)
    description = Column(Text)
    due_date = Column(DateTime)
    status = Column(String, default="Pending")
    responsible_officer = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)
    remarks = Column(Text)

    site = relationship("Site", back_populates="compliance_items")


class Inspection(Base):
    __tablename__ = "inspections"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"))
    inspector_name = Column(String)
    inspection_type = Column(String)
    date = Column(DateTime, default=datetime.utcnow)
    latitude = Column(Float)
    longitude = Column(Float)
    observations = Column(Text)
    status = Column(String, default="Open")
    severity = Column(String, default="Low")
    image_path = Column(String)

    site = relationship("Site", back_populates="inspections")
    corrective_actions = relationship("CorrectiveAction", back_populates="inspection")


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"
    id = Column(Integer, primary_key=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id"))
    description = Column(Text)
    assigned_to = Column(String)
    deadline = Column(DateTime)
    status = Column(String, default="Pending")
    completed_at = Column(DateTime, nullable=True)

    inspection = relationship("Inspection", back_populates="corrective_actions")


class Violation(Base):
    __tablename__ = "violations"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"))
    worker_id = Column(String)
    violation_type = Column(String)
    source = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    image_path = Column(String)
    resolved = Column(Boolean, default=False)

    site = relationship("Site", back_populates="violations")


class AlertLog(Base):
    __tablename__ = "alert_log"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    alert_type = Column(String)
    message = Column(Text)
    severity = Column(String, default="Medium")
    sent_at = Column(DateTime, default=datetime.utcnow)
    channel = Column(String)


class Contractor(Base):
    __tablename__ = "contractors"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"))
    name = Column(String)
    contact = Column(String)
    license_number = Column(String)
    license_expiry = Column(DateTime)
    compliance_status = Column(String, default="Valid")


def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
