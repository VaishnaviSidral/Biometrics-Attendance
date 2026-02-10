"""
Report Generator Service
Generates various attendance reports for HR dashboard
"""
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import json
import logging

from models.employee import Employee
from models.attendance import AttendanceLog, DailyAttendance, WeeklySummary, AttendanceStatus, ComplianceStatus
from config import settings, get_status_color

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate attendance reports"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_dashboard_summary(self) -> Dict:
        """Get summary statistics for dashboard"""
        # Total employees
        total_employees = self.db.query(Employee).count()
        
        # Get latest week's data
        latest_summary = self.db.query(WeeklySummary).order_by(
            WeeklySummary.week_start.desc()
        ).first()
        
        if latest_summary:
            week_start = latest_summary.week_start
            week_end = latest_summary.week_end
            
            # Get all summaries for this week
            weekly_summaries = self.db.query(WeeklySummary).filter(
                WeeklySummary.week_start == week_start
            ).all()
            
            # Calculate averages
            total_compliance = sum(s.compliance_percentage for s in weekly_summaries)
            avg_compliance = total_compliance / len(weekly_summaries) if weekly_summaries else 0
            
            # Count by status
            status_counts = {
                'RED': 0,
                'AMBER': 0,
                'GREEN': 0
            }
            for s in weekly_summaries:
                status_counts[s.status.value] += 1
            
            total_wfo_days = sum(s.wfo_days for s in weekly_summaries)
        else:
            week_start = None
            week_end = None
            avg_compliance = 0
            status_counts = {'RED': 0, 'AMBER': 0, 'GREEN': 0}
            total_wfo_days = 0
        
        return {
            'total_employees': total_employees,
            'avg_compliance': round(avg_compliance, 2),
            'status_distribution': status_counts,
            'total_wfo_days': total_wfo_days,
            'week_start': week_start.isoformat() if week_start else None,
            'week_end': week_end.isoformat() if week_end else None,
            'alerts': status_counts.get('RED', 0)
        }
    
    def get_all_employees_report(
        self, 
        week_start: Optional[date] = None,
        sort_by: str = 'name',
        sort_order: str = 'asc',
        status_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Generate report for all employees
        
        Args:
            week_start: Filter by specific week (optional)
            sort_by: Column to sort by
            sort_order: 'asc' or 'desc'
            status_filter: Filter by status ('RED', 'AMBER', 'GREEN')
        
        Returns:
            List of employee reports
        """
        if week_start:
            # Filter by specific week in the JOIN condition to keep all employees
            # (Outer join with condition ensures employees without data for this week are still returned)
            query = self.db.query(Employee, WeeklySummary).outerjoin(
                WeeklySummary,
                and_(
                    WeeklySummary.employee_code == Employee.code,
                    WeeklySummary.week_start == week_start
                )
            )
        else:
            # Get latest week
            latest = self.db.query(func.max(WeeklySummary.week_start)).scalar()
            if latest:
                query = self.db.query(Employee, WeeklySummary).outerjoin(
                    WeeklySummary,
                    and_(
                        WeeklySummary.employee_code == Employee.code,
                        WeeklySummary.week_start == latest
                    )
                )
            else:
                # No data at all, just return employees
                query = self.db.query(Employee, WeeklySummary).outerjoin(
                    WeeklySummary,
                    Employee.code == WeeklySummary.employee_code
                )
        
        if status_filter:
            query = query.filter(WeeklySummary.status == status_filter)
        
        results = query.all()
        
        reports = []
        for emp, summary in results:
            report = {
                'employee_code': emp.code,
                'employee_name': emp.name,
                'department': emp.department,
                'total_office_hours': self._format_minutes(summary.total_office_minutes) if summary else '0h 0m',
                'total_office_minutes': summary.total_office_minutes if summary else 0,
                'wfo_days': summary.wfo_days if summary else 0,
                'required_wfo_days': emp.required_wfo_days,
                'expected_hours': self._format_minutes(summary.expected_minutes) if summary else self._format_minutes(settings.expected_weekly_minutes),
                'compliance_percentage': summary.compliance_percentage if summary else 0,
                'status': summary.status.value if summary else 'RED',
                'week_start': summary.week_start.isoformat() if summary else None,
                'week_end': summary.week_end.isoformat() if summary else None
            }
            reports.append(report)
        
        # Sort results
        reverse = sort_order.lower() == 'desc'
        if sort_by == 'name':
            reports.sort(key=lambda x: x['employee_name'], reverse=reverse)
        elif sort_by == 'compliance':
            reports.sort(key=lambda x: x['compliance_percentage'], reverse=reverse)
        elif sort_by == 'hours':
            reports.sort(key=lambda x: x['total_office_minutes'], reverse=reverse)
        elif sort_by == 'status':
            status_order = {'GREEN': 3, 'AMBER': 2, 'RED': 1}
            reports.sort(key=lambda x: status_order.get(x['status'], 0), reverse=reverse)
        
        return reports
    
    def get_individual_report(
        self, 
        employee_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        """
        Generate detailed report for a single employee
        
        Args:
            employee_code: Employee code
            start_date: Start of date range
            end_date: End of date range
        
        Returns:
            Detailed employee report
        """
        # Get employee
        employee = self.db.query(Employee).filter(
            Employee.code == employee_code
        ).first()
        
        if not employee:
            return None
        
        # Build query for daily attendance
        query = self.db.query(DailyAttendance).filter(
            DailyAttendance.employee_code == employee_code
        )
        
        if start_date:
            query = query.filter(DailyAttendance.date >= start_date)
        if end_date:
            query = query.filter(DailyAttendance.date <= end_date)
        
        daily_records = query.order_by(DailyAttendance.date.desc()).all()
        
        # Get weekly summaries
        weekly_query = self.db.query(WeeklySummary).filter(
            WeeklySummary.employee_code == employee_code
        ).order_by(WeeklySummary.week_start.desc())
        
        weekly_summaries = weekly_query.all()
        
        # Calculate overall statistics
        total_office_minutes = sum(d.total_office_minutes for d in daily_records)
        total_wfo_days = len([d for d in daily_records if d.status != AttendanceStatus.ABSENT])
        
        # Get dynamic settings for expected hours
        from routers.settings import get_dynamic_settings
        dynamic_settings = get_dynamic_settings(self.db)
        expected_daily_minutes = dynamic_settings['expected_hours_per_day'] * 60
        
        # Format daily records with compliance
        daily_data = []
        for record in daily_records:
            pairs = json.loads(record.in_out_pairs) if record.in_out_pairs else []
            
            # Calculate daily compliance percentage
            if expected_daily_minutes > 0:
                daily_compliance = (record.total_office_minutes / expected_daily_minutes) * 100
            else:
                daily_compliance = 0
            
            # Determine daily status color based on thresholds
            if daily_compliance > dynamic_settings['threshold_amber']:
                daily_status_color = 'GREEN'
            elif daily_compliance >= dynamic_settings['threshold_red']:
                daily_status_color = 'AMBER'
            else:
                daily_status_color = 'RED'
            
            daily_data.append({
                'date': record.date.isoformat(),
                'day': record.date.strftime('%A'),
                'first_in': record.first_in.strftime('%H:%M') if record.first_in else '-',
                'last_out': record.last_out.strftime('%H:%M') if record.last_out else '-',
                'in_out_pairs': pairs,
                'total_hours': self._format_minutes(record.total_office_minutes),
                'total_minutes': record.total_office_minutes,
                'status': record.status.value,
                'daily_compliance': round(daily_compliance, 1),
                'daily_status_color': daily_status_color
            })
        
        # Format weekly summaries
        weekly_data = []
        for summary in weekly_summaries:
            weekly_data.append({
                'week_start': summary.week_start.isoformat(),
                'week_end': summary.week_end.isoformat(),
                'week_label': f"{summary.week_start.strftime('%d %b')} - {summary.week_end.strftime('%d %b %Y')}",
                'total_hours': self._format_minutes(summary.total_office_minutes),
                'total_minutes': summary.total_office_minutes,
                'total_minutes': summary.total_office_minutes,
                'wfo_days': summary.wfo_days,
                'required_wfo_days': employee.required_wfo_days,
                'compliance_percentage': summary.compliance_percentage,
                'status': summary.status.value
            })
        
        # Calculate average compliance
        avg_compliance = sum(w['compliance_percentage'] for w in weekly_data) / len(weekly_data) if weekly_data else 0
        
        return {
            'employee': {
                'code': employee.code,
                'name': employee.name,
                'department': employee.department
            },
            'summary': {
                'total_office_hours': self._format_minutes(total_office_minutes),
                'total_wfo_days': total_wfo_days,
                'avg_compliance': round(avg_compliance, 2),
                'overall_status': 'GREEN' if avg_compliance > dynamic_settings['threshold_amber'] else ('AMBER' if avg_compliance >= dynamic_settings['threshold_red'] else 'RED')
            },
            'daily_records': daily_data,
            'weekly_summaries': weekly_data
        }
    
    def get_wfo_compliance_report(
        self, 
        week_start: Optional[date] = None
    ) -> Dict:
        """
        Generate WFO compliance report
        
        Args:
            week_start: Specific week to report on
        
        Returns:
            WFO compliance report with all employees
        """
        # Get dynamic settings
        from routers.settings import get_dynamic_settings
        dynamic_settings = get_dynamic_settings(self.db)
        
        if not week_start:
            # Get latest week
            week_start = self.db.query(func.max(WeeklySummary.week_start)).scalar()
        
        if not week_start:
            return {
                'week_start': None,
                'week_end': None,
                'expected_wfo_days': dynamic_settings['wfo_days_per_week'],
                'expected_hours_per_day': dynamic_settings['expected_hours_per_day'],
                'employees': [],
                'summary': {
                    'total_employees': 0,
                    'compliant': 0,
                    'non_compliant': 0,
                    'compliance_rate': 0
                }
            }
        
        # Get all summaries for this week
        summaries = self.db.query(
            WeeklySummary, Employee
        ).join(
            Employee, WeeklySummary.employee_code == Employee.code
        ).filter(
            WeeklySummary.week_start == week_start
        ).all()
        
        employees = []
        compliant_count = 0
        
        for summary, employee in summaries:
            # Compliant if Green (> threshold_amber) or Amber (>= threshold_red)?
            # Usually "Compliant" means meeting the target. If Amber is "Meets Target" and Green is "Excellent",
            # then anything >= threshold_red is compliant.
            # Let's assume >= threshold_red is compliant (Meets Target or better).
            
            is_compliant = summary.compliance_percentage >= dynamic_settings['threshold_red']
            if is_compliant:
                compliant_count += 1
            
            employees.append({
                'employee_code': employee.code,
                'employee_name': employee.name,
                'wfo_days': summary.wfo_days,
                'actual_hours': self._format_minutes(summary.total_office_minutes),
                'actual_minutes': summary.total_office_minutes,
                'expected_hours': self._format_minutes(summary.expected_minutes),
                'expected_minutes': summary.expected_minutes,
                'compliance_percentage': summary.compliance_percentage,
                'status': summary.status.value,
                'is_compliant': is_compliant
            })
        
        total_employees = len(employees)
        compliance_rate = (compliant_count / total_employees * 100) if total_employees > 0 else 0
        
        # Get week end
        week_end = week_start + timedelta(days=6)
        
        return {
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'week_label': f"{week_start.strftime('%d %b')} - {week_end.strftime('%d %b %Y')}",
            'expected_wfo_days': dynamic_settings['wfo_days_per_week'],
            'expected_hours_per_day': dynamic_settings['expected_hours_per_day'],
            'employees': employees,
            'summary': {
                'total_employees': total_employees,
                'compliant': compliant_count,
                'non_compliant': total_employees - compliant_count,
                'compliance_rate': round(compliance_rate, 2)
            }
        }
    
    def get_available_weeks(self) -> List[Dict]:
        """Get list of available weeks in the data"""
        weeks = self.db.query(
            WeeklySummary.week_start,
            WeeklySummary.week_end
        ).distinct().order_by(WeeklySummary.week_start.desc()).all()
        
        return [{
            'week_start': w.week_start.isoformat(),
            'week_end': w.week_end.isoformat(),
            'label': f"{w.week_start.strftime('%d %b')} - {w.week_end.strftime('%d %b %Y')}"
        } for w in weeks]
    
    def _format_minutes(self, minutes: int) -> str:
        """Format minutes as human-readable string"""
        if not minutes:
            return '0h 0m'
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"

    def get_dashboard_daily_stats(
        self,
        week_start: Optional[date] = None
    ) -> Dict:
        """Get daily stats for dashboard chart (WFO vs WFH)"""
        if not week_start:
            # Get latest week
            week_start = self.db.query(func.max(WeeklySummary.week_start)).scalar()
        
        if not week_start:
            return {'dates': [], 'wfo': [], 'wfh': [], 'week_label': ''}

        week_end = week_start + timedelta(days=6)
        
        # Get total active employees count
        total_employees = self.db.query(Employee).count()
        
        # Query daily attendance for this week
        daily_counts = self.db.query(
            DailyAttendance.date,
            func.count(DailyAttendance.id)
        ).filter(
            and_(
                DailyAttendance.date >= week_start,
                DailyAttendance.date <= week_end,
                DailyAttendance.status == AttendanceStatus.PRESENT
            )
        ).group_by(DailyAttendance.date).all()
        
        counts_map = {d: c for d, c in daily_counts}
        
        stats = []
        current = week_start
        while current <= week_end:
            # Skip weekends if needed? User didn't specify, but usually M-F. 
            # Showing all 7 days for completeness.
            wfo_count = counts_map.get(current, 0)
            wfh_count = max(0, total_employees - wfo_count)
            
            stats.append({
                'date': current.isoformat(),
                'day': current.strftime('%a'),
                'wfo': wfo_count,
                'wfh': wfh_count
            })
            current += timedelta(days=1)
            
        return {
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'week_label': f"{week_start.strftime('%d %b')} - {week_end.strftime('%d %b %Y')}",
            'stats': stats
        }

    def get_daily_details(
        self,
        date_str: str,
        status_category: str  # 'WFO' or 'WFH'
    ) -> List[Dict]:
        """Get list of employees for specific day and status"""
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get all daily attendance for this date
        daily_records = self.db.query(
            DailyAttendance
        ).filter(
            DailyAttendance.date == target_date
        ).all()
        
        present_employees = {d.employee_code: d for d in daily_records if d.status == AttendanceStatus.PRESENT}
        
        results = []
        all_employees = self.db.query(Employee).all()
        
        for emp in all_employees:
            record = present_employees.get(emp.code)
            is_present = record is not None
            
            # Determine if matches filter
            if status_category == 'WFO' and is_present:
                results.append({
                    'employee_code': emp.code,
                    'employee_name': emp.name,
                    'department': emp.department,
                    'status': 'PRESENT',
                    'hours': self._format_minutes(record.total_office_minutes),
                    'in_time': record.first_in.strftime('%H:%M') if record.first_in else '-',
                    'out_time': record.last_out.strftime('%H:%M') if record.last_out else '-'
                })
            elif status_category == 'WFH' and not is_present:
                # WFH or Absent
                results.append({
                    'employee_code': emp.code,
                    'employee_name': emp.name,
                    'department': emp.department,
                    'status': 'WFH/ABSENT',
                    'hours': '0h 0m',
                    'in_time': '-',
                    'out_time': '-'
                })
                
        return results
