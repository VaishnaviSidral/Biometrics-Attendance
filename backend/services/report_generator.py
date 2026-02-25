"""
Report Generator Service
Generates various attendance reports for HR dashboard.
Supports work_mode based compliance (WFO / HYBRID / WFH).
Uses dynamic settings from DB for all compliance calculations.

Compliance Philosophy:
  Daily compliance status is the SINGLE SOURCE OF TRUTH.
  Weekly and monthly compliance are aggregations of daily statuses,
  NOT aggregations of hours.
"""
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import json
import logging

from models.employee import Employee
from models.attendance import DailyAttendance, WeeklySummary, ComplianceStatus
from services.time_calculator import build_work_mode_config, TimeCalculator

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate attendance reports"""

    def __init__(self, db: Session):
        self.db = db
        # Load dynamic settings and build config once per request
        self._dynamic_settings = None
        self._work_mode_config = None
        self._calculator = None

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

    @property
    def calculator(self) -> TimeCalculator:
        """Lazy-load TimeCalculator with dynamic settings"""
        if self._calculator is None:
            ds = self.dynamic_settings
            self._calculator = TimeCalculator(
                expected_hours_per_day=ds['expected_hours_per_day'],
                wfo_days_per_week=ds['wfo_days_per_week'],
                hybrid_days_per_week=ds['hybrid_days_per_week'],
                compliance_hours=ds['compliance_hours'],
                mid_compliance_hours=ds['mid_compliance_hours'],
                non_compliance_hours=ds['non_compliance_hours']
            )
        return self._calculator

    def _get_daily_compliance_status(self, total_minutes: int, is_present: bool,
                                      is_wfh: bool = False) -> str:
        """
        Get daily compliance status using the rule engine.
        This is the SINGLE SOURCE OF TRUTH.
        """
        return self.calculator.compute_daily_compliance_status(
            total_minutes, is_present, is_wfh
        )

    def _aggregate_daily_statuses(self, daily_status_list: List[str]) -> str:
        """
        Aggregate daily compliance statuses into period status.
        Uses strict rule: ANY Non-Compliance → Non-Compliance.
        """
        return TimeCalculator.aggregate_compliance_statuses(daily_status_list)

    def _get_compliance_pct_for_display(self, total_minutes: int, expected_minutes: int) -> float:
        """
        Get compliance percentage for UI display ONLY.
        This is NOT used for determining compliance status.
        """
        if expected_minutes > 0:
            return min((total_minutes / expected_minutes) * 100, 100.0)
        return 100.0

    def get_dashboard_summary(self) -> Dict:
        """Get summary statistics for dashboard"""
        total_employees = self.db.query(Employee).filter(Employee.status == 1).count()

        # Count by work_mode
        work_mode_counts = {}
        for mode in ['WFO', 'HYBRID', 'WFH']:
            count = self.db.query(Employee).filter(Employee.work_mode == mode, Employee.status == 1).count()
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

            # Use daily status aggregation for compliance
            total_compliance = 0
            status_counts = {'Non-Compliance': 0, 'Mid-Compliance': 0, 'Compliance': 0}
            total_wfo_days = 0
            valid_count = 0

            for s in weekly_summaries:
                emp = self.db.query(Employee).filter(Employee.code == s.employee_code, Employee.status == 1).first()
                if not emp:
                    continue
                work_mode = (emp.work_mode or 'WFO').upper()
                mode_config = self.work_mode_config.get(work_mode, self.work_mode_config['WFO'])

                if mode_config.get('always_compliant'):
                    compliance = 100.0
                    status_val = 'Compliance'
                else:
                    # Get daily statuses for this employee for this week
                    daily_records = self.db.query(DailyAttendance).filter(
                        and_(
                            DailyAttendance.employee_code == s.employee_code,
                            DailyAttendance.date >= week_start,
                            DailyAttendance.date <= week_end,
                        )
                    ).all()

                    daily_statuses = []
                    for dr in daily_records:
                        if dr.date.weekday() < 5:  # weekdays only
                            if dr.compliance_status:
                                daily_statuses.append(dr.compliance_status.value)
                            else:
                                # Fallback: compute from rule engine
                                cs = self._get_daily_compliance_status(
                                    dr.total_office_minutes,
                                    dr.total_office_minutes > 0 or dr.first_in is not None,
                                    False
                                )
                                daily_statuses.append(cs)

                    status_val = self._aggregate_daily_statuses(daily_statuses)
                    # Percentage for display only
                    expected_minutes = mode_config.get('expected_weekly_hours', 0) * 60
                    compliance = self._get_compliance_pct_for_display(s.total_office_minutes, expected_minutes)

                total_compliance += compliance
                status_counts[status_val] += 1
                total_wfo_days += s.wfo_days
                valid_count += 1

            avg_compliance = total_compliance / valid_count if valid_count else 0
        else:
            week_start = None
            week_end = None
            avg_compliance = 0
            status_counts = {'Non-Compliance': 0, 'Mid-Compliance': 0, 'Compliance': 0}
            total_wfo_days = 0

        return {
            'total_employees': total_employees,
            'work_mode_counts': work_mode_counts,
            'avg_compliance': round(avg_compliance, 2),
            'status_distribution': status_counts,
            'total_wfo_days': total_wfo_days,
            'week_start': week_start.isoformat() if week_start else None,
            'week_end': week_end.isoformat() if week_end else None,
            'alerts': status_counts.get('Non-Compliance', 0)
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
        Compliance status is aggregated from daily statuses, not hours.
        Only active employees (status=1).
        """
        if week_start:
            query = self.db.query(Employee, WeeklySummary).outerjoin(
                WeeklySummary,
                and_(
                    WeeklySummary.employee_code == Employee.code,
                    WeeklySummary.week_start == week_start
                )
            )
            actual_week_start = week_start
        else:
            latest = self.db.query(func.max(WeeklySummary.week_start)).scalar()
            actual_week_start = latest
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

        # Only active employees
        query = query.filter(Employee.status == 1)

        # Filter by work_mode
        if work_mode_filter:
            query = query.filter(Employee.work_mode == work_mode_filter.upper())

        if status_filter:
            query = query.filter(WeeklySummary.status == status_filter)

        results = query.all()

        # Get the week_end for daily status lookup
        week_end = (actual_week_start + timedelta(days=6)) if actual_week_start else None

        reports = []
        for emp, summary in results:
            work_mode = (emp.work_mode or 'WFO').upper()
            mode_config = self.work_mode_config.get(work_mode, self.work_mode_config['WFO'])

            total_minutes = summary.total_office_minutes if summary else 0
            wfo_days = summary.wfo_days if summary else 0

            # For WFH employees, compliance is always 100%
            if mode_config.get('always_compliant'):
                compliance = 100.0
                status_val = 'Compliance'
            else:
                # Get daily compliance statuses from DailyAttendance
                if actual_week_start and week_end:
                    daily_records = self.db.query(DailyAttendance).filter(
                        and_(
                            DailyAttendance.employee_code == emp.code,
                            DailyAttendance.date >= actual_week_start,
                            DailyAttendance.date <= week_end
                        )
                    ).all()

                    daily_statuses = []
                    for dr in daily_records:
                        if dr.date.weekday() < 5:
                            if dr.compliance_status:
                                daily_statuses.append(dr.compliance_status.value)
                            else:
                                cs = self._get_daily_compliance_status(
                                    dr.total_office_minutes,
                                    dr.total_office_minutes > 0 or dr.first_in is not None,
                                    False
                                )
                                daily_statuses.append(cs)

                    status_val = self._aggregate_daily_statuses(daily_statuses)
                else:
                    status_val = 'Non-Compliance'

                # Percentage for display only
                expected_minutes = mode_config.get('expected_weekly_hours', 0) * 60
                compliance = self._get_compliance_pct_for_display(total_minutes, expected_minutes)

            required_days = mode_config['required_days']
            expected_weekly_hours = mode_config['expected_weekly_hours']

            report = {
                'employee_code': emp.code,
                'employee_name': emp.name,
                'email': emp.email,
                'department': emp.department,
                'work_mode': work_mode,
                'total_office_hours': self._format_minutes(total_minutes),
                'total_office_minutes': total_minutes,
                'wfo_days': wfo_days,
                'required_wfo_days': required_days,
                'expected_hours': f"{expected_weekly_hours}h 0m",
                'expected_minutes': expected_weekly_hours * 60,
                'compliance_percentage': round(compliance, 2),
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
            status_order = {'Compliance': 3, 'Mid-Compliance': 2, 'Non-Compliance': 1}
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
        is_wfh = mode_config.get('always_compliant', False)

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
        if start_date and end_date:
            weekly_query = weekly_query.filter(
                WeeklySummary.week_start <= end_date,
                WeeklySummary.week_end >= start_date
            )

        weekly_summaries = weekly_query.order_by(WeeklySummary.week_start.desc()).all()

        total_office_minutes = sum(d.total_office_minutes for d in daily_records)

        expected_daily_minutes = mode_config['hours_per_day'] * 60

        # Calculate days as floor(total_minutes / expected_daily_minutes)
        if expected_daily_minutes > 0:
            total_wfo_days = total_office_minutes // expected_daily_minutes
        else:
            total_wfo_days = 0

        # Format daily records with compliance_status from DB
        daily_data = []
        all_daily_statuses = []  # collect for overall compliance aggregation
        for record in daily_records:
            pairs = json.loads(record.in_out_pairs) if record.in_out_pairs else []

            # Daily compliance percentage (for display only)
            if expected_daily_minutes > 0:
                daily_compliance = min((record.total_office_minutes / expected_daily_minutes) * 100, 100.0)
            else:
                daily_compliance = 100.0 if is_wfh else 0

            # Use stored compliance_status (single source of truth)
            if record.compliance_status:
                daily_status_color = record.compliance_status.value
            else:
                # Fallback for records without compliance_status
                is_present = record.total_office_minutes > 0 or record.first_in is not None
                daily_status_color = self._get_daily_compliance_status(
                    record.total_office_minutes, is_present, is_wfh
                )

            # Collect weekday statuses for overall aggregation
            if record.date.weekday() < 5:
                all_daily_statuses.append(daily_status_color)

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

        # Format weekly summaries — compliance from daily status aggregation
        weekly_data = []
        for summary in weekly_summaries:
            if is_wfh:
                w_compliance = 100.0
                w_status = 'Compliance'
            else:
                # Get daily statuses for this week
                week_daily = self.db.query(DailyAttendance).filter(
                    and_(
                        DailyAttendance.employee_code == employee_code,
                        DailyAttendance.date >= summary.week_start,
                        DailyAttendance.date <= summary.week_end
                    )
                ).all()

                week_daily_statuses = []
                for dr in week_daily:
                    if dr.date.weekday() < 5:
                        if dr.compliance_status:
                            week_daily_statuses.append(dr.compliance_status.value)
                        else:
                            cs = self._get_daily_compliance_status(
                                dr.total_office_minutes,
                                dr.total_office_minutes > 0 or dr.first_in is not None,
                                False
                            )
                            week_daily_statuses.append(cs)

                w_status = self._aggregate_daily_statuses(week_daily_statuses)
                # Percentage for display only
                expected_minutes = mode_config.get('expected_weekly_hours', 0) * 60
                w_compliance = self._get_compliance_pct_for_display(summary.total_office_minutes, expected_minutes)

            weekly_data.append({
                'week_start': summary.week_start.isoformat(),
                'week_end': summary.week_end.isoformat(),
                'week_label': f"{summary.week_start.strftime('%d %b')} - {summary.week_end.strftime('%d %b %Y')}",
                'total_hours': self._format_minutes(summary.total_office_minutes),
                'total_minutes': summary.total_office_minutes,
                'wfo_days': summary.wfo_days,
                'required_wfo_days': mode_config['required_days'],
                'compliance_percentage': round(w_compliance, 2),
                'status': w_status
            })

        # Overall compliance = aggregation of daily statuses
        if is_wfh:
            overall_status = 'Compliance'
            avg_compliance = 100.0
        else:
            overall_status = self._aggregate_daily_statuses(all_daily_statuses)
            # Avg compliance percentage for display only
            total_presence_days = sum(
                1 for d in daily_records
                if d.total_office_minutes > 0 and d.date.weekday() < 5
            )
            expected_period_minutes = total_presence_days * expected_daily_minutes if expected_daily_minutes > 0 else 0
            avg_compliance = self._get_compliance_pct_for_display(total_office_minutes, expected_period_minutes)

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
                'overall_status': overall_status
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

        week_end = week_start + timedelta(days=6)

        summaries = self.db.query(
            WeeklySummary, Employee
        ).join(
            Employee, WeeklySummary.employee_code == Employee.code
        ).filter(
            WeeklySummary.week_start == week_start,
            Employee.status == 1
        ).all()

        employees = []
        compliant_count = 0

        for summary, employee in summaries:
            work_mode = (employee.work_mode or 'WFO').upper()
            mode_config = self.work_mode_config.get(work_mode, self.work_mode_config['WFO'])

            if mode_config.get('always_compliant'):
                compliance = 100.0
                is_compliant = True
                status_val = 'Compliance'
            else:
                # Get daily statuses for this employee for this week
                daily_records = self.db.query(DailyAttendance).filter(
                    and_(
                        DailyAttendance.employee_code == employee.code,
                        DailyAttendance.date >= week_start,
                        DailyAttendance.date <= week_end
                    )
                ).all()

                daily_statuses = []
                for dr in daily_records:
                    if dr.date.weekday() < 5:
                        if dr.compliance_status:
                            daily_statuses.append(dr.compliance_status.value)
                        else:
                            cs = self._get_daily_compliance_status(
                                dr.total_office_minutes,
                                dr.total_office_minutes > 0 or dr.first_in is not None,
                                False
                            )
                            daily_statuses.append(cs)

                status_val = self._aggregate_daily_statuses(daily_statuses)
                is_compliant = status_val == 'Compliance'
                # Percentage for display only
                expected_minutes = mode_config.get('expected_weekly_hours', 0) * 60
                compliance = self._get_compliance_pct_for_display(summary.total_office_minutes, expected_minutes)

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
                'compliance_percentage': round(compliance, 2),
                'status': status_val,
                'is_compliant': is_compliant
            })

        total_employees = len(employees)
        compliance_rate = (compliant_count / total_employees * 100) if total_employees > 0 else 0

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
        Compliance is based on daily status aggregation, not hours.
        """
        if not week_start:
            week_start = self.db.query(func.max(WeeklySummary.week_start)).scalar()

        all_employees = self.db.query(Employee).filter(Employee.status == 1).all()
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

        week_end = week_start + timedelta(days=6)

        # Get weekly summaries for the selected week
        summaries = {
            s.employee_code: s
            for s in self.db.query(WeeklySummary).filter(
                WeeklySummary.week_start == week_start
            ).all()
        }

        compliant = 0
        mid_compliant = 0
        non_compliant = 0

        for emp in non_exempt_employees:
            summary = summaries.get(emp.code)

            if summary:
                # Get daily statuses for this employee for this week
                daily_records = self.db.query(DailyAttendance).filter(
                    and_(
                        DailyAttendance.employee_code == emp.code,
                        DailyAttendance.date >= week_start,
                        DailyAttendance.date <= week_end
                    )
                ).all()

                daily_statuses = []
                for dr in daily_records:
                    if dr.date.weekday() < 5:
                        if dr.compliance_status:
                            daily_statuses.append(dr.compliance_status.value)
                        else:
                            cs = self._get_daily_compliance_status(
                                dr.total_office_minutes,
                                dr.total_office_minutes > 0 or dr.first_in is not None,
                                False
                            )
                            daily_statuses.append(cs)

                status = self._aggregate_daily_statuses(daily_statuses)
                if status == 'Compliance':
                    compliant += 1
                elif status == 'Mid-Compliance':
                    mid_compliant += 1
                else:
                    non_compliant += 1
            else:
                non_compliant += 1  # No data = non-compliant

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

        total_employees = self.db.query(Employee).filter(Employee.status == 1).count()

        # Presence = total_office_minutes > 0 (biometric reality)
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

    def get_monthly_report(self, month: str, search: Optional[str] = None, work_mode: Optional[str] = None):
        """
        Month format: YYYY-MM
        Compliance logic = DAY BASED using daily compliance_status.
        Monthly compliance is aggregation of daily statuses, NOT hours.

        Rules:
          - If ANY Non-Compliance day → Monthly = "Non-Compliance"
          - Else if ANY Mid-Compliance day → Monthly = "Mid-Compliance"
          - Else → Monthly = "Compliance"
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

        # Use dynamic settings
        ds = self.dynamic_settings
        wfo_days_per_week = ds['wfo_days_per_week']
        hybrid_days_per_week = ds['hybrid_days_per_week']
        compliance_hours = ds['compliance_hours']
        mid_compliance_hours = ds['mid_compliance_hours']

        # Calculate required days for the month proportional to working days
        weeks_in_month = working_days / 5.0 if working_days > 0 else 0
        wfo_required = round(weeks_in_month * wfo_days_per_week)
        hybrid_required = round(weeks_in_month * hybrid_days_per_week)

        # Get all active employees (optionally filtered)
        emp_query = self.db.query(Employee).filter(Employee.status == 1)

        if search:
            search_term = f"%{search}%"
            emp_query = emp_query.filter(
                (Employee.name.ilike(search_term)) |
                (Employee.code.ilike(search_term))
            )
        if work_mode:
            emp_query = emp_query.filter(Employee.work_mode.ilike(work_mode))
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
            # Total office minutes for the month
            total_office_minutes = sum(r.total_office_minutes or 0 for r in records)
            total_office_hours = total_office_minutes / 60.0

            # Days below required daily hours
            days_below_required_hours = 0
            for r in records:
                daily_minutes = r.total_office_minutes or 0
                daily_hours = daily_minutes / 60.0
                if daily_minutes > 0 and daily_hours < compliance_hours:
                    days_below_required_hours += 1

            # ── COMPLIANCE: Aggregation from daily statuses ──
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

                # Collect daily compliance statuses for weekdays
                daily_statuses = []
                for r in records:
                    if r.date.weekday() < 5:
                        if r.compliance_status:
                            daily_statuses.append(r.compliance_status.value)
                        else:
                            # Fallback: compute from rule engine
                            is_present = (r.total_office_minutes or 0) > 0 or r.first_in is not None
                            cs = self._get_daily_compliance_status(
                                r.total_office_minutes or 0, is_present, False
                            )
                            daily_statuses.append(cs)

                # Aggregate: ANY Non-Compliance → Monthly Non-Compliance
                compliance_status = self._aggregate_daily_statuses(daily_statuses)

                # Percentage for display only
                expected_monthly_minutes = required_days * compliance_hours * 60
                if expected_monthly_minutes > 0:
                    compliance_percentage = min((total_office_minutes / expected_monthly_minutes) * 100, 100.0)
                else:
                    compliance_percentage = 100.0

            final.append({
                "employee_code": emp.code,
                "employee_name": emp.name,
                "department": emp.department,
                "work_mode": work_mode,
                "exempted": is_exempted,
                "total_wfo_days": wfo_days,
                "total_wfh_days": wfh_days,
                "days_below_required_hours": days_below_required_hours,
                "total_office_hours": round(total_office_hours, 1),
                "avg_daily_hours": round(total_office_hours / wfo_days, 1) if wfo_days > 0 else 0,
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
        NOT on the compliance rule.
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

        results = []
        all_employees = self.db.query(Employee).filter(Employee.status == 1).all()

        for emp in all_employees:
            record = present_employees.get(emp.code)
            is_present = record is not None

            if status_category == 'WFO' and is_present:
                minutes = record.total_office_minutes or 0

                # Use stored compliance_status or compute from rule engine
                if record.compliance_status:
                    compliance_label = record.compliance_status.value
                else:
                    work_mode = (emp.work_mode or 'WFO').upper()
                    is_wfh = work_mode == 'WFH'
                    compliance_label = self._get_daily_compliance_status(minutes, True, is_wfh)

                results.append({
                    'employee_code': emp.code,
                    'employee_name': emp.name,
                    'department': emp.department,
                    'work_mode': emp.work_mode or 'WFO',
                    'status': 'PRESENT',
                    'compliance_label': compliance_label,
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
                    'compliance_label': 'Non-Compliance',
                    'hours': '0h 0m',
                    'in_time': '-',
                    'out_time': '-'
                })

        return results
