"""
Employee Attendance Router
Handles employee-specific attendance data access.

Compliance Philosophy:
  Daily compliance status is the single source of truth.
  Weekly compliance is aggregated from daily statuses, NOT from hours.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import extract, func, and_
from typing import Optional, List
from datetime import date, datetime, time, timedelta
from pydantic import BaseModel

from database import get_db
from services.auth_utils import get_current_user, CurrentUser
from services.time_calculator import TimeCalculator
from models.attendance import DailyAttendance, WeeklySummary
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


def _get_week_boundaries(target_date: date = None):
    """Get Monday-Sunday boundaries for the week containing target_date."""
    if not target_date:
        target_date = date.today()
    # Monday = 0
    monday = target_date - timedelta(days=target_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


@router.get("/weekly-compliance")
async def get_employee_weekly_compliance(
    week_start: Optional[str] = Query(None, description="Week start date YYYY-MM-DD (Monday)"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get weekly compliance data for the logged-in employee.
    Shows current week by default + summary of last 5 weeks.

    Compliance is derived from daily compliance statuses, NOT from hours.
    """
    # Get employee
    employee_code = current_user.employee_code
    if not employee_code:
        employee = db.query(Employee).filter(Employee.email == current_user.email).first()
        if employee:
            employee_code = employee.code
        else:
            raise HTTPException(status_code=404, detail="No employee record associated with this user")

    employee = db.query(Employee).filter(Employee.code == employee_code).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    work_mode = (employee.work_mode or 'WFO').upper()

    # Dynamic settings for compliance calculation
    from routers.settings import get_dynamic_settings
    from services.time_calculator import build_work_mode_config
    ds = get_dynamic_settings(db)
    wmc = build_work_mode_config(
        expected_hours_per_day=ds['expected_hours_per_day'],
        wfo_days_per_week=ds['wfo_days_per_week'],
        hybrid_days_per_week=ds['hybrid_days_per_week']
    )
    mode_config = wmc.get(work_mode, wmc['WFO'])
    is_wfh = mode_config.get('always_compliant', False)

    # Create calculator for rule engine
    calculator = TimeCalculator(
        expected_hours_per_day=ds['expected_hours_per_day'],
        wfo_days_per_week=ds['wfo_days_per_week'],
        hybrid_days_per_week=ds['hybrid_days_per_week'],
        compliance_hours=ds['compliance_hours'],
        mid_compliance_hours=ds['mid_compliance_hours'],
        non_compliance_hours=ds['non_compliance_hours']
    )

    # Determine selected week
    if week_start:
        try:
            sel_monday = datetime.strptime(week_start, "%Y-%m-%d").date()
        except ValueError:
            sel_monday = _get_week_boundaries()[0]
    else:
        sel_monday = _get_week_boundaries()[0]

    sel_sunday = sel_monday + timedelta(days=6)

    # --- Selected week's daily breakdown ---
    daily_records = db.query(DailyAttendance).filter(
        and_(
            DailyAttendance.employee_code == employee_code,
            DailyAttendance.date >= sel_monday,
            DailyAttendance.date <= sel_sunday
        )
    ).order_by(DailyAttendance.date).all()

    daily_map = {r.date: r for r in daily_records}
    expected_daily_minutes = mode_config['hours_per_day'] * 60

    daily_data = []
    week_daily_statuses = []
    week_present_days = 0
    current = sel_monday
    while current <= sel_sunday:
        record = daily_map.get(current)
        if record:
            minutes = record.total_office_minutes or 0
            is_present = minutes > 0 or record.first_in is not None

            if record.compliance_status and current.weekday() < 5:
                day_compliance_status = record.compliance_status.value
            elif current.weekday() < 5:
                day_compliance_status = calculator.compute_daily_compliance_status(
                    minutes, is_present, is_wfh
                )
            else:
                day_compliance_status = None

            daily_data.append({
                'date': current.isoformat(),
                'day': current.strftime('%A'),
                'first_in': record.first_in.strftime('%I:%M %p') if record.first_in else '-',
                'last_out': record.last_out.strftime('%I:%M %p') if record.last_out else '-',
                'total_hours': format_minutes_to_hours(minutes),
                'total_minutes': minutes,
                'is_present': is_present,
                'is_weekday': current.weekday() < 5,
                'compliance_status': day_compliance_status
            })

            if current.weekday() < 5:
                if day_compliance_status:
                    week_daily_statuses.append(day_compliance_status)
                if is_present:
                    week_present_days += 1
        else:
            is_weekday = current.weekday() < 5
            daily_data.append({
                'date': current.isoformat(),
                'day': current.strftime('%A'),
                'first_in': '-',
                'last_out': '-',
                'total_hours': '0h 00m',
                'total_minutes': 0,
                'is_present': False,
                'is_weekday': is_weekday,
                'compliance_status': 'Non-Compliance' if is_weekday and not is_wfh else (
                    'Compliance' if is_weekday and is_wfh else None
                )
            })

            if is_weekday:
                if is_wfh:
                    week_daily_statuses.append('Compliance')
                else:
                    week_daily_statuses.append('Non-Compliance')

        current += timedelta(days=1)

    week_total_minutes = sum(
            d['total_minutes']
            for d in daily_data
            if d['is_weekday']
        )
    week_wfo_days = sum(1 for d in daily_data if d['is_present'] and d['is_weekday'])

    required_days = mode_config['required_days']
    week_status = TimeCalculator.calculate_weekly_compliance(
        week_daily_statuses, week_present_days, required_days, is_wfh
    )

    if is_wfh:
        week_compliance = 100.0
    else:
        expected_weekly_minutes = mode_config.get('expected_weekly_hours', 0) * 60
        if expected_weekly_minutes > 0:
            week_compliance = min((week_total_minutes / expected_weekly_minutes) * 100, 100.0)
        else:
            week_compliance = 0.0

    # --- Last 5 weeks summary (from WeeklySummary table) ---
    weekly_summaries = db.query(WeeklySummary).filter(
        WeeklySummary.employee_code == employee_code
    ).order_by(WeeklySummary.week_start.desc()).limit(5).all()

    weeks_summary = []
    for s in weekly_summaries:
        if is_wfh:
            s_compliance = 100.0
            s_status = 'Compliance'
        else:
            s_daily_records = db.query(DailyAttendance).filter(
                and_(
                    DailyAttendance.employee_code == employee_code,
                    DailyAttendance.date >= s.week_start,
                    DailyAttendance.date <= s.week_end
                )
            ).all()

            s_daily_map = {r.date: r for r in s_daily_records}
            s_daily_statuses = []
            s_present_days = 0

            s_current = s.week_start
            while s_current <= s.week_end:
                if s_current.weekday() < 5:
                    dr = s_daily_map.get(s_current)
                    if dr:
                        is_p = (dr.total_office_minutes or 0) > 0 or dr.first_in is not None
                        if is_p:
                            s_present_days += 1
                        if dr.compliance_status:
                            s_daily_statuses.append(dr.compliance_status.value)
                        else:
                            cs = calculator.compute_daily_compliance_status(
                                dr.total_office_minutes,
                                is_p, False
                            )
                            s_daily_statuses.append(cs)
                    else:
                        s_daily_statuses.append('Non-Compliance')
                s_current += timedelta(days=1)

            s_status = TimeCalculator.calculate_weekly_compliance(
                s_daily_statuses, s_present_days, mode_config['required_days'], False
            )
            expected_weekly_minutes = mode_config.get('expected_weekly_hours', 0) * 60
            if expected_weekly_minutes > 0:
                s_compliance = min((s.total_office_minutes / expected_weekly_minutes) * 100, 100.0)
            else:
                s_compliance = 0.0

        weeks_summary.append({
            'week_start': s.week_start.isoformat(),
            'week_end': s.week_end.isoformat(),
            'week_label': f"{s.week_start.strftime('%d %b')} - {s.week_end.strftime('%d %b %Y')}",
            'total_hours': format_minutes_to_hours(s.total_office_minutes),
            'total_minutes': s.total_office_minutes,
            'wfo_days': s.wfo_days,
            'required_days': mode_config['required_days'],
            'compliance_percentage': round(s_compliance, 2),
            'status': s_status
        })

    # Available weeks for the dropdown
    available_weeks = db.query(
        WeeklySummary.week_start,
        WeeklySummary.week_end
    ).filter(
        WeeklySummary.employee_code == employee_code
    ).distinct().order_by(WeeklySummary.week_start.desc()).all()

    available_weeks_list = [{
        'week_start': w.week_start.isoformat(),
        'week_end': w.week_end.isoformat(),
        'label': f"{w.week_start.strftime('%d %b')} - {w.week_end.strftime('%d %b %Y')}"
    } for w in available_weeks]

    return {
        'employee_name': employee.name,
        'employee_code': employee.code,
        'work_mode': work_mode,
        'selected_week': {
            'week_start': sel_monday.isoformat(),
            'week_end': sel_sunday.isoformat(),
            'week_label': f"{sel_monday.strftime('%d %b')} - {sel_sunday.strftime('%d %b %Y')}",
            'total_hours': format_minutes_to_hours(week_total_minutes),
            'total_minutes': week_total_minutes,
            'wfo_days': week_wfo_days,
            'required_days': mode_config['required_days'],
            'expected_hours': f"{mode_config['expected_weekly_hours']}h",
            'compliance_percentage': round(week_compliance, 2),
            'status': week_status,
            'daily': daily_data
        },
        'weeks_summary': weeks_summary,
        'available_weeks': available_weeks_list
    }
