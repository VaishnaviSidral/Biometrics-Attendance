"""
Report Generator Service
Generates various attendance reports for HR dashboard.
Supports work_mode based compliance (WFO / HYBRID / WFH).
Uses dynamic settings from DB for all compliance calculations.
"""
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import json
import logging

from models.employee import Employee
from models.attendance import AttendanceLog, DailyAttendance, WeeklySummary, AttendanceStatus, ComplianceStatus
from services.time_calculator import build_work_mode_config
from config import settings, get_status_color

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate attendance reports"""

    def __init__(self, db: Session):
        self.db = db
        # Load dynamic settings and build config once per request
        self._dynamic_settings = None
        self._work_mode_config = None

    @property
    def dynamic_settings(self) -> Dict:
        """Lazy-load dynamic settings from DB"""
        if self._dynamic_settings is None:
            from routers.settings import get_dynamic_settings
            self._dynamic_settings = get_dynamic_settings(self.db)
        return self._dynamic_settings

    @property
    def work_mode_config(self) -> Dict:
        """Lazy-load work mode config built from dynamic settings"""
        if self._work_mode_config is None:
            ds = self.dynamic_settings
            self._work_mode_config = build_work_mode_config(
                expected_hours_per_day=ds['expected_hours_per_day'],
                wfo_days_per_week=ds['wfo_days_per_week'],
                hybrid_days_per_week=ds['hybrid_days_per_week']
            )
        return self._work_mode_config

    def get_dashboard_summary(self) -> Dict:
        """Get summary statistics for dashboard"""
        total_employees = self.db.query(Employee).count()

        # Count by work_mode
        work_mode_counts = {}
        for mode in ['WFO', 'HYBRID', 'WFH']:
            count = self.db.query(Employee).filter(Employee.work_mode == mode).count()
            work_mode_counts[mode] = count

        latest_summary = self.db.query(WeeklySummary).order_by(
            WeeklySummary.week_start.desc()
        ).first()

        if latest_summary:
            week_start = latest_summary.week_start
            week_end = latest_summary.week_end

            weekly_summaries = self.db.query(WeeklySummary).filter(
                WeeklySummary.week_start == week_start
            ).all()

            # Recalculate compliance using dynamic config for display
            total_compliance = 0
            status_counts = {'RED': 0, 'AMBER': 0, 'GREEN': 0}
            total_wfo_days = 0

            for s in weekly_summaries:
                emp = self.db.query(Employee).filter(Employee.code == s.employee_code).first()
                work_mode = (emp.work_mode or 'WFO').upper() if emp else 'WFO'
                mode_config = self.work_mode_config.get(work_mode, self.work_mode_config['WFO'])

                if mode_config.get('always_compliant'):
                    compliance = 100.0
                    status_val = 'GREEN'
                else:
                    compliance = min(s.compliance_percentage, 100.0)  # Cap at 100%
                    status_val = s.status.value

                total_compliance += compliance
                status_counts[status_val] += 1
                total_wfo_days += s.wfo_days

            avg_compliance = total_compliance / len(weekly_summaries) if weekly_summaries else 0
        else:
            week_start = None
            week_end = None
            avg_compliance = 0
            status_counts = {'RED': 0, 'AMBER': 0, 'GREEN': 0}
            total_wfo_days = 0

        return {
            'total_employees': total_employees,
            'work_mode_counts': work_mode_counts,
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
        status_filter: Optional[str] = None,
        work_mode_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Generate report for all employees.
        Supports filtering by work_mode for the WFO/Hybrid/WFH tabs.
        """
        if week_start:
            query = self.db.query(Employee, WeeklySummary).outerjoin(
                WeeklySummary,
                and_(
                    WeeklySummary.employee_code == Employee.code,
                    WeeklySummary.week_start == week_start
                )
            )
        else:
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
                query = self.db.query(Employee, WeeklySummary).outerjoin(
                    WeeklySummary,
                    Employee.code == WeeklySummary.employee_code
                )

        # Filter by work_mode
        if work_mode_filter:
            query = query.filter(Employee.work_mode == work_mode_filter.upper())

        if status_filter:
            query = query.filter(WeeklySummary.status == status_filter)

        results = query.all()

        reports = []
        for emp, summary in results:
            work_mode = (emp.work_mode or 'WFO').upper()
            mode_config = self.work_mode_config.get(work_mode, self.work_mode_config['WFO'])

            # For WFH employees, compliance is always 100%
            if mode_config.get('always_compliant'):
                compliance = 100.0
                status_val = 'GREEN'
            else:
                compliance = min(summary.compliance_percentage, 100.0) if summary else 0  # Cap at 100%
                status_val = summary.status.value if summary else 'RED'

            required_days = mode_config['required_days']
            expected_weekly_hours = mode_config['expected_weekly_hours']

            report = {
                'employee_code': emp.code,
                'employee_name': emp.name,
                'email': emp.email,
                'department': emp.department,
                'work_mode': work_mode,
                'total_office_hours': self._format_minutes(summary.total_office_minutes) if summary else '0h 0m',
                'total_office_minutes': summary.total_office_minutes if summary else 0,
                'wfo_days': summary.wfo_days if summary else 0,
                'required_wfo_days': required_days,
                'expected_hours': f"{expected_weekly_hours}h 0m",
                'expected_minutes': expected_weekly_hours * 60,
                'compliance_percentage': compliance,
                'status': status_val,
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
        """Generate detailed report for a single employee"""
        employee = self.db.query(Employee).filter(
            Employee.code == employee_code
        ).first()

        if not employee:
            return None

        work_mode = (employee.work_mode or 'WFO').upper()
        mode_config = self.work_mode_config.get(work_mode, self.work_mode_config['WFO'])

        query = self.db.query(DailyAttendance).filter(
            DailyAttendance.employee_code == employee_code
        )

        if start_date:
            query = query.filter(DailyAttendance.date >= start_date)
        if end_date:
            query = query.filter(DailyAttendance.date <= end_date)

        daily_records = query.order_by(DailyAttendance.date.desc()).all()

        # Filter weekly summaries by date range too
        weekly_query = self.db.query(WeeklySummary).filter(
            WeeklySummary.employee_code == employee_code
        )
        if start_date:
            weekly_query = weekly_query.filter(WeeklySummary.week_start >= start_date)
        if end_date:
            weekly_query = weekly_query.filter(WeeklySummary.week_end <= end_date)

        weekly_summaries = weekly_query.order_by(WeeklySummary.week_start.desc()).all()

        total_office_minutes = sum(d.total_office_minutes for d in daily_records)

        expected_daily_minutes = mode_config['hours_per_day'] * 60

        # Calculate days as floor(total_minutes / expected_daily_minutes)
        # e.g. 29h27m = 1767 min / 540 = 3 days
        if expected_daily_minutes > 0:
            total_wfo_days = total_office_minutes // expected_daily_minutes
        else:
            total_wfo_days = 0

        # Format daily records
        daily_data = []
        for record in daily_records:
            pairs = json.loads(record.in_out_pairs) if record.in_out_pairs else []

            if expected_daily_minutes > 0:
                daily_compliance = min((record.total_office_minutes / expected_daily_minutes) * 100, 100.0)  # Cap at 100%
            else:
                daily_compliance = 100.0 if mode_config.get('always_compliant') else 0

            daily_status_color = get_status_color(daily_compliance)

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

        # Format weekly summaries — each week has its own compliance
        weekly_data = []
        for summary in weekly_summaries:
            # Override compliance for WFH
            if mode_config.get('always_compliant'):
                w_compliance = 100.0
                w_status = 'GREEN'
            else:
                w_compliance = min(summary.compliance_percentage, 100.0)  # Cap at 100%
                w_status = summary.status.value

            weekly_data.append({
                'week_start': summary.week_start.isoformat(),
                'week_end': summary.week_end.isoformat(),
                'week_label': f"{summary.week_start.strftime('%d %b')} - {summary.week_end.strftime('%d %b %Y')}",
                'total_hours': self._format_minutes(summary.total_office_minutes),
                'total_minutes': summary.total_office_minutes,
                'wfo_days': summary.wfo_days,
                'required_wfo_days': mode_config['required_days'],
                'compliance_percentage': w_compliance,
                'status': w_status
            })

        # Average compliance is computed over the filtered weeks only
        avg_compliance = sum(w['compliance_percentage'] for w in weekly_data) / len(weekly_data) if weekly_data else 0

        return {
            'employee': {
                'code': employee.code,
                'name': employee.name,
                'email': employee.email,
                'department': employee.department,
                'work_mode': work_mode
            },
            'summary': {
                'total_office_hours': self._format_minutes(total_office_minutes),
                'total_wfo_days': total_wfo_days,
                'avg_compliance': round(avg_compliance, 2),
                'overall_status': get_status_color(avg_compliance)
            },
            'daily_records': daily_data,
            'weekly_summaries': weekly_data
        }

    def get_wfo_compliance_report(
        self,
        week_start: Optional[date] = None
    ) -> Dict:
        """Generate WFO compliance report"""
        if not week_start:
            week_start = self.db.query(func.max(WeeklySummary.week_start)).scalar()

        if not week_start:
            return {
                'week_start': None,
                'week_end': None,
                'employees': [],
                'summary': {
                    'total_employees': 0,
                    'compliant': 0,
                    'non_compliant': 0,
                    'compliance_rate': 0
                }
            }

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
            work_mode = (employee.work_mode or 'WFO').upper()
            mode_config = self.work_mode_config.get(work_mode, self.work_mode_config['WFO'])

            if mode_config.get('always_compliant'):
                compliance = 100.0
                is_compliant = True
                status_val = 'GREEN'
            else:
                compliance = min(summary.compliance_percentage, 100.0)  # Cap at 100%
                is_compliant = compliance >= self.dynamic_settings['threshold_red']
                status_val = summary.status.value

            if is_compliant:
                compliant_count += 1

            employees.append({
                'employee_code': employee.code,
                'employee_name': employee.name,
                'work_mode': work_mode,
                'wfo_days': summary.wfo_days,
                'actual_hours': self._format_minutes(summary.total_office_minutes),
                'actual_minutes': summary.total_office_minutes,
                'expected_hours': self._format_minutes(mode_config['expected_weekly_hours'] * 60),
                'expected_minutes': mode_config['expected_weekly_hours'] * 60,
                'compliance_percentage': compliance,
                'status': status_val,
                'is_compliant': is_compliant
            })

        total_employees = len(employees)
        compliance_rate = (compliant_count / total_employees * 100) if total_employees > 0 else 0

        week_end = week_start + timedelta(days=6)

        return {
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'week_label': f"{week_start.strftime('%d %b')} - {week_end.strftime('%d %b %Y')}",
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
            week_start = self.db.query(func.max(WeeklySummary.week_start)).scalar()

        if not week_start:
            return {'dates': [], 'wfo': [], 'wfh': [], 'week_label': ''}

        week_end = week_start + timedelta(days=6)

        total_employees = self.db.query(Employee).count()

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
        status_category: str
    ) -> List[Dict]:
        """Get list of employees for specific day and status"""
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()

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

            if status_category == 'WFO' and is_present:
                results.append({
                    'employee_code': emp.code,
                    'employee_name': emp.name,
                    'department': emp.department,
                    'work_mode': emp.work_mode or 'WFO',
                    'status': 'PRESENT',
                    'hours': self._format_minutes(record.total_office_minutes),
                    'in_time': record.first_in.strftime('%H:%M') if record.first_in else '-',
                    'out_time': record.last_out.strftime('%H:%M') if record.last_out else '-'
                })
            elif status_category == 'WFH' and not is_present:
                results.append({
                    'employee_code': emp.code,
                    'employee_name': emp.name,
                    'department': emp.department,
                    'work_mode': emp.work_mode or 'WFO',
                    'status': 'WFH/ABSENT',
                    'hours': '0h 0m',
                    'in_time': '-',
                    'out_time': '-'
                })

        return results
