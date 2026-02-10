"""
Upload Router
Handles file upload and data processing
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import logging

from database import get_db
from services.attendance_parser import AttendanceParser
from services.time_calculator import TimeCalculator
from services.auth_utils import require_admin
from models.employee import Employee
from models.user import User
from models.attendance import AttendanceLog, DailyAttendance, WeeklySummary, AttendanceStatus, ComplianceStatus
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/")
async def upload_attendance_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Upload and process biometric attendance file (CSV or Excel)
    
    This endpoint:
    1. Parses the uploaded file
    2. Extracts and stores employees
    3. Stores raw attendance logs
    4. Calculates daily summaries
    5. Calculates weekly summaries
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not file.filename.lower().endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(
            status_code=400, 
            detail="Invalid file format. Please upload a CSV or Excel file."
        )
    
    try:
        # Read file content
        content = await file.read()
        
        # Parse file
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
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
        
        # Extract and store employees
        employees = parser.get_unique_employees(records)
        employees_created = 0
        
        for emp in employees:
            existing = db.query(Employee).filter(Employee.code == emp['code']).first()
            if not existing:
                new_emp = Employee(
                    code=emp['code'],
                    name=emp['name'] or f"Employee {emp['code']}"
                )
                db.add(new_emp)
                employees_created += 1
            elif emp['name'] and not existing.name:
                existing.name = emp['name']
        
        db.commit()
        
        # Store raw attendance logs
        logs_created = 0
        for record in records:
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
        
        # Calculate daily summaries with dynamic settings from database
        from routers.settings import get_dynamic_settings
        dynamic_settings = get_dynamic_settings(db)
        
        calculator = TimeCalculator(
            expected_hours_per_day=dynamic_settings['expected_hours_per_day'],
            wfo_days_per_week=dynamic_settings['wfo_days_per_week'],
            min_hours_for_present=dynamic_settings['min_hours_for_present'],
            threshold_red=dynamic_settings['threshold_red'],
            threshold_amber=dynamic_settings['threshold_amber']
        )
        
        daily_summaries = calculator.calculate_daily_summary(records)
        daily_created = 0
        
        for emp_code, date_summaries in daily_summaries.items():
            for rec_date, summary in date_summaries.items():
                # Check if already exists
                existing = db.query(DailyAttendance).filter(
                    DailyAttendance.employee_code == emp_code,
                    DailyAttendance.date == rec_date
                ).first()
                
                status_enum = AttendanceStatus[summary['status']]
                
                if existing:
                    # Update existing
                    existing.total_office_minutes = summary['total_office_minutes']
                    existing.status = status_enum
                    existing.in_out_pairs = summary['in_out_pairs']
                    existing.first_in = summary['first_in']
                    existing.last_out = summary['last_out']
                else:
                    # Create new
                    daily = DailyAttendance(
                        employee_code=emp_code,
                        date=rec_date,
                        total_office_minutes=summary['total_office_minutes'],
                        status=status_enum,
                        in_out_pairs=summary.get('in_out_pairs'),
                        first_in=summary.get('first_in'),
                        last_out=summary.get('last_out')
                    )
                    db.add(daily)
                    daily_created += 1
        
        db.commit()
        
        # Calculate weekly summaries
        all_dates = [record['date'] for record in records]
        weeks = calculator.get_all_weeks(all_dates)
        weekly_created = 0
        
        # Fetch employee requirements for calculation
        all_employees = db.query(Employee).all()
        employee_requirements = {emp.code: emp.required_wfo_days for emp in all_employees}
        
        for week_start, week_end in weeks:
            weekly_data = calculator.calculate_weekly_summary(
                daily_summaries, week_start, week_end, employee_requirements
            )
            
            for emp_code, week_summary in weekly_data.items():
                existing = db.query(WeeklySummary).filter(
                    WeeklySummary.employee_code == emp_code,
                    WeeklySummary.week_start == week_start
                ).first()
                
                status_enum = ComplianceStatus[week_summary['status']]
                
                if existing:
                    # Update existing
                    existing.total_office_minutes = week_summary['total_office_minutes']
                    existing.wfo_days = week_summary['wfo_days']
                    existing.expected_minutes = week_summary['expected_minutes']
                    existing.compliance_percentage = week_summary['compliance_percentage']
                    existing.status = status_enum
                else:
                    # Create new
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
                "employees_created": employees_created,
                "attendance_logs_created": logs_created,
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
