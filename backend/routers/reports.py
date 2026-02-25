"""
Reports Router
Handles report generation API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime
import csv
import io

from database import get_db
from services.report_generator import ReportGenerator
from services.auth_utils import require_admin, CurrentUser

router = APIRouter(prefix="/reports", tags=["reports"])


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse date string to date object"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


@router.get("/dashboard")
async def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Get dashboard summary statistics"""
    generator = ReportGenerator(db)
    return generator.get_dashboard_summary()


@router.get("/dashboard-stats")
async def get_dashboard_daily_stats(
    week_start: Optional[str] = Query(None, description="Week start date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Get daily WFO/WFH stats for dashboard chart"""
    generator = ReportGenerator(db)
    week_date = parse_date(week_start)
    return generator.get_dashboard_daily_stats(week_start=week_date)


@router.get("/weekly-compliance-stats")
async def get_weekly_compliance_stats(
    week_start: Optional[str] = Query(None, description="Week start date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Get weekly compliance stats for dashboard cards"""
    generator = ReportGenerator(db)
    week_date = parse_date(week_start)
    return generator.get_weekly_compliance_stats(week_start=week_date)


@router.get("/daily-details")
async def get_daily_details(
    date: str = Query(..., description="Date (YYYY-MM-DD)"),
    status: str = Query("WFO", description="Status category: WFO or WFH"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Get details of employees for specific day and status"""
    generator = ReportGenerator(db)
    return generator.get_daily_details(date_str=date, status_category=status)


@router.get("/all-employees")
async def get_all_employees_report(
    week_start: Optional[str] = Query(None, description="Week start date (YYYY-MM-DD)"),
    sort_by: str = Query("name", description="Sort by: name, compliance, hours, status"),
    sort_order: str = Query("asc", description="Sort order: asc, desc"),
    status_filter: Optional[str] = Query(None, description="Filter by status: Non-Compliance, Mid-Compliance, Compliance"),
    work_mode: Optional[str] = Query(None, description="Filter by work mode: WFO, HYBRID, WFH"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Get report for all employees with optional work_mode filter"""
    generator = ReportGenerator(db)
    week_date = parse_date(week_start)

    return {
        "employees": generator.get_all_employees_report(
            week_start=week_date,
            sort_by=sort_by,
            sort_order=sort_order,
            status_filter=status_filter,
            work_mode_filter=work_mode
        ),
        "available_weeks": generator.get_available_weeks()
    }


@router.get("/individual/{employee_code}")
async def get_individual_report(
    employee_code: str,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Get detailed report for a single employee"""
    generator = ReportGenerator(db)

    report = generator.get_individual_report(
        employee_code=employee_code,
        start_date=parse_date(start_date),
        end_date=parse_date(end_date)
    )

    if not report:
        raise HTTPException(status_code=404, detail="Employee not found")

    return report


@router.get("/wfo-compliance")
async def get_wfo_compliance_report(
    week_start: Optional[str] = Query(None, description="Week start date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Get WFO compliance report"""
    generator = ReportGenerator(db)
    week_date = parse_date(week_start)

    report = generator.get_wfo_compliance_report(week_start=week_date)
    report['available_weeks'] = generator.get_available_weeks()

    return report


@router.get("/weeks")
async def get_available_weeks(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Get list of available weeks"""
    generator = ReportGenerator(db)
    return {"weeks": generator.get_available_weeks()}


@router.get("/monthly-report")
async def get_monthly_report(
    month: str = Query(..., description="Month in YYYY-MM format"),
    search: Optional[str] = Query(None, description="Search by employee name or code"),
    work_mode: Optional[str] = Query(None, description="Filter by work mode: WFO, HYBRID, WFH"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Admin Monthly Report — presence-based, day-based compliance"""
    generator = ReportGenerator(db)
    return generator.get_monthly_report(month=month, search=search, work_mode=work_mode)


@router.get("/monthly-report/export")
async def export_monthly_report_csv(
    month: str = Query(..., description="Month in YYYY-MM format"),
    search: Optional[str] = Query(None, description="Search by employee name or code"),
    work_mode: Optional[str] = Query(None, description="Filter by work mode: WFO, HYBRID"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Export monthly report as CSV"""
    generator = ReportGenerator(db)
    data = generator.get_monthly_report(month=month, search=search, work_mode=work_mode)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Emp Code",
        "Emp Name",
        "Work Mode",
        "Required WFO Days",
        "Total WFO Days",
        "Total WFH Days",
        "Days Below Required Hours",
        # "Compliance %",
        "Status"
    ])

    for row in data:
        writer.writerow([
            row["employee_code"],
            row["employee_name"],
            row["work_mode"],
            row["required_days"], 
            row["total_wfo_days"],
            row["total_wfh_days"],
            row["days_below_required_hours"],
            # f'{row["compliance_percentage"]:.2f}%',
            row["compliance_status"]
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=monthly_report_{month}.csv"
        }
    )


# @router.get("/monthly-report/export/{employee_code}")
# async def export_monthly_individual_csv(
#     employee_code: str,
#     month: str = Query(..., description="Month in YYYY-MM format"),
#     db: Session = Depends(get_db),
#     current_user: CurrentUser = Depends(require_admin)
# ):
#     """Export individual employee monthly attendance as CSV"""
#     from datetime import datetime as dt_mod
#     import calendar as cal_mod

#     year, mon = map(int, month.split("-"))
#     start_date = date(year, mon, 1)
#     _, days_in = cal_mod.monthrange(year, mon)
#     end_date = date(year, mon, days_in)

#     generator = ReportGenerator(db)
#     report = generator.get_individual_report(
#         employee_code=employee_code,
#         start_date=start_date,
#         end_date=end_date
#     )

#     if not report:
#         raise HTTPException(status_code=404, detail="Employee not found")

#     output = io.StringIO()
#     writer = csv.writer(output)

#     month_label = start_date.strftime('%B %Y')
#     writer.writerow([f'Monthly Report - {month_label}'])
#     writer.writerow(['Code', report['employee']['code']])
#     writer.writerow(['Name', report['employee']['name']])
#     writer.writerow(['Work Mode', report['employee']['work_mode']])
#     writer.writerow(['Department', report['employee']['department'] or ''])
#     writer.writerow([])
#     writer.writerow(['Date', 'Day', 'First In', 'Last Out', 'Total Hours', 'Status'])

#     for day in report['daily_records']:
#         writer.writerow([
#             day['date'],
#             day['day'],
#             day['first_in'],
#             day['last_out'],
#             day['total_hours'],
#             day['status']
#         ])

#     output.seek(0)
#     return StreamingResponse(
#         iter([output.getvalue()]),
#         media_type="text/csv",
#         headers={
#             "Content-Disposition": f"attachment; filename={employee_code}_{month}_report.csv"
#         }
#     )


@router.get("/export/all-employees")
async def export_all_employees_csv(
    week_start: Optional[str] = Query(None, description="Week start date (YYYY-MM-DD)"),
    sort_by: str = Query("name", description="Sort by: name, compliance, hours, status"),
    sort_order: str = Query("asc", description="Sort order: asc, desc"),
    status_filter: Optional[str] = Query(None, description="Filter by status: Non-Compliance, Mid-Compliance, Compliance"),
    work_mode: Optional[str] = Query(None, description="Filter by work mode: WFO, HYBRID, WFH"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Export all employees report as CSV — respects the same filters as the UI"""
    generator = ReportGenerator(db)
    week_date = parse_date(week_start)

    employees = generator.get_all_employees_report(
        week_start=week_date,
        sort_by=sort_by,
        sort_order=sort_order,
        status_filter=status_filter,
        work_mode_filter=work_mode
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'Employee Code', 'Employee Name', 'Work Mode', 'Department',
        'Total Office Hours', 'WFO Days', 'Expected Hours',
        'Compliance %', 'Status'
    ])

    for emp in employees:
        writer.writerow([
            emp['employee_code'],
            emp['employee_name'],
            emp['work_mode'],
            emp['department'] or '',
            emp['total_office_hours'],
            emp['wfo_days'],
            emp['expected_hours'],
            f"{emp['compliance_percentage']:.2f}%",
            emp['status']
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=all_employees_report.csv"}
    )


@router.get("/export/wfo-compliance")
async def export_wfo_compliance_csv(
    week_start: Optional[str] = Query(None, description="Week start date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Export WFO compliance report as CSV"""
    generator = ReportGenerator(db)
    week_date = parse_date(week_start)

    report = generator.get_wfo_compliance_report(week_start=week_date)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'Employee Code', 'Employee Name', 'Work Mode',
        'WFO Days', 'Actual Hours', 'Expected Hours',
        'Compliance %', 'Status', 'Compliant'
    ])

    for emp in report['employees']:
        writer.writerow([
            emp['employee_code'],
            emp['employee_name'],
            emp['work_mode'],
            emp['wfo_days'],
            emp['actual_hours'],
            emp['expected_hours'],
            f"{emp['compliance_percentage']:.2f}%",
            emp['status'],
            'Yes' if emp['is_compliant'] else 'No'
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=wfo_compliance_report.csv"}
    )


@router.get("/export/individual/{employee_code}")
async def export_individual_csv(
    employee_code: str,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """Export individual employee report as CSV"""
    generator = ReportGenerator(db)

    report = generator.get_individual_report(
        employee_code=employee_code,
        start_date=parse_date(start_date),
        end_date=parse_date(end_date)
    )

    if not report:
        raise HTTPException(status_code=404, detail="Employee not found")

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Employee Report'])
    writer.writerow(['Code', report['employee']['code']])
    writer.writerow(['Name', report['employee']['name']])
    writer.writerow(['Work Mode', report['employee']['work_mode']])
    writer.writerow(['Department', report['employee']['department'] or ''])
    writer.writerow([])

    writer.writerow(['Summary'])
    writer.writerow(['Total Office Hours', report['summary']['total_office_hours']])
    writer.writerow(['Total WFO Days', report['summary']['total_wfo_days']])
    writer.writerow(['Average Compliance', f"{report['summary']['avg_compliance']}%"])
    writer.writerow(['Overall Status', report['summary']['overall_status']])
    writer.writerow([])

    writer.writerow(['Daily Records'])
    writer.writerow(['Date', 'Day', 'First In', 'Last Out', 'Time Logs', 'Total Hours', 'Status'])

    for day in report['daily_records']:
        time_logs = ""
        if day.get('in_out_pairs'):
            logs = []
            for pair in day['in_out_pairs']:
                p_in = pair.get('in', '-')
                p_out = pair.get('out', '-')
                logs.append(f"{p_in}-{p_out}")
            time_logs = ", ".join(logs)

        writer.writerow([
            day['date'],
            day['day'],
            day['first_in'],
            day['last_out'],
            time_logs,
            day['total_hours'],
            day['status']
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={employee_code}_report.csv"}
    )
