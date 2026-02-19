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
        print("\n====== DEBUG: DAILY RECORDS FETCHED ======")
        print("EMP:", employee_code)
        for r in daily_records:
            print("DATE:", r.date,
                "| MINUTES:", r.total_office_minutes,
                "| FIRST_IN:", r.first_in,
                "| LAST_OUT:", r.last_out,
                "| DB_STATUS:", getattr(r.status, "value", r.status))
        print("========================================\n")
        # Filter weekly summaries by date range too
        weekly_query = self.db.query(WeeklySummary).filter(
            WeeklySummary.employee_code == employee_code
        )
        if start_date and end_date:
            weekly_query = weekly_query.filter(
                WeeklySummary.week_start <= end_date,
                WeeklySummary.week_end >= start_date
            )

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
            print("DEBUG LOOP ->",
                "DATE:", record.date,
                "| MINUTES:", record.total_office_minutes,
                "| CALC_STATUS:",
                "PRESENT" if record.total_office_minutes > 0 else "ABSENT")

            daily_data.append({
                'date': record.date.isoformat(),
                'day': record.date.strftime('%A'),
                'first_in': record.first_in.strftime('%H:%M') if record.first_in else '-',
                'last_out': record.last_out.strftime('%H:%M') if record.last_out else '-',
                'in_out_pairs': pairs,
                'total_hours': self._format_minutes(record.total_office_minutes),
                'total_minutes': record.total_office_minutes,
                'status': "PRESENT" if record.total_office_minutes > 0 else "ABSENT",
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

    def get_weekly_compliance_stats(
        self,
        week_start: Optional[date] = None
    ) -> Dict:
        """
        Get weekly compliance stats for dashboard cards.
        Returns:
        - total_employees: all employees in the system
        - non_exempt_employees: WFO + HYBRID employees (not WFH)
        - compliant_employees: non-exempt employees meeting WFO policy (GREEN status)
        - non_compliant_employees: non-exempt employees NOT meeting WFO policy (AMBER/RED)
        
        Compliance is based on policy rules (9-hour, required days), NOT presence.
        """
        if not week_start:
            week_start = self.db.query(func.max(WeeklySummary.week_start)).scalar()

        all_employees = self.db.query(Employee).all()
        total = len(all_employees)

        non_exempt_employees = [e for e in all_employees if (e.work_mode or 'WFO').upper() != 'WFH']
        non_exempt_count = len(non_exempt_employees)

        if not week_start:
            return {
                'total_employees': total,
                'non_exempt_employees': non_exempt_count,
                'compliant_employees': 0,
                'non_compliant_employees': non_exempt_count,
                'week_start': None,
                'week_end': None
            }

        # Get weekly summaries for the selected week
        summaries = {
            s.employee_code: s
            for s in self.db.query(WeeklySummary).filter(
                WeeklySummary.week_start == week_start
            ).all()
        }

        threshold_amber = self.dynamic_settings['threshold_amber']  # GREEN threshold (90%)

        compliant = 0
        mid_compliant = 0
        non_compliant = 0

        for emp in non_exempt_employees:
            summary = summaries.get(emp.code)

            if summary:
                compliance = min(summary.compliance_percentage, 100.0)

                if compliance >= 90:
                    compliant += 1                    # GREEN
                elif compliance >= 60:
                    mid_compliant += 1                # AMBER
                else:
                    non_compliant += 1                # RED
            else:
                non_compliant += 1                    # No data = non-compliant


        week_end = week_start + timedelta(days=6)

        return {
            'total_employees': total,
            'non_exempt_employees': non_exempt_count,
            'compliant_employees': compliant,
            'partial_compliant_employees': mid_compliant,
            'non_compliant_employees': non_compliant,
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat()
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

        # Presence = total_office_minutes > 0 (biometric reality)
        # NOT based on 9-hour compliance rule
        daily_counts = self.db.query(
            DailyAttendance.date,
            func.count(DailyAttendance.id)
        ).filter(
            and_(
                DailyAttendance.date >= week_start,
                DailyAttendance.date <= week_end,
                DailyAttendance.total_office_minutes > 0
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

    def get_available_months(self) -> List[Dict]:
        """Get list of available months from daily attendance data"""
        months = self.db.query(
            func.date_format(DailyAttendance.date, '%Y-%m').label('month')
        ).distinct().order_by(
            func.date_format(DailyAttendance.date, '%Y-%m').desc()
        ).all()

        result = []
        for row in months:
            month_str = row.month
            try:
                dt = datetime.strptime(month_str, '%Y-%m')
                result.append({
                    'value': month_str,
                    'label': dt.strftime('%B %Y')
                })
            except Exception:
                result.append({
                    'value': month_str,
                    'label': month_str
                })
        return result

    def get_monthly_report(self, month: str, search: Optional[str] = None):
        """
        Month format: YYYY-MM
        Compliance logic = DAY BASED using dynamic settings.
        Shows ALL employees (even those with 0 attendance records).
        Search filters by employee name or code (ILIKE).
        """
        import calendar as cal_mod

        year, mon = map(int, month.split("-"))
        start_date = date(year, mon, 1)
        _, days_in_month = cal_mod.monthrange(year, mon)
        end_date = date(year, mon, days_in_month)

        # Calculate working days (Mon-Fri) in the month
        working_days = 0
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                working_days += 1
            current += timedelta(days=1)

        # Use dynamic settings for required days
        ds = self.dynamic_settings
        wfo_days_per_week = ds['wfo_days_per_week']       # e.g. 5
        hybrid_days_per_week = ds['hybrid_days_per_week']  # e.g. 3
        threshold_red = ds['threshold_red']                # e.g. 60
        threshold_amber = ds['threshold_amber']            # e.g. 90

        # Calculate required days for the month proportional to working days
        # working_days represents full weekdays; scale by required per week
        weeks_in_month = working_days / 5.0 if working_days > 0 else 0
        wfo_required = round(weeks_in_month * wfo_days_per_week)
        hybrid_required = round(weeks_in_month * hybrid_days_per_week)

        # Get all employees (optionally filtered by search)
        emp_query = self.db.query(Employee)

        if search:
            search_term = f"%{search}%"
            emp_query = emp_query.filter(
                (Employee.name.ilike(search_term)) |
                (Employee.code.ilike(search_term))
            )
        all_employees = emp_query.order_by(Employee.name).all()

        # Get all daily attendance records for this month
        daily_records = self.db.query(DailyAttendance).filter(
            and_(
                DailyAttendance.date >= start_date,
                DailyAttendance.date <= end_date
            )
        ).all()

        # Build lookup: employee_code -> list of daily records
        emp_daily_map = {}
        for rec in daily_records:
            emp_daily_map.setdefault(rec.employee_code, []).append(rec)

        final = []
        for emp in all_employees:
            work_mode = (emp.work_mode or "WFO").upper()
            is_exempted = work_mode == "WFH"

            records = emp_daily_map.get(emp.code, [])

            # WFO Day = total_office_minutes > 0
            wfo_days = sum(1 for r in records if (r.total_office_minutes or 0) > 0)
            # WFH Day = working_days - wfo_days
            wfh_days = working_days - wfo_days

            # Compliance calculation (DAY BASED using dynamic settings)
            if is_exempted:
                compliance_percentage = 100.0
                compliance_status = "Compliance"
                required_days = 0
            else:
                if work_mode == "WFO":
                    required_days = wfo_required
                elif work_mode == "HYBRID":
                    required_days = hybrid_required
                else:
                    required_days = wfo_required

                if required_days > 0:
                    compliance_percentage = (wfo_days / required_days) * 100
                else:
                    compliance_percentage = 100.0

                compliance_percentage = min(compliance_percentage, 100.0)

                if compliance_percentage >= threshold_amber:
                    compliance_status = "Compliance"
                elif compliance_percentage >= threshold_red:
                    compliance_status = "Mid-Compliance"
                else:
                    compliance_status = "Non-Compliance"

            final.append({
                "employee_code": emp.code,
                "employee_name": emp.name,
                "department": emp.department,
                "work_mode": work_mode,
                "exempted": is_exempted,
                "total_wfo_days": wfo_days,
                "total_wfh_days": wfh_days,
                "required_days": required_days,
                "working_days": working_days,
                "compliance_percentage": round(compliance_percentage, 2),
                "compliance_status": compliance_status
            })

        return final


    def get_daily_details(
        self,
        date_str: str,
        status_category: str
    ) -> List[Dict]:
        """Get list of employees for specific day and status.
        
        Presence is based on biometric reality (total_office_minutes > 0 OR first_in exists),
        NOT on the 9-hour compliance rule.
        Compliance label is added separately for policy reporting.
        """
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        daily_records = self.db.query(
            DailyAttendance
        ).filter(
            DailyAttendance.date == target_date
        ).all()

        # Presence = biometric reality: any minutes > 0 OR any in_time recorded
        present_employees = {
            d.employee_code: d for d in daily_records
            if d.total_office_minutes > 0 or d.first_in is not None
        }

        # Get expected daily minutes for compliance label
        expected_daily_minutes = self.dynamic_settings['expected_hours_per_day'] * 60

        results = []
        all_employees = self.db.query(Employee).all()

        for emp in all_employees:
            record = present_employees.get(emp.code)
            is_present = record is not None

            if status_category == 'WFO' and is_present:
                # Compliance label: 9-hour rule is ONLY for compliance, not presence
                minutes = record.total_office_minutes or 0
                is_compliant = minutes >= expected_daily_minutes
                results.append({
                    'employee_code': emp.code,
                    'employee_name': emp.name,
                    'department': emp.department,
                    'work_mode': emp.work_mode or 'WFO',
                    'status': 'PRESENT',
                    'compliance_label': 'Compliant' if is_compliant else 'Non-Compliant',
                    'hours': self._format_minutes(minutes),
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
                    'compliance_label': '-',
                    'hours': '0h 0m',
                    'in_time': '-',
                    'out_time': '-'
                })

        return results
