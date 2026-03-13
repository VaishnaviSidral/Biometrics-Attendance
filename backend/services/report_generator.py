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
from typing import List, Dict, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import json
import logging

from models.employee import Employee
from models.attendance import DailyAttendance, WeeklySummary, ComplianceStatus
from models.holidays import Holiday
from services.time_calculator import build_work_mode_config, TimeCalculator
from services.redmine_service import redmine_service

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate attendance reports"""

    def __init__(self, db: Session):
        self.db = db
        self._dynamic_settings = None
        self._work_mode_config = None
        self._calculator = None
        self._holidays_cache: Dict[str, bool] = {}
        self._leave_cache: Dict[str, Set[str]] = {}

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

    def _preload_holidays(self, start_date: date, end_date: date):
        """Batch-load holidays for a date range into cache."""
        cache_key = f"{start_date}_{end_date}"
        if cache_key in self._holidays_cache:
            return
        holidays = self.db.query(Holiday.date).filter(
            Holiday.date >= start_date,
            Holiday.date <= end_date
        ).all()
        for h in holidays:
            self._holidays_cache[h.date.isoformat() if isinstance(h.date, date) else str(h.date)] = True
        self._holidays_cache[cache_key] = True

    def _is_holiday_cached(self, date_str: str) -> bool:
        return self._holidays_cache.get(date_str, False)

    def _preload_leaves(self, email: str, start_date: date, end_date: date):
        """Load leave days from Redmine for a single employee into cache."""
        if not email:
            return
        cache_key = f"{email}_{start_date}_{end_date}"
        if cache_key in self._leave_cache:
            return
        try:
            leave_days = redmine_service.get_leave_days_for_period(
                email, start_date.isoformat(), end_date.isoformat()
            )
            existing = self._leave_cache.get(email, set())
            for d in leave_days:
                d_str = d.isoformat() if isinstance(d, date) else str(d)
                existing.add(d_str)
            self._leave_cache[email] = existing
            self._leave_cache[cache_key] = existing
        except Exception:
            pass

    def _batch_preload_leaves(self, emails: list, start_date: date, end_date: date):
        """Batch-load leave days for many employees in a single DB round-trip."""
        uncached = [
            e for e in emails
            if e and f"{e}_{start_date}_{end_date}" not in self._leave_cache
        ]
        if not uncached:
            return

        try:
            results = redmine_service.get_leave_days_for_employees(
                uncached, start_date.isoformat(), end_date.isoformat()
            )
            for email, leave_days in results.items():
                existing = self._leave_cache.get(email, set())
                for d in leave_days:
                    d_str = d.isoformat() if isinstance(d, date) else str(d)
                    existing.add(d_str)
                self._leave_cache[email] = existing
                self._leave_cache[f"{email}_{start_date}_{end_date}"] = existing

            for email in uncached:
                if email not in results:
                    self._leave_cache.setdefault(email, set())
                    self._leave_cache[f"{email}_{start_date}_{end_date}"] = self._leave_cache[email]
        except Exception:
            pass

    def _is_on_leave_cached(self, email: str, date_str: str) -> bool:
        if not email:
            return False
        return date_str in self._leave_cache.get(email, set())

    def _get_daily_compliance_fast(self, total_minutes: int, is_present: bool,
                                    is_wfh: bool, date_str: str,
                                    employee_email: str) -> str:
        """Fast daily compliance using pre-loaded holiday/leave caches."""
        if is_present and total_minutes > 0:
            if is_wfh:
                return "Compliance"
            daily_hours = total_minutes / 60.0
            if daily_hours >= self.calculator.compliance_hours:
                return "Compliance"
            elif daily_hours >= self.calculator.mid_compliance_hours:
                return "Mid-Compliance"
            else:
                return "Non-Compliance"

        if self._is_holiday_cached(date_str):
            return "Holiday"

        if self._is_on_leave_cached(employee_email, date_str):
            return "Leave"

        return "Non-Compliance"

    def _get_daily_compliance_status(self, total_minutes: int, is_present: bool,
                                      is_wfh: bool = False, date: str = None, 
                                      employee_email: str = None, db: Session = None) -> str:
        """Delegate to rule engine for daily compliance."""
        return self.calculator.compute_daily_compliance_status(
            total_minutes, is_present, is_wfh, date, employee_email, db
        )

    def _get_compliance_pct_for_display(self, total_minutes: int, expected_minutes: int) -> float:
        """Compliance percentage for UI display ONLY — never determines status."""
        if expected_minutes > 0:
            return min((total_minutes / expected_minutes) * 100, 100.0)
        return 100.0

    # ──────────────────────────────────────────────
    # BATCH DAILY ATTENDANCE LOADING
    # ──────────────────────────────────────────────

    def _batch_load_daily_attendance(self, start_date: date, end_date: date,
                                      employee_codes: List[str] = None) -> Dict[str, Dict[date, 'DailyAttendance']]:
        """Load all daily attendance records for a date range, grouped by employee code."""
        query = self.db.query(DailyAttendance).filter(
            and_(
                DailyAttendance.date >= start_date,
                DailyAttendance.date <= end_date,
            )
        )
        if employee_codes:
            query = query.filter(DailyAttendance.employee_code.in_(employee_codes))

        records = query.all()
        result: Dict[str, Dict[date, DailyAttendance]] = {}
        for r in records:
            result.setdefault(r.employee_code, {})[r.date] = r
        return result

    # ──────────────────────────────────────────────
    # SHARED WEEKLY COMPLIANCE HELPER (DB-aware)
    # ──────────────────────────────────────────────

    def _compute_employee_weekly_compliance(
        self, employee_code: str, week_start: date, week_end: date, work_mode: str
    ) -> Dict:
        """
        Single DB-aware helper for weekly compliance.
        Enumerates all weekdays (Mon-Fri), treats missing records as absent.
        Calls TimeCalculator.calculate_weekly_compliance() — no re-implementation.

        Returns dict with: status, compliance_percentage, present_days, daily_statuses
        """
        mode_config = self.work_mode_config.get(work_mode, self.work_mode_config['WFO'])
        is_wfh = mode_config.get('always_compliant', False)

        if is_wfh:
            return {
                'status': 'Compliance',
                'compliance_percentage': 100.0,
                'present_days': 0,
                'daily_statuses': [],
            }

        daily_records = self.db.query(DailyAttendance).filter(
            and_(
                DailyAttendance.employee_code == employee_code,
                DailyAttendance.date >= week_start,
                DailyAttendance.date <= week_end,
            )
        ).all()

        daily_map = {r.date: r for r in daily_records}

        employee = self.db.query(Employee).filter(Employee.code == employee_code).first()
        employee_email = employee.email if employee else None
        
        daily_statuses = []
        present_days = 0
        total_minutes = 0

        current = week_start
        while current <= week_end:
            if current.weekday() < 5:
                record = daily_map.get(current)
                if record:
                    mins = record.total_office_minutes or 0
                    total_minutes += mins
                    is_present = mins > 0 or record.first_in is not None
                    if is_present:
                        present_days += 1
                    if record.compliance_status:
                        daily_statuses.append(record.compliance_status.value)
                    else:
                        cs = self._get_daily_compliance_status(
                            mins, is_present, False, current.isoformat(), employee_email, self.db
                        )
                        daily_statuses.append(cs)
                else:
                    cs = self._get_daily_compliance_status(
                        0, False, False, current.isoformat(), employee_email, self.db
                    )
                    daily_statuses.append(cs)
            current += timedelta(days=1)

        status = TimeCalculator.calculate_weekly_compliance(
            daily_statuses, present_days = 0, required_days = 0, is_wfh = is_wfh
        )

        expected_minutes = mode_config.get('expected_weekly_hours', 0) * 60
        pct = self._get_compliance_pct_for_display(total_minutes, expected_minutes)

        return {
            'status': status,
            'compliance_percentage': round(pct, 2),
            'present_days': present_days,
            'daily_statuses': daily_statuses,
            'total_minutes': total_minutes,
        }

    def _compute_weekly_compliance_fast(
        self, employee_code: str, week_start: date, week_end: date,
        work_mode: str, daily_map: Dict[date, 'DailyAttendance'],
        employee_email: str = None
    ) -> Dict:
        """
        Optimized weekly compliance using pre-loaded data.
        Avoids per-employee DB queries by accepting pre-loaded daily records and caches.
        """
        mode_config = self.work_mode_config.get(work_mode, self.work_mode_config['WFO'])
        is_wfh = mode_config.get('always_compliant', False)

        if is_wfh:
            return {
                'status': 'Compliance',
                'compliance_percentage': 100.0,
                'present_days': 0,
                'daily_statuses': [],
            }

        daily_statuses = []
        present_days = 0
        total_minutes = 0

        current = week_start
        while current <= week_end:
            if current.weekday() < 5:
                record = daily_map.get(current)
                if record:
                    mins = record.total_office_minutes or 0
                    total_minutes += mins
                    is_present = mins > 0 or record.first_in is not None
                    if is_present:
                        present_days += 1
                    if record.compliance_status:
                        daily_statuses.append(record.compliance_status.value)
                    else:
                        cs = self._get_daily_compliance_fast(
                            mins, is_present, False, current.isoformat(), employee_email
                        )
                        daily_statuses.append(cs)
                else:
                    cs = self._get_daily_compliance_fast(
                        0, False, False, current.isoformat(), employee_email
                    )
                    daily_statuses.append(cs)
            current += timedelta(days=1)

        status = TimeCalculator.calculate_weekly_compliance(
            daily_statuses, present_days=0, required_days=0, is_wfh=is_wfh
        )

        expected_minutes = mode_config.get('expected_weekly_hours', 0) * 60
        pct = self._get_compliance_pct_for_display(total_minutes, expected_minutes)

        return {
            'status': status,
            'compliance_percentage': round(pct, 2),
            'present_days': present_days,
            'daily_statuses': daily_statuses,
            'total_minutes': total_minutes,
        }

    def get_dashboard_summary(self) -> Dict:
        """Get summary statistics for dashboard"""
        all_employees = self.db.query(Employee).filter(Employee.status == 1).all()
        total_employees = len(all_employees)
        emp_by_code = {e.code: e for e in all_employees}

        work_mode_counts = {}
        for mode in ['WFO', 'HYBRID', 'WFH']:
            work_mode_counts[mode] = sum(1 for e in all_employees if (e.work_mode or 'WFO').upper() == mode)

        latest_summary = self.db.query(WeeklySummary).order_by(
            WeeklySummary.week_start.desc()
        ).first()

        if latest_summary:
            week_start = latest_summary.week_start
            week_end = latest_summary.week_end

            weekly_summaries = self.db.query(WeeklySummary).filter(
                WeeklySummary.week_start == week_start
            ).all()

            emp_codes = [s.employee_code for s in weekly_summaries if emp_by_code.get(s.employee_code)]
            all_daily = self._batch_load_daily_attendance(week_start, week_end, emp_codes)
            self._preload_holidays(week_start, week_end)
            leave_emails = [
                emp_by_code[c].email for c in emp_codes
                if emp_by_code.get(c) and emp_by_code[c].email
                and (emp_by_code[c].work_mode or 'WFO').upper() != 'WFH'
            ]
            self._batch_preload_leaves(leave_emails, week_start, week_end)

            total_compliance = 0
            status_counts = {'Non-Compliance': 0, 'Mid-Compliance': 0, 'Compliance': 0, 'Leave': 0, 'Holiday': 0}
            total_wfo_days = 0
            valid_count = 0

            for s in weekly_summaries:
                emp = emp_by_code.get(s.employee_code)
                if not emp:
                    continue
                work_mode = (emp.work_mode or 'WFO').upper()
                daily_map = all_daily.get(s.employee_code, {})

                result = self._compute_weekly_compliance_fast(
                    s.employee_code, week_start, week_end, work_mode,
                    daily_map, emp.email
                )

                total_compliance += result['compliance_percentage']
                status_counts[result['status']] += 1
                total_wfo_days += s.wfo_days
                valid_count += 1

            avg_compliance = total_compliance / valid_count if valid_count else 0
        else:
            week_start = None
            week_end = None
            avg_compliance = 0
            status_counts = {'Non-Compliance': 0, 'Mid-Compliance': 0, 'Compliance': 0, 'Leave': 0, 'Holiday': 0}
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

        query = query.filter(Employee.status == 1)

        if work_mode_filter:
            query = query.filter(Employee.work_mode == work_mode_filter.upper())

        if status_filter:
            query = query.filter(WeeklySummary.status == status_filter)

        results = query.all()

        week_end = (actual_week_start + timedelta(days=6)) if actual_week_start else None

        all_daily = {}
        if actual_week_start and week_end:
            emp_codes = [emp.code for emp, _ in results]
            all_daily = self._batch_load_daily_attendance(actual_week_start, week_end, emp_codes)
            self._preload_holidays(actual_week_start, week_end)
            leave_emails = [
                emp.email for emp, _ in results
                if emp.email and (emp.work_mode or 'WFO').upper() != 'WFH'
            ]
            self._batch_preload_leaves(leave_emails, actual_week_start, week_end)

        reports = []
        for emp, summary in results:
            work_mode = (emp.work_mode or 'WFO').upper()
            mode_config = self.work_mode_config.get(work_mode, self.work_mode_config['WFO'])

            total_minutes = summary.total_office_minutes if summary else 0
            wfo_days = summary.wfo_days if summary else 0

            if actual_week_start and week_end:
                daily_map = all_daily.get(emp.code, {})
                result = self._compute_weekly_compliance_fast(
                    emp.code, actual_week_start, week_end, work_mode,
                    daily_map, emp.email
                )
                status_val = result['status']
                compliance = result['compliance_percentage']
            else:
                status_val = 'Non-Compliance'
                compliance = 0.0

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

        if expected_daily_minutes > 0:
            total_wfo_days = total_office_minutes // expected_daily_minutes
        else:
            total_wfo_days = 0

        # Preload holidays & leaves
        if start_date and end_date:
            self._preload_holidays(start_date, end_date)

            if employee.email:
                self._preload_leaves(employee.email, start_date, end_date)

        daily_data = []
        all_daily_statuses = []

        for record in daily_records:

            pairs = json.loads(record.in_out_pairs) if record.in_out_pairs else []

            if expected_daily_minutes > 0:
                daily_compliance = min(
                    (record.total_office_minutes / expected_daily_minutes) * 100,
                    100.0
                )
            else:
                daily_compliance = 100.0 if is_wfh else 0

            current_date_str = record.date.isoformat()

            # Correct holiday check
            is_holiday = self._holidays_cache.get(current_date_str, False)
            is_leave = current_date_str in getattr(self, "leaves_set", set())

            worked_today = record.total_office_minutes > 0 or record.first_in is not None

            if is_holiday and not worked_today:
                daily_status_color = "Holiday"

            elif is_leave:
                daily_status_color = "Leave"

            elif record.compliance_status:
                daily_status_color = record.compliance_status.value

            else:
                daily_status_color = self._get_daily_compliance_status(
                    record.total_office_minutes,
                    worked_today,
                    is_wfh,
                    current_date_str,
                    employee.email,
                    self.db
                )

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

        # Weekly Data

        if weekly_summaries:
            ws_start = min(s.week_start for s in weekly_summaries)
            ws_end = max(s.week_end for s in weekly_summaries)

            weekly_daily = self._batch_load_daily_attendance(
                ws_start, ws_end, [employee_code]
            )

            self._preload_holidays(ws_start, ws_end)

            if employee.email:
                self._preload_leaves(employee.email, ws_start, ws_end)

            emp_weekly_daily_map = weekly_daily.get(employee_code, {})

        else:
            emp_weekly_daily_map = {}

        weekly_data = []
        weekly_statuses_for_overall = []

        for summary in weekly_summaries:

            result = self._compute_weekly_compliance_fast(
                employee_code,
                summary.week_start,
                summary.week_end,
                work_mode,
                emp_weekly_daily_map,
                employee.email
            )

            weekly_statuses_for_overall.append(result['status'])

            weekly_data.append({
                'week_start': summary.week_start.isoformat(),
                'week_end': summary.week_end.isoformat(),
                'week_label': f"{summary.week_start.strftime('%d %b')} - {summary.week_end.strftime('%d %b %Y')}",
                'total_hours': self._format_minutes(summary.total_office_minutes),
                'total_minutes': summary.total_office_minutes,
                'wfo_days': summary.wfo_days,
                'required_wfo_days': mode_config['required_days'],
                'compliance_percentage': result['compliance_percentage'],
                'status': result['status']
            })

        # Overall Compliance

        if is_wfh:
            overall_status = 'Compliance'
            avg_compliance = 100.0

        else:

            overall_status = TimeCalculator.calculate_monthly_compliance(
                weekly_statuses_for_overall
            )

            if start_date and end_date:

                total_working_days = sum(
                    1
                    for i in range((end_date - start_date).days + 1)
                    if (
                        (start_date + timedelta(days=i)).weekday() < 5 and
                        (start_date + timedelta(days=i)).isoformat()
                        not in self._holidays_cache and
                        (start_date + timedelta(days=i)).isoformat()
                        not in getattr(self, "leaves_set", set())
                    )
                )

            else:

                total_working_days = sum(
                    1 for d in daily_records if d.date.weekday() < 5
                )

            expected_period_minutes = total_working_days * expected_daily_minutes

            if expected_period_minutes > 0:
                avg_compliance = (
                    total_office_minutes / expected_period_minutes
                ) * 100
            else:
                avg_compliance = 0.0

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

        emp_codes = [employee.code for _, employee in summaries]
        all_daily = self._batch_load_daily_attendance(week_start, week_end, emp_codes)
        self._preload_holidays(week_start, week_end)
        leave_emails = [
            employee.email for _, employee in summaries
            if employee.email and (employee.work_mode or 'WFO').upper() != 'WFH'
        ]
        self._batch_preload_leaves(leave_emails, week_start, week_end)

        employees = []
        compliant_count = 0

        for summary, employee in summaries:
            work_mode = (employee.work_mode or 'WFO').upper()
            mode_config = self.work_mode_config.get(work_mode, self.work_mode_config['WFO'])
            daily_map = all_daily.get(employee.code, {})

            result = self._compute_weekly_compliance_fast(
                employee.code, week_start, week_end, work_mode,
                daily_map, employee.email
            )

            status_val = result['status']
            compliance = result['compliance_percentage']
            is_compliant = status_val == 'Compliance'

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

        summaries = {
            s.employee_code: s
            for s in self.db.query(WeeklySummary).filter(
                WeeklySummary.week_start == week_start
            ).all()
        }

        emp_codes = [e.code for e in non_exempt_employees if summaries.get(e.code)]
        all_daily = self._batch_load_daily_attendance(week_start, week_end, emp_codes)
        self._preload_holidays(week_start, week_end)
        leave_emails = [
            emp.email for emp in non_exempt_employees
            if summaries.get(emp.code) and emp.email
        ]
        self._batch_preload_leaves(leave_emails, week_start, week_end)

        compliant = 0
        mid_compliant = 0
        non_compliant = 0

        for emp in non_exempt_employees:
            summary = summaries.get(emp.code)

            if summary:
                work_mode = (emp.work_mode or 'WFO').upper()
                daily_map = all_daily.get(emp.code, {})
                result = self._compute_weekly_compliance_fast(
                    emp.code, week_start, week_end, work_mode,
                    daily_map, emp.email
                )
                status = result['status']
                if status == 'Compliance':
                    compliant += 1
                elif status == 'Mid-Compliance':
                    mid_compliant += 1
                else:
                    non_compliant += 1
            else:
                non_compliant += 1

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
        Monthly compliance = aggregation of WEEKLY statuses (not daily).
        Uses calculate_monthly_compliance(weekly_statuses).
        """
        import calendar as cal_mod

        year, mon = map(int, month.split("-"))
        start_date = date(year, mon, 1)
        _, days_in_month = cal_mod.monthrange(year, mon)
        end_date = date(year, mon, days_in_month)

        working_days = 0
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                working_days += 1
            current += timedelta(days=1)

        ds = self.dynamic_settings
        compliance_hours = ds['compliance_hours']

        first_monday = start_date - timedelta(days=start_date.weekday())
        month_weeks = []
        wk_start = first_monday
        while wk_start <= end_date:
            wk_end = wk_start + timedelta(days=6)
            has_weekday_in_month = any(
                start_date <= (wk_start + timedelta(days=d)) <= end_date
                and (wk_start + timedelta(days=d)).weekday() < 5
                for d in range(7)
            )
            if has_weekday_in_month:
                month_weeks.append((wk_start, wk_end))
            wk_start += timedelta(days=7)

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

        overall_start = month_weeks[0][0] if month_weeks else start_date
        overall_end = month_weeks[-1][1] if month_weeks else end_date

        emp_codes = [e.code for e in all_employees]
        all_daily_by_emp = self._batch_load_daily_attendance(overall_start, overall_end, emp_codes)
        self._preload_holidays(overall_start, overall_end)
        leave_emails = [
            emp.email for emp in all_employees
            if emp.email and (emp.work_mode or 'WFO').upper() != 'WFH'
        ]
        self._batch_preload_leaves(leave_emails, overall_start, overall_end)

        daily_records_in_month = self.db.query(DailyAttendance).filter(
            and_(
                DailyAttendance.date >= start_date,
                DailyAttendance.date <= end_date
            )
        ).all()

        emp_month_records = {}
        for rec in daily_records_in_month:
            emp_month_records.setdefault(rec.employee_code, []).append(rec)

        final = []
        for emp in all_employees:
            emp_work_mode = (emp.work_mode or "WFO").upper()
            is_exempted = emp_work_mode == "WFH"
            mode_config = self.work_mode_config.get(emp_work_mode, self.work_mode_config['WFO'])

            records = emp_month_records.get(emp.code, [])

            wfo_days = sum(1 for r in records if (r.total_office_minutes or 0) > 0)
            wfh_days = working_days - wfo_days
            total_office_minutes = sum(r.total_office_minutes or 0 for r in records)
            total_office_hours = total_office_minutes / 60.0

            days_below_required_hours = 0
            for r in records:
                daily_minutes = r.total_office_minutes or 0
                daily_hours = daily_minutes / 60.0
                if daily_minutes > 0 and daily_hours < compliance_hours:
                    days_below_required_hours += 1

            if is_exempted:
                compliance_percentage = 100.0
                compliance_status = "Compliance"
                required_days = 0
            else:
                required_days = mode_config.get('required_days', 0)
                emp_daily_map = all_daily_by_emp.get(emp.code, {})

                weekly_statuses = []
                for wk_s, wk_e in month_weeks:
                    result = self._compute_weekly_compliance_fast(
                        emp.code, wk_s, wk_e, emp_work_mode,
                        emp_daily_map, emp.email
                    )
                    weekly_statuses.append(result['status'])

                compliance_status = TimeCalculator.calculate_monthly_compliance(weekly_statuses)

                expected_monthly_minutes = required_days * len(month_weeks) * mode_config.get('hours_per_day', compliance_hours) * 60
                if expected_monthly_minutes > 0:
                    compliance_percentage = min((total_office_minutes / expected_monthly_minutes) * 100, 100.0)
                else:
                    compliance_percentage = 100.0

            final.append({
                "employee_code": emp.code,
                "employee_name": emp.name,
                "department": emp.department,
                "work_mode": emp_work_mode,
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
                    compliance_label = self._get_daily_compliance_status(
                        minutes, True, is_wfh, target_date.isoformat(), emp.email, self.db
                    )

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
