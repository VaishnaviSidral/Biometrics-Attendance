"""
User model for authentication and authorization
"""
from sqlalchemy import Column, Integer, String, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
import enum
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import Base


class UserRole(str, enum.Enum):
    """User role enumeration"""
    ADMIN = "ADMIN"
    EMPLOYEE = "EMPLOYEE"


class User(Base):
    """User model for authentication"""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    employee_code = Column(String(20), ForeignKey("employees.code"), nullable=True)
    
    # Relationship to Employee (only for EMPLOYEE role users)
    employee = relationship("Employee", foreign_keys=[employee_code])
    
    def __repr__(self):
        return f"<User(username={self.username}, role={self.role})>"
