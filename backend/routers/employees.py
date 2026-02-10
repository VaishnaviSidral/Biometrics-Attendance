"""
Employees Router
Handles employee-related API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from services.auth_utils import require_admin
from models.employee import Employee
from models.user import User
from models.attendance import DailyAttendance, WeeklySummary

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("/")
async def list_employees(
    search: Optional[str] = Query(None, description="Search by name or code"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    List all employees with optional search
    """
    query = db.query(Employee)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Employee.name.ilike(search_term)) | 
            (Employee.code.ilike(search_term))
        )
    
    total = query.count()
    employees = query.offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "employees": [
            {
                "id": emp.id,
                "code": emp.code,
                "name": emp.name,
                "department": emp.department
            }
            for emp in employees
        ]
    }


@router.get("/{employee_code}")
async def get_employee(
    employee_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get single employee details
    """
    employee = db.query(Employee).filter(Employee.code == employee_code).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Get attendance stats
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
        "department": employee.department,
        "stats": {
            "total_days_recorded": daily_count,
            "total_weeks_recorded": weekly_count
        }
    }


@router.put("/{employee_code}")
async def update_employee(
    employee_code: str,
    name: Optional[str] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update employee details
    """
    employee = db.query(Employee).filter(Employee.code == employee_code).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if name:
        employee.name = name
    if department:
        employee.department = department
    
    db.commit()
    db.refresh(employee)
    
    return {
        "id": employee.id,
        "code": employee.code,
        "name": employee.name,
        "department": employee.department
    }
