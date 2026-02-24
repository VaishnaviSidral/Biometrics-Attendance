"""
Time Calculator Service
Handles time calculations for attendance data including IN/OUT pairing,
daily totals, weekly aggregation, and compliance calculations.

Compliance rules:
  WFO:    configurable days office, configurable hours/day
  Hybrid: configurable days office, configurable hours/day
  WFH:    Only tracking, compliance = 100%

Status thresholds:
  Compliance     >= threshold_amber%  → GREEN
  Mid-Compliance = threshold_red% – (threshold_amber-1)%  → AMBER
  Non-Compliance < threshold_red%  → RED
"""
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional, Tuple
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
            'always_compliant': True,  # WFH = 100% compliance
        },
        'CLIENT_OFFICE': {
            'required_days': wfo_days_per_week,
            'hours_per_day': expected_hours_per_day,
            'expected_weekly_hours': wfo_days_per_week * expected_hours_per_day,
        }
    }


# Default config (used as fallback only)
DEFAULT_WORK_MODE_CONFIG = build_work_mode_config()


class TimeCalculator:
    """Calculate attendance times and compliance metrics"""

    def __init__(self, expected_hours_per_day: int = 9, wfo_days_per_week: int = 5,
                 hybrid_days_per_week: int = 3, threshold_red: int = 60,
                 threshold_amber: int = 90):
        self.expected_hours_per_day = expected_hours_per_day
        self.wfo_days_per_week = wfo_days_per_week
        self.hybrid_days_per_week = hybrid_days_per_week
        self.threshold_red = threshold_red
        self.threshold_amber = threshold_amber
        self.expected_daily_minutes = expected_hours_per_day * 60
        self.expected_weekly_minutes = wfo_days_per_week * expected_hours_per_day * 60

        # Build dynamic config from the actual settings
        self.work_mode_config = build_work_mode_config(
            expected_hours_per_day=expected_hours_per_day,
            wfo_days_per_week=wfo_days_per_week,
            hybrid_days_per_week=hybrid_days_per_week
        )

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
        # The 9-hour rule is for COMPLIANCE only, NOT for presence
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
        Correct logic:
        - Presence days come from biometric data (daily_attendance)
        - Policy days come from work_mode config (WFO/Hybrid/WFH)
        - wfo_days = min(actual_presence_days, policy_required_days)
        - compliance based on minutes vs expected policy minutes
        """

        weekly = {}
        employee_work_modes = employee_work_modes or {}
        config = work_mode_config or self.work_mode_config

        for emp_code, date_summaries in daily_summaries.items():

            total_minutes = 0
            actual_presence_days = 0   # biometric truth

            # --- Aggregate daily data ---
            for day_date, summary in date_summaries.items():
                if week_start <= day_date <= week_end:
                    minutes = summary.get('total_office_minutes', 0)
                    total_minutes += minutes

                    # Presence = came to office that day
                    if minutes > 0:
                        actual_presence_days += 1

            # --- Work mode policy ---
            work_mode = employee_work_modes.get(emp_code, 'WFO').upper()
            mode_config = config.get(work_mode, config['WFO'])

            policy_required_days = mode_config.get('required_days', 0)
            hours_per_day = mode_config.get('hours_per_day', self.expected_hours_per_day)

            # --- WFO days (policy capped) ---
            # Example:
            # Hybrid policy = 3 days
            # Actual presence = 5 days
            # → wfo_days = 3
            wfo_days = min(actual_presence_days, policy_required_days)

            # --- Expected minutes ---
            expected_minutes = policy_required_days * hours_per_day * 60

            # --- Compliance ---
            if mode_config.get('always_compliant'):   # WFH
                compliance = 100.0
                expected_minutes = 0
            else:
                if expected_minutes > 0:
                    compliance = (total_minutes / expected_minutes) * 100
                    compliance = min(compliance, 100.0)
                else:
                    compliance = 0.0

            # --- Status ---
            status = self._get_status_color(compliance)

            # --- Weekly record ---
            weekly[emp_code] = {
                'week_start': week_start,
                'week_end': week_end,
                'total_office_minutes': total_minutes,
                'actual_presence_days': actual_presence_days,   # real biometric days
                'policy_required_days': policy_required_days,   # HR policy days
                'wfo_days': wfo_days,                            # compliance days
                'expected_minutes': expected_minutes,
                'compliance_percentage': round(compliance, 2),
                'status': status,
                'work_mode': work_mode
            }

        return weekly

    def _get_status_color(self, percentage: float) -> str:
        """
        Get status color based on percentage.
            >= threshold_amber = GREEN (Compliance)
            threshold_red to threshold_amber-1 = AMBER (Mid-Compliance)
            < threshold_red = RED (Non-Compliance)
        """
        if percentage >= self.threshold_amber:
            return "GREEN"
        elif percentage >= self.threshold_red:
            return "AMBER"
        else:
            return "RED"

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
