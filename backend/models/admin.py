"""
Admin model for the Biometrics Attendance System
Admins table in Biometric DB - determines admin role
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import Base


class Admin(Base):
    """Admin model - stores admin emails for role determination"""
    
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    is_admin = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<Admin(email={self.email}, is_admin={self.is_admin})>"




