"""
Employees Router
Handles employee-related API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging

from database import get_db
from services.auth_utils import require_admin, CurrentUser
from services.attendance_parser import AttendanceParser
from models.employee import Employee
from models.attendance import DailyAttendance, WeeklySummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/employees", tags=["employees"])


class EmployeeUpdate(BaseModel):
    """Employee update request"""
    name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    work_mode: Optional[str] = None  # WFO / HYBRID / WFH


@router.get("/")
async def list_employees(
    search: Optional[str] = Query(None, description="Search by name or code"),
    work_mode: Optional[str] = Query(None, description="Filter by work mode: WFO, HYBRID, WFH"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """List all employees with optional search and work_mode filter"""
    query = db.query(Employee)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Employee.name.ilike(search_term)) |
            (Employee.code.ilike(search_term))
        )

    if work_mode:
        query = query.filter(Employee.work_mode == work_mode.upper())

    total = query.count()
    employees = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "employees": [
            {
                "id": emp.id,
                "code": emp.code,
                "name": emp.name,
                "email": emp.email,
                "department": emp.department,
                "work_mode": emp.work_mode or "WFO"
            }
            for emp in employees
        ]
    }


@router.get("/{employee_code}")
async def get_employee(
    employee_code: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Get single employee details"""
    employee = db.query(Employee).filter(Employee.code == employee_code).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    daily_count = db.query(DailyAttendance).filter(
        DailyAttendance.employee_code == employee_code
    ).count()

    weekly_count = db.query(WeeklySummary).filter(
        WeeklySummary.employee_code == employee_code
    ).count()

    return {
        "id": employee.id,
        "code": employee.code,
        "name": employee.name,
        "email": employee.email,
        "department": employee.department,
        "work_mode": employee.work_mode or "WFO",
        "stats": {
            "total_days_recorded": daily_count,
            "total_weeks_recorded": weekly_count
        }
    }


@router.put("/{employee_code}")
async def update_employee(
    employee_code: str,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Update employee details including work_mode"""
    employee = db.query(Employee).filter(Employee.code == employee_code).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if data.name is not None:
        employee.name = data.name
    if data.email is not None:
        employee.email = data.email
    if data.department is not None:
        employee.department = data.department
    if data.work_mode is not None:
        if data.work_mode.upper() not in ('WFO', 'HYBRID', 'WFH'):
            raise HTTPException(status_code=400, detail="work_mode must be WFO, HYBRID, or WFH")
        employee.work_mode = data.work_mode.upper()

    db.commit()
    db.refresh(employee)

    return {
        "id": employee.id,
        "code": employee.code,
        "name": employee.name,
        "email": employee.email,
        "department": employee.department,
        "work_mode": employee.work_mode or "WFO"
    }