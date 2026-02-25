"""
Application Settings Model
Stores dynamic configuration that can be changed by admin
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from database import Base


class AppSettings(Base):
    """Dynamic application settings stored in database"""
    __tablename__ = "app_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, nullable=False, index=True)
    value = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Default settings keys
    EXPECTED_HOURS_PER_DAY = "expected_hours_per_day"
    WFO_DAYS_PER_WEEK = "wfo_days_per_week"
    HYBRID_DAYS_PER_WEEK = "hybrid_days_per_week"
    THRESHOLD_RED = "threshold_red"
    THRESHOLD_AMBER = "threshold_amber"

    # Hour-based compliance thresholds
    COMPLIANCE_HOURS = "compliance_hours"           # >= X → Compliance
    MID_COMPLIANCE_HOURS = "mid_compliance_hours"   # >= Y → Mid-Compliance
    NON_COMPLIANCE_HOURS = "non_compliance_hours"   # >= Z → Non-Compliance
