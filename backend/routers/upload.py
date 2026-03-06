"""
Upload Router
Handles file upload and data processing
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
import logging

from database import get_db
from services.attendance_parser import AttendanceParser
from services.time_calculator import TimeCalculator, build_work_mode_config
from services.auth_utils import require_admin, CurrentUser
from models.employee import Employee
from models.attendance import AttendanceLog, DailyAttendance, WeeklySummary, AttendanceStatus, ComplianceStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/")
async def upload_attendance_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """
    Upload and process biometric attendance file (CSV or Excel)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.lower().endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload a CSV or Excel file."
        )

    try:
        content = await file.read()

        parser = AttendanceParser()
        try:
            df, records = parser.parse_file(content, file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"File parsing error: {str(e)}")
        except Exception as e:
            logger.exception("Error parsing file")
            raise HTTPException(status_code=400, detail=f"Could not parse file. Please check the format.")

        if not records:
            error_msg = "No valid records found in the file."
            if parser.warnings:
                error_msg += f" Warnings: {'; '.join(parser.warnings[:3])}"
            raise HTTPException(status_code=400, detail=error_msg)

        # Validate employees exist in DB (employees must be imported separately)
        unique_employees = parser.get_unique_employees(records)
        existing_employees = {
            emp.code for emp in db.query(Employee.code).all()
        }

        # Find employees in file that are NOT in the DB
        unknown_codes = set()
        for emp in unique_employees:
            if emp['code'] not in existing_employees:
                unknown_codes.add(emp['code'])

        # Filter out records for unknown employees and warn
        if unknown_codes:
            records = [r for r in records if r['code'] not in unknown_codes]
            for code in sorted(unknown_codes):
                parser.warnings.append(
                    f"Employee '{code}' not found in employees table — their attendance records were skipped. "
                    f"Please import this employee first."
                )

        if not records:
            raise HTTPException(
                status_code=400,
                detail="No records to process. All employees in the file are missing from the employees table. "
                       "Please import employees first, then upload attendance data."
            )

        # Store raw attendance logs WITH deduplication
        logs_created = 0
        logs_skipped = 0
        for record in records:
            # Check if this exact log already exists
            existing_log = db.query(AttendanceLog).filter(
                and_(
                    AttendanceLog.employee_code == record['code'],
                    AttendanceLog.date == record['date'],
                    AttendanceLog.in_time == record['in_time'],
                    AttendanceLog.out_time == record['out_time']
                )
            ).first()

            if existing_log:
                logs_skipped += 1
                continue

            log = AttendanceLog(
                employee_code=record['code'],
                date=record['date'],
                in_time=record['in_time'],
                out_time=record['out_time'],
                total_time=record['total_time'],
                shift=record['shift'],
                late_minutes=record['late_minutes'],
                overtime_minutes=record['overtime_minutes'],
                remark=record['remark']
            )
            db.add(log)
            logs_created += 1

        db.commit()

        # Get dynamic settings from DB
        from routers.settings import get_dynamic_settings
        dynamic_settings = get_dynamic_settings(db)

        calculator = TimeCalculator(
            expected_hours_per_day=dynamic_settings['expected_hours_per_day'],
            wfo_days_per_week=dynamic_settings['wfo_days_per_week'],
            hybrid_days_per_week=dynamic_settings['hybrid_days_per_week'],
            threshold_red=dynamic_settings['threshold_red'],
            threshold_amber=dynamic_settings['threshold_amber'],
            compliance_hours=dynamic_settings['compliance_hours'],
            mid_compliance_hours=dynamic_settings['mid_compliance_hours'],
            non_compliance_hours=dynamic_settings['non_compliance_hours']
        )

        # Fetch employee work modes for compliance_status computation
        all_employees = db.query(Employee).all()
        employee_work_modes = {emp.code: (emp.work_mode or 'WFO') for emp in all_employees}

        # Calculate daily summaries from current file and upsert
        daily_summaries = calculator.calculate_daily_summary(records)
        daily_created = 0

        for emp_code, date_summaries in daily_summaries.items():
            for rec_date, summary in date_summaries.items():
                existing = db.query(DailyAttendance).filter(
                    DailyAttendance.employee_code == emp_code,
                    DailyAttendance.date == rec_date
                ).first()

                status_enum = AttendanceStatus[summary['status']]

                # Compute daily compliance_status using rule engine
                work_mode = employee_work_modes.get(emp_code, 'WFO').upper()
                is_wfh = work_mode == 'WFH'
                is_present = summary['total_office_minutes'] > 0 or summary['status'] == 'PRESENT'

                # Only compute compliance for weekdays
                if rec_date.weekday() < 5:
                    # Get employee email for leave checking
                    employee = db.query(Employee).filter(Employee.code == emp_code).first()
                    employee_email = employee.email if employee else None
                    
                    daily_compliance = calculator.compute_daily_compliance_status(
                        summary['total_office_minutes'], is_present, is_wfh, 
                        rec_date.isoformat(), employee_email, db
                    )
                    compliance_enum = ComplianceStatus(daily_compliance)
                else:
                    compliance_enum = None  # Weekends don't have compliance

                if existing:
                    existing.total_office_minutes = summary['total_office_minutes']
                    existing.status = status_enum
                    existing.compliance_status = compliance_enum
                    existing.in_out_pairs = summary['in_out_pairs']
                    existing.first_in = summary['first_in']
                    existing.last_out = summary['last_out']
                else:
                    daily = DailyAttendance(
                        employee_code=emp_code,
                        date=rec_date,
                        total_office_minutes=summary['total_office_minutes'],
                        status=status_enum,
                        compliance_status=compliance_enum,
                        in_out_pairs=summary.get('in_out_pairs'),
                        first_in=summary.get('first_in'),
                        last_out=summary.get('last_out')
                    )
                    db.add(daily)
                    daily_created += 1

        db.commit()

        # Calculate weekly summaries by aggregating from ALL daily_attendance
        # records in the DB (not just current file), so partial week uploads
        # accumulate correctly.
        all_dates = [record['date'] for record in records]
        weeks = calculator.get_all_weeks(all_dates)
        weekly_created = 0

        # Build dynamic work mode config from settings
        work_mode_config = build_work_mode_config(
            expected_hours_per_day=dynamic_settings['expected_hours_per_day'],
            wfo_days_per_week=dynamic_settings['wfo_days_per_week'],
            hybrid_days_per_week=dynamic_settings['hybrid_days_per_week']
        )

        for week_start, week_end in weeks:
            # Query ALL daily_attendance records for this week from DB
            # for ALL employees (not just ones in the current file)
            db_daily_records = db.query(DailyAttendance).filter(
                and_(
                    DailyAttendance.date >= week_start,
                    DailyAttendance.date <= week_end
                )
            ).all()

            # Build daily_summaries dict from DB records (EXCLUDE SAT/SUN)
            db_daily_summaries = {}
            for rec in db_daily_records:
                # weekday(): Mon=0 ... Sun=6
                if rec.date.weekday() >= 5:
                    continue   # skip Saturday & Sunday

                if rec.employee_code not in db_daily_summaries:
                    db_daily_summaries[rec.employee_code] = {}

                db_daily_summaries[rec.employee_code][rec.date] = {
                    'total_office_minutes': rec.total_office_minutes,
                    'status': rec.status.value,
                    'compliance_status': rec.compliance_status.value if rec.compliance_status else None
                }

            # Calculate weekly summary from complete DB data
            # Weekly status is derived from daily compliance_status aggregation
            weekly_data = calculator.calculate_weekly_summary(
                db_daily_summaries, week_start, week_end,
                employee_work_modes, work_mode_config
            )

            for emp_code, week_summary in weekly_data.items():
                existing = db.query(WeeklySummary).filter(
                    WeeklySummary.employee_code == emp_code,
                    WeeklySummary.week_start == week_start
                ).first()

                status_enum = ComplianceStatus(week_summary['status'])

                if existing:
                    existing.total_office_minutes = week_summary['total_office_minutes']
                    existing.wfo_days = week_summary['wfo_days']
                    existing.expected_minutes = week_summary['expected_minutes']
                    existing.compliance_percentage = week_summary['compliance_percentage']
                    existing.status = status_enum
                else:
                    weekly = WeeklySummary(
                        employee_code=emp_code,
                        week_start=week_start,
                        week_end=week_end,
                        total_office_minutes=week_summary['total_office_minutes'],
                        wfo_days=week_summary['wfo_days'],
                        expected_minutes=week_summary['expected_minutes'],
                        compliance_percentage=week_summary['compliance_percentage'],
                        status=status_enum
                    )
                    db.add(weekly)
                    weekly_created += 1

        db.commit()

        return {
            "success": True,
            "message": "File processed successfully",
            "stats": {
                "records_parsed": len(records),
                "employees_skipped_not_in_db": len(unknown_codes),
                "attendance_logs_created": logs_created,
                "attendance_logs_skipped_duplicates": logs_skipped,
                "daily_summaries_created": daily_created,
                "weekly_summaries_created": weekly_created
            },
            "warnings": parser.warnings[:10] if parser.warnings else [],
            "errors": parser.errors[:10] if parser.errors else []
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        with open("upload_debug.log", "a") as f:
            f.write(f"Error processing upload: {str(e)}\n")
            traceback.print_exc(file=f)
        logger.exception("Error processing upload")
        raise HTTPException(status_code=500, detail=f"Error processing file ({type(e).__name__}): {str(e)}")
