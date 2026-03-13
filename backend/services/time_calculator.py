"""
Time Calculator Service
Handles time calculations for attendance data including IN/OUT pairing,
daily totals, weekly aggregation, and compliance calculations.

Compliance Philosophy:
  Compliance is measured based on daily discipline, not total hours.
  An employee is compliant only if they consistently meet expected daily working hours.
  Working extra on some days does NOT compensate for underworking on other days.

Daily Rule Engine (Single Source of Truth):
  For each working day, for each employee:
    - If absent → "Non-Compliance"
    - If present:
        - If daily_hours >= compliance_hours → "Compliance"
        - Else if daily_hours >= mid_compliance_hours → "Mid-Compliance"
        - Else → "Non-Compliance"

Aggregation Rules (Weekly / Monthly):
  - If ANY Non-Compliance day → Period = "Non-Compliance"
  - Else if ANY Mid-Compliance day → Period = "Mid-Compliance"
  - Else → Period = "Compliance"

Work Mode:
  WFO:    configurable days office, configurable hours/day
  Hybrid: configurable days office, configurable hours/day
  WFH:    Only tracking, compliance = always "Compliance"
"""
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from models.holidays import Holiday
from services.redmine_service import redmine_service
from datetime import datetime, timedelta, date, time
from collections import defaultdict
import json
import logging

logger = logging.getLogger(__name__)


def build_work_mode_config(
    expected_hours_per_day: int = 9,
    wfo_days_per_week: int = 5,
    hybrid_days_per_week: int = 3
) -> Dict:
    """
    Build work mode configuration dynamically from settings.
    Called with values from DB settings so changes in Settings page
    actually affect compliance calculations.
    """
    return {
        'WFO': {
            'required_days': wfo_days_per_week,
            'hours_per_day': expected_hours_per_day,
            'expected_weekly_hours': wfo_days_per_week * expected_hours_per_day,
        },
        'HYBRID': {
            'required_days': hybrid_days_per_week,
            'hours_per_day': expected_hours_per_day,
            'expected_weekly_hours': hybrid_days_per_week * expected_hours_per_day,
        },
        'WFH': {
            'required_days': 0,
            'hours_per_day': 0,
            'expected_weekly_hours': 0,
            'always_compliant': True,  # WFH = always Compliance
        }
    }


# Default config (used as fallback only)
DEFAULT_WORK_MODE_CONFIG = build_work_mode_config()


class TimeCalculator:
    """Calculate attendance times and compliance metrics"""

    def __init__(self, expected_hours_per_day: int = 9, wfo_days_per_week: int = 5,
                 hybrid_days_per_week: int = 3, threshold_red: int = 60,
                 threshold_amber: int = 90, compliance_hours: float = 9.0,
                 mid_compliance_hours: float = 7.0, non_compliance_hours: float = 6.0):
        self.expected_hours_per_day = expected_hours_per_day
        self.wfo_days_per_week = wfo_days_per_week
        self.hybrid_days_per_week = hybrid_days_per_week
        self.threshold_red = threshold_red
        self.threshold_amber = threshold_amber
        self.compliance_hours = compliance_hours
        self.mid_compliance_hours = mid_compliance_hours
        self.non_compliance_hours = non_compliance_hours
        self.expected_daily_minutes = expected_hours_per_day * 60
        self.expected_weekly_minutes = wfo_days_per_week * expected_hours_per_day * 60

        # Build dynamic config from the actual settings
        self.work_mode_config = build_work_mode_config(
            expected_hours_per_day=expected_hours_per_day,
            wfo_days_per_week=wfo_days_per_week,
            hybrid_days_per_week=hybrid_days_per_week
        )

    # ──────────────────────────────────────────────
    # DAILY RULE ENGINE — Single Source of Truth
    # ──────────────────────────────────────────────

    def compute_daily_compliance_status(self, total_minutes: int, is_present: bool,
                                         is_wfh: bool = False, date: str = None, 
                                         employee_email: str = None, db: Session = None) -> str:
        """
        Optimized Rule Engine — Daily compliance status with holiday and leave checking.

        Execution Order:
        1. Check biometric data first - if IN/OUT entries exist, calculate normally
        2. If no biometric data, check if date is a holiday
        3. If not holiday, check if employee is on leave in Redmine
        
        Rules:
          - WFH employees → always "Compliance" (if present)
          - If absent and no biometric data:
              - If holiday → "Holiday"
              - If on leave → "Leave"
              - Else → "Non-Compliance"
          - If present:
              - daily_hours >= compliance_hours → "Compliance"
              - daily_hours >= mid_compliance_hours → "Mid-Compliance"
              - Else → "Non-Compliance"

        Returns: "Compliance", "Mid-Compliance", "Non-Compliance", or "Leave"
        """
        # Step 1: If present with biometric data, calculate normally
        if is_present and total_minutes > 0:
            if is_wfh:
                return "Compliance"
            
            daily_hours = total_minutes / 60.0
            if daily_hours >= self.compliance_hours:
                return "Compliance"
            elif daily_hours >= self.mid_compliance_hours:
                return "Mid-Compliance"
            else:
                return "Non-Compliance"
        
        # Step 2: No biometric data, check if it's a holiday
        if date and db:
            try:
                holiday = db.query(Holiday).filter(Holiday.date == datetime.strptime(date, '%Y-%m-%d').date()).first()
                if holiday:
                    return "Holiday"
            except ValueError:
                pass  # Invalid date format, continue to next check
        
        # Step 3: Check if employee is on leave in Redmine
        if date and employee_email:
            try:
                if redmine_service.is_employee_on_leave(employee_email, date):
                    return "Leave"
            except Exception:
                pass  # Error checking leave, continue to default
        
        # Default: Non-Compliance
        return "Non-Compliance"

    # ──────────────────────────────────────────────
    # AGGREGATION HELPERS
    # ──────────────────────────────────────────────

    @staticmethod
    def aggregate_compliance_statuses(daily_statuses: List[str]) -> str:
        """
        Pure aggregation of a list of compliance status strings.
        Leave days are excluded from compliance calculations.
        
        Used internally by the weekly/monthly functions below.
        """
        if not daily_statuses:
            return "Non-Compliance"
        
        # Filter out leave days for compliance calculation
        working_days_statuses = [status for status in daily_statuses if status != "Leave"]
        
        if not working_days_statuses:
            # All days are leave, return Compliance by default
            return "Compliance"

        if "Non-Compliance" in working_days_statuses:
            return "Non-Compliance"
        elif "Mid-Compliance" in working_days_statuses:
            return "Mid-Compliance"
        else:
            return "Compliance"

    # ──────────────────────────────────────────────
    # WEEKLY COMPLIANCE — Single shared function
    # ──────────────────────────────────────────────
    @staticmethod
    def calculate_weekly_compliance(
        daily_statuses: List[str],
        present_days: int,
        required_days: int,
        is_wfh: bool = False
    ) -> str:

        # Step 1: WFH always compliant
        if is_wfh:
            return "Compliance"

        # Step 2: If the entire week is Leave / Official Leave
        if all(s in ["Leave", "Official Leave"] for s in daily_statuses):
            return "Leave"

        # Step 3: Remove non-working days
        valid_statuses = [
            s for s in daily_statuses
            if s not in ["Leave", "Official Leave", "Holiday", "Weekend"]
        ]

        if not valid_statuses:
            return "Compliance"

        # Step 4: If any Non-Compliance
        if "Non-Compliance" in valid_statuses:
            return "Non-Compliance"

        # Step 5: If all Compliance
        if all(s == "Compliance" for s in valid_statuses):
            return "Compliance"

        # Step 6: Otherwise Mid
        return "Mid-Compliance"
        
    # ──────────────────────────────────────────────
    # MONTHLY COMPLIANCE — Aggregated from weekly
    # ──────────────────────────────────────────────

    @staticmethod
    def calculate_monthly_compliance(weekly_statuses: List[str]) -> str:

        if not weekly_statuses:
            return "Non-Compliance"

        # If all weeks are Leave
        if all(s == "Leave" for s in weekly_statuses):
            return "Leave"

        if "Non-Compliance" in weekly_statuses:
            return "Non-Compliance"

        if "Mid-Compliance" in weekly_statuses:
            return "Mid-Compliance"

        return "Compliance"

    # ──────────────────────────────────────────────
    # DAILY SUMMARY CALCULATION
    # ──────────────────────────────────────────────

    def calculate_daily_summary(self, records: List[Dict]) -> Dict[str, Dict[date, Dict]]:
        """
        Calculate daily attendance summary for each employee
        """
        employee_date_records = defaultdict(lambda: defaultdict(list))

        for record in records:
            emp_code = record['code']
            rec_date = record['date']
            employee_date_records[emp_code][rec_date].append(record)

        summaries = {}

        for emp_code, date_records in employee_date_records.items():
            summaries[emp_code] = {}

            for rec_date, day_records in date_records.items():
                summary = self._calculate_day_summary(day_records)
                summaries[emp_code][rec_date] = summary

        return summaries

    def _calculate_day_summary(self, day_records: List[Dict]) -> Dict:
        """Calculate summary for a single day's attendance"""
        in_times = []
        out_times = []
        total_from_device = None
        remark = None

        for record in day_records:
            if record.get('in_time'):
                in_times.append(record['in_time'])
            if record.get('out_time'):
                out_times.append(record['out_time'])
            if record.get('total_time') and not total_from_device:
                total_from_device = record['total_time']
            if record.get('remark'):
                remark = record['remark']

        if total_from_device:
            total_minutes = self._time_to_minutes(total_from_device)
        else:
            total_minutes = self._calculate_from_pairs(in_times, out_times)

        # Presence logic: PRESENT if any time > 0 OR any in_time exists
        if total_minutes > 0 or in_times:
            status = "PRESENT"
        else:
            status = "ABSENT"

        first_in = min(in_times) if in_times else None
        last_out = max(out_times) if out_times else None

        pairs = self._create_pairs(in_times, out_times)

        return {
            'total_office_minutes': total_minutes,
            'status': status,
            'first_in': first_in,
            'last_out': last_out,
            'in_out_pairs': json.dumps(pairs) if pairs else None,
            'remark': remark
        }

    def _time_to_minutes(self, t: time) -> int:
        """Convert time object to total minutes"""
        if not t:
            return 0
        return t.hour * 60 + t.minute

    def _calculate_from_pairs(self, in_times: List[time], out_times: List[time]) -> int:
        """Calculate total time from IN/OUT pairs"""
        if not in_times or not out_times:
            return 0

        sorted_ins = sorted(in_times)
        sorted_outs = sorted(out_times)

        total_minutes = 0
        used_outs = set()

        for in_time in sorted_ins:
            for i, out_time in enumerate(sorted_outs):
                if i in used_outs:
                    continue
                if out_time > in_time:
                    in_minutes = self._time_to_minutes(in_time)
                    out_minutes = self._time_to_minutes(out_time)
                    duration = out_minutes - in_minutes

                    if duration > 0:
                        total_minutes += duration
                        used_outs.add(i)
                        break

        return total_minutes

    def _create_pairs(self, in_times: List[time], out_times: List[time]) -> List[Dict]:
        """Create list of IN/OUT pairs for display"""
        pairs = []

        sorted_ins = sorted(in_times) if in_times else []
        sorted_outs = sorted(out_times) if out_times else []

        used_outs = set()

        for in_time in sorted_ins:
            pair = {
                'in': in_time.strftime('%H:%M') if in_time else None,
                'out': None,
                'duration': None
            }

            for i, out_time in enumerate(sorted_outs):
                if i in used_outs:
                    continue
                if out_time > in_time:
                    pair['out'] = out_time.strftime('%H:%M')
                    duration = self._time_to_minutes(out_time) - self._time_to_minutes(in_time)
                    pair['duration'] = f"{duration // 60}h {duration % 60}m"
                    used_outs.add(i)
                    break

            pairs.append(pair)

        return pairs

    # ──────────────────────────────────────────────
    # WEEKLY SUMMARY — Aggregates from daily statuses
    # ──────────────────────────────────────────────

    def calculate_weekly_summary(
        self,
        daily_summaries: Dict[str, Dict[date, Dict]],
        week_start: date,
        week_end: date,
        employee_work_modes: Dict[str, str] = None,
        work_mode_config: Dict = None
    ) -> Dict[str, Dict]:
        """
        Calculate weekly summary for each employee.
        Enumerates ALL weekdays (Mon-Fri) in the week range.
        Missing weekday records are treated as absent → Non-Compliance.
        Uses calculate_weekly_compliance() for status determination.
        """

        weekly = {}
        employee_work_modes = employee_work_modes or {}
        config = work_mode_config or self.work_mode_config

        for emp_code, date_summaries in daily_summaries.items():

            total_minutes = 0
            actual_presence_days = 0
            daily_statuses = []

            work_mode = employee_work_modes.get(emp_code, 'WFO').upper()
            mode_config = config.get(work_mode, config['WFO'])
            is_wfh = mode_config.get('always_compliant', False)

            policy_required_days = mode_config.get('required_days', 0)
            hours_per_day = mode_config.get('hours_per_day', self.expected_hours_per_day)

            # Enumerate ALL weekdays in the range
            current = week_start
            while current <= week_end:
                if current.weekday() < 5:  # Mon-Fri only
                    summary = date_summaries.get(current)
                    if summary:
                        minutes = summary.get('total_office_minutes', 0)
                        total_minutes += minutes

                        is_present = minutes > 0
                        if is_present:
                            actual_presence_days += 1

                        if 'compliance_status' in summary and summary['compliance_status']:
                            daily_statuses.append(summary['compliance_status'])
                        else:
                            daily_status = self.compute_daily_compliance_status(
                                minutes, is_present, is_wfh
                            )
                            daily_statuses.append(daily_status)
                    else:
                        # No record for this weekday → absent
                        if is_wfh:
                            daily_statuses.append("Compliance")
                        else:
                            daily_statuses.append("Non-Compliance")
                current += timedelta(days=1)

            wfo_days = min(actual_presence_days, policy_required_days)

            expected_minutes = policy_required_days * hours_per_day * 60

            compliance_status = self.calculate_weekly_compliance(
                daily_statuses, actual_presence_days, policy_required_days, is_wfh
            )

            if is_wfh:
                compliance_percentage = 100.0
                expected_minutes = 0
            elif expected_minutes > 0:
                compliance_percentage = min((total_minutes / expected_minutes) * 100, 100.0)
            else:
                compliance_percentage = 0.0

            weekly[emp_code] = {
                'week_start': week_start,
                'week_end': week_end,
                'total_office_minutes': total_minutes,
                'actual_presence_days': actual_presence_days,
                'policy_required_days': policy_required_days,
                'wfo_days': wfo_days,
                'expected_minutes': expected_minutes,
                'compliance_percentage': round(compliance_percentage, 2),
                'status': compliance_status,
                'work_mode': work_mode,
                'daily_statuses': daily_statuses
            }

        return weekly

    def get_week_bounds(self, d: date) -> Tuple[date, date]:
        """Get the Monday and Sunday of the week containing the given date"""
        monday = d - timedelta(days=d.weekday())
        sunday = monday + timedelta(days=6)
        return monday, sunday

    def get_all_weeks(self, dates: List[date]) -> List[Tuple[date, date]]:
        """Get all unique weeks from a list of dates"""
        weeks = set()

        for d in dates:
            week_bounds = self.get_week_bounds(d)
            weeks.add(week_bounds)

        return sorted(list(weeks))

    def format_minutes(self, minutes: int) -> str:
        """Format minutes as human-readable string"""
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"
