"""
Attendance models for the Biometrics Attendance System
"""
from sqlalchemy import Column, Integer, String, Date, Time, DateTime, ForeignKey, Enum, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import Base


class AttendanceStatus(str, enum.Enum):
    """Status for daily attendance"""
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
class ComplianceStatus(str, enum.Enum):
    """Status for compliance"""
    NON_COMPLIANCE = "Non-Compliance"
    MID_COMPLIANCE = "Mid-Compliance"
    COMPLIANCE = "Compliance"


class AttendanceLog(Base):
    """Raw attendance log from biometric device"""
    
    __tablename__ = "attendance_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(20), ForeignKey("employees.code"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    in_time = Column(Time, nullable=True)
    out_time = Column(Time, nullable=True)
    total_time = Column(Time, nullable=True)
    shift = Column(Integer, nullable=True)
    late_minutes = Column(Integer, default=0)
    overtime_minutes = Column(Integer, default=0)
    remark = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    employee = relationship("Employee", back_populates="attendance_logs")
    
    def __repr__(self):
        return f"<AttendanceLog(employee={self.employee_code}, date={self.date}, in={self.in_time}, out={self.out_time})>"


class DailyAttendance(Base):
    """Daily attendance summary per employee"""
    
    __tablename__ = "daily_attendance"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(20), ForeignKey("employees.code"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    total_office_minutes = Column(Integer, default=0)
    status = Column(Enum(AttendanceStatus), nullable=False, default=AttendanceStatus.ABSENT)
    compliance_status = Column(Enum(ComplianceStatus), nullable=True, default=None)
    in_out_pairs = Column(Text, nullable=True)  # JSON string of IN/OUT pairs
    first_in = Column(Time, nullable=True)
    last_out = Column(Time, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    employee = relationship("Employee", back_populates="daily_summaries")
    
    # Unique constraint on employee_code and date
    __table_args__ = (
        # UniqueConstraint handled by unique index
    )
    
    def __repr__(self):
        return f"<DailyAttendance(employee={self.employee_code}, date={self.date}, minutes={self.total_office_minutes})>"


class WeeklySummary(Base):
    """Weekly attendance summary per employee"""
    
    __tablename__ = "weekly_summary"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(20), ForeignKey("employees.code"), nullable=False, index=True)
    week_start = Column(Date, nullable=False, index=True)
    week_end = Column(Date, nullable=False)
    total_office_minutes = Column(Integer, default=0)
    wfo_days = Column(Integer, default=0)
    expected_minutes = Column(Integer, default=2700)  # WFO: 5 days * 9 hours * 60 mins = 2700
    compliance_percentage = Column(Float, default=0.0)
    status = Column(Enum(ComplianceStatus), nullable=False, default=ComplianceStatus.NON_COMPLIANCE)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    employee = relationship("Employee", back_populates="weekly_summaries")
    
    def __repr__(self):
        return f"<WeeklySummary(employee={self.employee_code}, week={self.week_start}, compliance={self.compliance_percentage}%)>"
