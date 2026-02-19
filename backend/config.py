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
    Get status color based on attendance percentage

    Per README:
        Compliance     >= 90%  → GREEN
        Mid-Compliance = 60% – 89%  → AMBER
        Non-Compliance < 60%  → RED
    """
    if percentage >= settings.THRESHOLD_AMBER:
        return "GREEN"
    elif percentage >= settings.THRESHOLD_RED:
        return "AMBER"
    else:
        return "RED"
