"""
Holidays Model
Represents holiday records in the biometric database
"""
from sqlalchemy import Column, Integer, Date, String
from database import Base


class Holiday(Base):
    """Holiday model for storing holiday information"""
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    holiday_description = Column(String(255), nullable=False)

    def __repr__(self):
        return f"<Holiday(date={self.date}, description={self.holiday_description})>"
