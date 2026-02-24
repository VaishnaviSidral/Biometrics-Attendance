"""
Settings Router
Handles settings API endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict
from pydantic import BaseModel

from database import get_db
from models.settings import AppSettings
from config import settings as default_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    """Request model for updating settings"""
    expected_hours_per_day: int = 9
    wfo_days_per_week: int = 5
    hybrid_days_per_week: int = 3
    threshold_red: int = 60      # Non-Compliance threshold (percentage)
    threshold_amber: int = 90    # Compliance threshold (percentage)
    compliance_hours: int = 9           # >= X hours → COMPLIANCE (GREEN)
    mid_compliance_hours: int = 7       # >= Y hours → MID-COMPLIANCE (AMBER)
    non_compliance_hours: int = 6       # >= Z hours → NON-COMPLIANCE (RED)


def get_setting_value(db: Session, key: str, default: str) -> str:
    """Get a setting value from database or return default"""
    setting = db.query(AppSettings).filter(AppSettings.key == key).first()
    return setting.value if setting else default


def set_setting_value(db: Session, key: str, value: str) -> None:
    """Set a setting value in database"""
    setting = db.query(AppSettings).filter(AppSettings.key == key).first()
    if setting:
        setting.value = value
    else:
        setting = AppSettings(key=key, value=value)
        db.add(setting)


@router.get("")
async def get_settings(db: Session = Depends(get_db)) -> Dict:
    """Get all application settings"""
    expected_hours = int(get_setting_value(
        db, AppSettings.EXPECTED_HOURS_PER_DAY,
        str(default_settings.EXPECTED_HOURS_PER_DAY)
    ))
    wfo_days = int(get_setting_value(
        db, AppSettings.WFO_DAYS_PER_WEEK,
        str(default_settings.WFO_DAYS_PER_WEEK)
    ))
    hybrid_days = int(get_setting_value(
        db, AppSettings.HYBRID_DAYS_PER_WEEK,
        str(default_settings.HYBRID_DAYS_PER_WEEK)
    ))
    threshold_red = int(get_setting_value(
        db, AppSettings.THRESHOLD_RED,
        str(default_settings.THRESHOLD_RED)
    ))
    threshold_amber = int(get_setting_value(
        db, AppSettings.THRESHOLD_AMBER,
        str(default_settings.THRESHOLD_AMBER)
    ))
    compliance_hours = int(get_setting_value(
        db, AppSettings.COMPLIANCE_HOURS,
        str(default_settings.COMPLIANCE_HOURS)
    ))
    mid_compliance_hours = int(get_setting_value(
        db, AppSettings.MID_COMPLIANCE_HOURS,
        str(default_settings.MID_COMPLIANCE_HOURS)
    ))
    non_compliance_hours = int(get_setting_value(
        db, AppSettings.NON_COMPLIANCE_HOURS,
        str(default_settings.NON_COMPLIANCE_HOURS)
    ))

    return {
        "expected_hours_per_day": expected_hours,
        "wfo_days_per_week": wfo_days,
        "hybrid_days_per_week": hybrid_days,
        "expected_weekly_minutes_wfo": wfo_days * expected_hours * 60,
        "expected_weekly_minutes_hybrid": hybrid_days * expected_hours * 60,
        "thresholds": {
            "red": threshold_red,
            "amber": threshold_amber
        },
        "compliance_hours": compliance_hours,
        "mid_compliance_hours": mid_compliance_hours,
        "non_compliance_hours": non_compliance_hours
    }


@router.put("")
async def update_settings(
    settings_data: SettingsUpdate,
    db: Session = Depends(get_db)
) -> Dict:
    """Update application settings"""
    set_setting_value(db, AppSettings.EXPECTED_HOURS_PER_DAY, str(settings_data.expected_hours_per_day))
    set_setting_value(db, AppSettings.WFO_DAYS_PER_WEEK, str(settings_data.wfo_days_per_week))
    set_setting_value(db, AppSettings.HYBRID_DAYS_PER_WEEK, str(settings_data.hybrid_days_per_week))
    set_setting_value(db, AppSettings.THRESHOLD_RED, str(settings_data.threshold_red))
    set_setting_value(db, AppSettings.THRESHOLD_AMBER, str(settings_data.threshold_amber))
    set_setting_value(db, AppSettings.COMPLIANCE_HOURS, str(settings_data.compliance_hours))
    set_setting_value(db, AppSettings.MID_COMPLIANCE_HOURS, str(settings_data.mid_compliance_hours))
    set_setting_value(db, AppSettings.NON_COMPLIANCE_HOURS, str(settings_data.non_compliance_hours))

    db.commit()

    return {
        "message": "Settings updated successfully",
        "settings": {
            "expected_hours_per_day": settings_data.expected_hours_per_day,
            "wfo_days_per_week": settings_data.wfo_days_per_week,
            "hybrid_days_per_week": settings_data.hybrid_days_per_week,
            "thresholds": {
                "red": settings_data.threshold_red,
                "amber": settings_data.threshold_amber
            },
            "compliance_hours": settings_data.compliance_hours,
            "mid_compliance_hours": settings_data.mid_compliance_hours,
            "non_compliance_hours": settings_data.non_compliance_hours
        }
    }


def get_dynamic_settings(db: Session) -> Dict:
    """
    Get settings as a dictionary for use in calculations.
    These values are used to build the dynamic WORK_MODE_CONFIG
    and drive all compliance calculations.
    """
    expected_hours = int(get_setting_value(
        db, AppSettings.EXPECTED_HOURS_PER_DAY,
        str(default_settings.EXPECTED_HOURS_PER_DAY)
    ))
    wfo_days = int(get_setting_value(
        db, AppSettings.WFO_DAYS_PER_WEEK,
        str(default_settings.WFO_DAYS_PER_WEEK)
    ))
    hybrid_days = int(get_setting_value(
        db, AppSettings.HYBRID_DAYS_PER_WEEK,
        str(default_settings.HYBRID_DAYS_PER_WEEK)
    ))
    threshold_red = int(get_setting_value(
        db, AppSettings.THRESHOLD_RED,
        str(default_settings.THRESHOLD_RED)
    ))
    threshold_amber = int(get_setting_value(
        db, AppSettings.THRESHOLD_AMBER,
        str(default_settings.THRESHOLD_AMBER)
    ))
    compliance_hours = int(get_setting_value(
        db, AppSettings.COMPLIANCE_HOURS,
        str(default_settings.COMPLIANCE_HOURS)
    ))
    mid_compliance_hours = int(get_setting_value(
        db, AppSettings.MID_COMPLIANCE_HOURS,
        str(default_settings.MID_COMPLIANCE_HOURS)
    ))
    non_compliance_hours = int(get_setting_value(
        db, AppSettings.NON_COMPLIANCE_HOURS,
        str(default_settings.NON_COMPLIANCE_HOURS)
    ))

    return {
        "expected_hours_per_day": expected_hours,
        "wfo_days_per_week": wfo_days,
        "hybrid_days_per_week": hybrid_days,
        "threshold_red": threshold_red,
        "threshold_amber": threshold_amber,
        "compliance_hours": compliance_hours,
        "mid_compliance_hours": mid_compliance_hours,
        "non_compliance_hours": non_compliance_hours
    }
