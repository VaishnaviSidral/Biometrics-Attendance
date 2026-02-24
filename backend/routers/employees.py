"""
Employees Router
Handles employee-related API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging
from sqlalchemy import text
from database import get_db, get_redmine_db
from services.auth_utils import require_admin, CurrentUser
from services.attendance_parser import AttendanceParser
from models.employee import Employee
from models.attendance import DailyAttendance, WeeklySummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/employees", tags=["employees"])


class EmployeeCreate(BaseModel):
    """Employee create request"""
    code: str
    name: str
    email: Optional[str] = None
    department: Optional[str] = None
    work_mode: str = "WFO"  # WFO / HYBRID / WFH / CLIENT_OFFICE
    status: int = 1


class EmployeeUpdate(BaseModel):
    """Employee update request"""
    name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    work_mode: Optional[str] = None  # WFO / HYBRID / WFH / CLIENT_OFFICE
    status: Optional[int] = None


@router.get("/")
async def list_employees(
    search: Optional[str] = Query(None, description="Search by name or code"),
    work_mode: Optional[str] = Query(None, description="Filter by work mode: WFO, HYBRID, WFH, CLIENT_OFFICE"),
    include_inactive: bool = Query(False, description="Include inactive employees (status=0)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """List all employees with optional search and work_mode filter"""
    query = db.query(Employee)

    if not include_inactive:
        query = query.filter(Employee.status == 1)

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
                "work_mode": emp.work_mode or "WFO",
                "status": emp.status if emp.status is not None else 1
            }
            for emp in employees
        ]
    }


@router.post("/")
async def create_employee(
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Create a new employee"""
    # Check if employee code already exists
    existing = db.query(Employee).filter(Employee.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Employee with code '{data.code}' already exists")

    # Validate work_mode
    valid_modes = ('WFO', 'HYBRID', 'WFH', 'CLIENT_OFFICE')
    if data.work_mode.upper() not in valid_modes:
        raise HTTPException(status_code=400, detail=f"work_mode must be one of: {', '.join(valid_modes)}")

    employee = Employee(
        code=data.code,
        name=data.name,
        email=data.email,
        department=data.department,
        work_mode=data.work_mode.upper(),
        status=data.status
    )

    db.add(employee)
    db.commit()
    db.refresh(employee)

    return {
        "id": employee.id,
        "code": employee.code,
        "name": employee.name,
        "email": employee.email,
        "department": employee.department,
        "work_mode": employee.work_mode or "WFO",
        "status": employee.status if employee.status is not None else 1
    }


# ============================================================
# BU Head endpoints — Redmine integration (READ ONLY)
# IMPORTANT: These must be defined BEFORE /{employee_code}
# to avoid the path parameter from capturing these routes.
# ============================================================

@router.get("/bu-heads/list")
async def get_bu_heads(
    redmine_db: Session = Depends(get_redmine_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """
    Fetch distinct BU Head names from Redmine.

    Source: custom_values table
        custom_field_id = 71
        customized_type = 'Project'
    Only active projects (projects.status = 1).
    """
    try:
        rows = redmine_db.execute(
            text("""
                SELECT DISTINCT cv.value
                FROM custom_values cv
                JOIN projects p ON p.id = cv.customized_id
                WHERE cv.custom_field_id = 71
                  AND cv.customized_type = 'Project'
                  AND p.status = 1
                  AND cv.value IS NOT NULL
                  AND cv.value != ''
                ORDER BY cv.value
            """)
        ).fetchall()

        return [row[0] for row in rows]
    except Exception as ex:
        logger.error(f"Error fetching BU heads from Redmine: {ex}")
        raise HTTPException(status_code=500, detail="Failed to fetch BU heads from Redmine")


@router.get("/with-project-bu")
async def get_employees_with_project_bu(
    db: Session = Depends(get_db),
    redmine_db: Session = Depends(get_redmine_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """
    Return employee → project → BU Head mapping.

    Data flow:
        biometric.employees.email
        → redmine.email_addresses.address
        → redmine.users.id
        → redmine.members.user_id → members.project_id
        → redmine.projects.id
        → redmine.custom_values (field 71) → BU Head name
    """
    try:
        # 1) Get all active biometric employees that have an email
        employees = db.query(Employee).filter(Employee.email.isnot(None), Employee.email != '', Employee.status == 1).all()

        if not employees:
            return []

        email_list = [emp.email for emp in employees]

        # 2) Build a mapping from Redmine in one query
        #    For each email → user → member → project → custom_value (BU Head)
        placeholders = ', '.join([f':e{i}' for i in range(len(email_list))])
        params = {f'e{i}': email for i, email in enumerate(email_list)}

        rows = redmine_db.execute(
            text(f"""
                SELECT
                    ea.address   AS email,
                    p.id         AS project_id,
                    p.name       AS project_name,
                    COALESCE(cv.value, 'N/A') AS bu_head
                FROM email_addresses ea
                JOIN users u        ON u.id = ea.user_id
                JOIN members m      ON m.user_id = u.id
                JOIN projects p     ON p.id = m.project_id
                LEFT JOIN custom_values cv
                    ON cv.customized_id   = p.id
                   AND cv.customized_type = 'Project'
                   AND cv.custom_field_id = 71
                WHERE ea.address IN ({placeholders})
                  AND p.status = 1
                ORDER BY ea.address, p.name
            """),
            params
        ).fetchall()

        # 3) Build a lookup: email → list of { project_id, project_name, bu_head }
        email_project_map = {}
        for row in rows:
            email = row[0]
            if email not in email_project_map:
                email_project_map[email] = []
            email_project_map[email].append({
                "project_id": row[1],
                "project_name": row[2],
                "bu_head": row[3]
            })

        # 4) Combine biometric employees with Redmine project info
        results = []
        for emp in employees:
            projects = email_project_map.get(emp.email, [])
            if projects:
                for proj in projects:
                    results.append({
                        "employee_code": emp.code,
                        "employee_name": emp.name,
                        "email": emp.email,
                        "project_id": proj["project_id"],
                        "project_name": proj["project_name"],
                        "bu_head": proj["bu_head"]
                    })
            else:
                # Employee exists in biometric DB but has no Redmine project mapping
                results.append({
                    "employee_code": emp.code,
                    "employee_name": emp.name,
                    "email": emp.email,
                    "project_id": None,
                    "project_name": None,
                    "bu_head": "N/A"
                })

        return results
    except Exception as ex:
        logger.error(f"Error fetching employee-project-BU mapping: {ex}")
        raise HTTPException(status_code=500, detail="Failed to fetch employee-project-BU mapping")


@router.get("/by-bu-head")
async def get_employees_by_bu_head(
    bu_head: str = Query(..., description="BU Head name to filter by"),
    db: Session = Depends(get_db),
    redmine_db: Session = Depends(get_redmine_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """
    Filter employees by BU Head name.

    Resolves employee → project → BU Head via email mapping,
    then returns only employees whose project BU Head matches.
    """
    try:
        # 1) Get employee emails that belong to projects with this BU Head
        rows = redmine_db.execute(
            text("""
                SELECT DISTINCT ea.address AS email
                FROM custom_values cv
                JOIN projects p        ON p.id = cv.customized_id
                JOIN members m         ON m.project_id = p.id
                JOIN users u           ON u.id = m.user_id
                JOIN email_addresses ea ON ea.user_id = u.id
                WHERE cv.custom_field_id = 71
                  AND cv.customized_type = 'Project'
                  AND cv.value = :bu_head
                  AND p.status = 1
            """),
            {"bu_head": bu_head}
        ).fetchall()

        matched_emails = [row[0] for row in rows]

        if not matched_emails:
            return []

        # 2) Find active biometric employees with those emails
        employees = db.query(Employee).filter(Employee.email.in_(matched_emails), Employee.status == 1).all()

        return [
            {
                "employee_code": emp.code,
                "employee_name": emp.name,
                "email": emp.email,
                "work_mode": emp.work_mode or "WFO",
                "bu_head": bu_head
            }
            for emp in employees
        ]
    except Exception as ex:
        logger.error(f"Error filtering employees by BU head: {ex}")
        raise HTTPException(status_code=500, detail="Failed to filter employees by BU head")


# ============================================================
# Employee CRUD by code (path parameter — must be LAST)
# ============================================================

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
        "status": employee.status if employee.status is not None else 1,
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
        if data.work_mode.upper() not in ('WFO', 'HYBRID', 'WFH', 'CLIENT_OFFICE'):
            raise HTTPException(status_code=400, detail="work_mode must be WFO, HYBRID, WFH, or CLIENT_OFFICE")
        employee.work_mode = data.work_mode.upper()
    if data.status is not None:
        employee.status = data.status

    db.commit()
    db.refresh(employee)

    return {
        "id": employee.id,
        "code": employee.code,
        "name": employee.name,
        "email": employee.email,
        "department": employee.department,
        "work_mode": employee.work_mode or "WFO",
        "status": employee.status if employee.status is not None else 1
    }