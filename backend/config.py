"""
Configuration settings for the Biometrics Attendance System
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings with defaults for hybrid work policy"""
    
    # Database (MySQL)
    DATABASE_URL: str = "mysql+pymysql://attendance_user:attendance_pass@localhost:3306/attendance_db"
    
    # Work Policy Configuration
    EXPECTED_HOURS_PER_DAY: int = 8  # Expected office hours per WFO day
    WFO_DAYS_PER_WEEK: int = 3  # Work From Office days per week
    WFH_DAYS_PER_WEEK: int = 2  # Work From Home days per week
    
    # Expected weekly office hours (WFO days * hours per day)
    @property
    def expected_weekly_minutes(self) -> int:
        return self.WFO_DAYS_PER_WEEK * self.EXPECTED_HOURS_PER_DAY * 60
    
    # Color Thresholds (percentage)
    THRESHOLD_RED: int = 70  # Below this is RED
    THRESHOLD_AMBER: int = 90  # Below this is AMBER, above is GREEN
    
    # API Settings
    API_PREFIX: str = "/api"
    DEBUG: bool = True
    
    # Authentication Settings
    SECRET_KEY: str = "your-secret-key-change-in-production-biometrics-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # Default Credentials (change in production)
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"
    DEFAULT_EMPLOYEE_PASSWORD: str = "employee123"
    
    class Config:
        env_file = ".env"


settings = Settings()


def get_status_color(percentage: float) -> str:
    """
    Get status color based on attendance percentage
    
    Args:
        percentage: Attendance compliance percentage (0-100)
    
    Returns:
        Status color string: "RED", "AMBER", or "GREEN"
    """
    if percentage < settings.THRESHOLD_RED:
        return "RED"
    elif percentage <= settings.THRESHOLD_AMBER:
        return "AMBER"
    else:
        return "GREEN"
