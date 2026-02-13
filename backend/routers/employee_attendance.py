"""
Employee Attendance Router
Handles employee-specific attendance data access
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import extract
from typing import Optional
from datetime import date, datetime, time
from pydantic import BaseModel

from database import get_db
from services.auth_utils import get_current_user, CurrentUser
from models.attendance import DailyAttendance
from models.employee import Employee


router = APIRouter(prefix="/employee", tags=["employee"])


class AttendanceRecord(BaseModel):
    """Single attendance record"""
    date: str
    first_in: Optional[str]
    last_out: Optional[str]
    total_hours: str
    total_minutes: int
    day: str


class EmployeeAttendanceResponse(BaseModel):
    """Employee attendance response"""
    employee_name: str
    employee_code: str
    work_mode: str
    month: int
    year: int
    monthly_total_hours: str
    monthly_total_minutes: int
    records: list[AttendanceRecord]


def format_time(t: Optional[time]) -> Optional[str]:
    """Format time object to string"""
    if t is None:
        return None
    return t.strftime("%I:%M %p")


def format_minutes_to_hours(minutes: int) -> str:
    """Convert minutes to 'Xh Ym' format"""
    if minutes == 0:
        return "0h 0m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins:02d}m"


@router.get("/attendance", response_model=EmployeeAttendanceResponse)
async def get_employee_attendance(
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    year: Optional[int] = Query(None, ge=2000, le=2100, description="Year"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get attendance records for the logged-in employee.
    Optionally filter by month and year.
    """
    # Admin should use individual report endpoints
    if current_user.role == "ADMIN":
        raise HTTPException(
            status_code=400,
            detail="Admin users should access individual employee reports directly"
        )

    # Get employee code from user's JWT
    employee_code = current_user.employee_code

    if not employee_code:
        # Try to find employee by email
        employee = db.query(Employee).filter(Employee.email == current_user.email).first()
        if employee:
            employee_code = employee.code
        else:
            raise HTTPException(
                status_code=404,
                detail="No employee record associated with this user"
            )
    
    # Get employee info
    employee = db.query(Employee).filter(Employee.code == employee_code).first()
    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    # Build query
    query = db.query(DailyAttendance).filter(
        DailyAttendance.employee_code == employee_code
    )

    if month and year:
        query = query.filter(
            extract('month', DailyAttendance.date) == month,
            extract('year', DailyAttendance.date) == year
        )
    elif month:
        current_year = datetime.now().year
        query = query.filter(
            extract('month', DailyAttendance.date) == month,
            extract('year', DailyAttendance.date) == current_year
        )
    elif year:
        query = query.filter(
            extract('year', DailyAttendance.date) == year
        )

    query = query.order_by(DailyAttendance.date.desc())

    attendance_records = query.all()

    monthly_total_minutes = sum(record.total_office_minutes or 0 for record in attendance_records)

    formatted_records = []
    for record in attendance_records:
        formatted_records.append(AttendanceRecord(
            date=record.date.strftime("%Y-%m-%d"),
            first_in=format_time(record.first_in),
            last_out=format_time(record.last_out),
            total_hours=format_minutes_to_hours(record.total_office_minutes or 0),
            total_minutes=record.total_office_minutes or 0,
            day=record.date.strftime("%A")
        ))

    response_month = month or datetime.now().month
    response_year = year or datetime.now().year

    return EmployeeAttendanceResponse(
        employee_name=employee.name,
        employee_code=employee.code,
        work_mode=employee.work_mode or 'WFO',
        month=response_month,
        year=response_year,
        monthly_total_hours=format_minutes_to_hours(monthly_total_minutes),
        monthly_total_minutes=monthly_total_minutes,
        records=formatted_records
    )
