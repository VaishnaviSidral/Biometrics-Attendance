"""
Configuration settings for the Biometrics Attendance System
"""
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
     # -------- Biometric DB (READ/WRITE) --------
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    # -------- Redmine DB (READ ONLY) --------
    REDMINE_DB_HOST: str
    REDMINE_DB_PORT: int
    REDMINE_DB_NAME: str
    REDMINE_DB_USER: str
    REDMINE_DB_PASSWORD: str

    # -------- Google OAuth --------
    GOOGLE_ENABLED: bool
    GOOGLE_CLIENT_ID: str

    # -------- App Config --------
    EXPECTED_HOURS_PER_DAY: int = 9
    WFO_DAYS_PER_WEEK: int = 5
    HYBRID_DAYS_PER_WEEK: int = 3

    THRESHOLD_RED: int = 60
    THRESHOLD_AMBER: int = 90

    # Hour-based compliance thresholds (daily)
    COMPLIANCE_HOURS: float = 9.0        # >= 9h → Compliance
    MID_COMPLIANCE_HOURS: float = 7.0    # >= 7h → Mid-Compliance
    NON_COMPLIANCE_HOURS: float = 6.0    # >= 6h → Non-Compliance, < 6h also Non-Compliance

    API_PREFIX: str = "/api"
    DEBUG: bool = True

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # -------- Derived values --------
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def REDMINE_DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.REDMINE_DB_USER}:{self.REDMINE_DB_PASSWORD}"
            f"@{self.REDMINE_DB_HOST}:{self.REDMINE_DB_PORT}/{self.REDMINE_DB_NAME}?charset=utf8mb4"
        )

    class Config:
        env_file = ".env"


settings = Settings()


def get_status_color(percentage: float) -> str:
    """
    Get compliance status based on attendance percentage (legacy fallback)

    Per README:
        Compliance     >= 90%  → Compliance
        Mid-Compliance = 60% – 89%  → Mid-Compliance
        Non-Compliance < 60%  → Non-Compliance
    """
    if percentage >= settings.THRESHOLD_AMBER:
        return "Compliance"
    elif percentage >= settings.THRESHOLD_RED:
        return "Mid-Compliance"
    else:
        return "Non-Compliance"


def get_status_color_by_hours(total_hours: float, compliance_hours: float, mid_compliance_hours: float, non_compliance_hours: float) -> str:
    """
    Get compliance status based on total working hours (hour-based compliance).

    Rules:
        total_hours >= compliance_hours       → Compliance
        total_hours >= mid_compliance_hours    → Mid-Compliance
        total_hours >= non_compliance_hours    → Non-Compliance
        total_hours < non_compliance_hours     → Non-Compliance
    """
    if total_hours >= compliance_hours:
        return "Compliance"
    elif total_hours >= mid_compliance_hours:
        return "Mid-Compliance"
    else:
        return "Non-Compliance"
