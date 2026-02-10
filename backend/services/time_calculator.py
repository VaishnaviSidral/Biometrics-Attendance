"""
Time Calculator Service
Handles time calculations for attendance data including IN/OUT pairing,
daily totals, weekly aggregation, and compliance calculations
"""
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import json
import logging

logger = logging.getLogger(__name__)


class TimeCalculator:
    """Calculate attendance times and compliance metrics"""
    
    def __init__(self, expected_hours_per_day: int = 8, wfo_days_per_week: int = 2, min_hours_for_present: int = 6, threshold_red: int = 70, threshold_amber: int = 90):
        self.expected_hours_per_day = expected_hours_per_day
        self.wfo_days_per_week = wfo_days_per_week
        self.min_minutes_for_present = min_hours_for_present * 60
        self.threshold_red = threshold_red
        self.threshold_amber = threshold_amber
        self.expected_daily_minutes = expected_hours_per_day * 60
        self.expected_weekly_minutes = wfo_days_per_week * expected_hours_per_day * 60
    
    def calculate_daily_summary(self, records: List[Dict]) -> Dict[str, Dict[date, Dict]]:
        """
        Calculate daily attendance summary for each employee
        
        Args:
            records: List of attendance records from parser
        
        Returns:
            Dict mapping employee_code -> date -> daily_summary
        """
        # Group records by employee and date
        employee_date_records = defaultdict(lambda: defaultdict(list))
        
        for record in records:
            emp_code = record['code']
            rec_date = record['date']
            employee_date_records[emp_code][rec_date].append(record)
        
        # Calculate daily summary for each employee-date combination
        summaries = {}
        
        for emp_code, date_records in employee_date_records.items():
            summaries[emp_code] = {}
            
            for rec_date, day_records in date_records.items():
                summary = self._calculate_day_summary(day_records)
                summaries[emp_code][rec_date] = summary
        
        return summaries
    
    def _calculate_day_summary(self, day_records: List[Dict]) -> Dict:
        """
        Calculate summary for a single day's attendance
        
        Handles:
        - Multiple IN/OUT entries
        - Missing IN or OUT
        - Uses total_time if available from biometric system
        """
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
        
        # If total time is provided by device, use it
        if total_from_device:
            total_minutes = self._time_to_minutes(total_from_device)
        else:
            # Calculate from IN/OUT pairs
            total_minutes = self._calculate_from_pairs(in_times, out_times)
        
        # Determine status
        # Determine status (Strict 6-hour rule)
        if total_minutes >= self.min_minutes_for_present:
            status = "PRESENT"
        else:
            # Less than 6 hours = ABSENT (even if there are punches)
            status = "ABSENT"
        
        # Get first IN and last OUT
        first_in = min(in_times) if in_times else None
        last_out = max(out_times) if out_times else None
        
        if total_minutes > 0:
            print(f"DEBUG time_calc: in_times={in_times}, out_times={out_times}, first_in={first_in}, last_out={last_out}, total_minutes={total_minutes}")
        
        # Create IN/OUT pairs for display
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
        """
        Calculate total time from IN/OUT pairs
        
        Algorithm:
        1. Sort both lists
        2. For each IN, find the next OUT after it
        3. Calculate duration and add to total
        """
        if not in_times or not out_times:
            return 0
        
        sorted_ins = sorted(in_times)
        sorted_outs = sorted(out_times)
        
        total_minutes = 0
        used_outs = set()
        
        for in_time in sorted_ins:
            # Find the next available OUT after this IN
            for i, out_time in enumerate(sorted_outs):
                if i in used_outs:
                    continue
                if out_time > in_time:
                    # Calculate duration
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
            
            # Find matching OUT
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
        employee_requirements: Dict[str, int] = None
    ) -> Dict[str, Dict]:
        """
        Calculate weekly summary for each employee
        
        Args:
            daily_summaries: Output from calculate_daily_summary
            week_start: Start of the week
            week_end: End of the week
            employee_requirements: Dict of {emp_code: required_wfo_days}
        
        Returns:
            Dict mapping employee_code -> weekly_summary
        """
        weekly = {}
        employee_requirements = employee_requirements or {}
        
        for emp_code, date_summaries in daily_summaries.items():
            total_minutes = 0
            wfo_days = 0
            
            for day_date, summary in date_summaries.items():
                if week_start <= day_date <= week_end:
                    total_minutes += summary.get('total_office_minutes', 0)
                    if summary.get('status') in ['PRESENT', 'PARTIAL']:
                        wfo_days += 1
            
            # Determine expected minutes based on ACTUAL days worked
            # User request: "expected hours should be Number of WFO per employee worked * 8"
            expected_minutes = wfo_days * self.expected_hours_per_day * 60
            
            # Calculate compliance percentage (no cap - allow >100% for overtime)
            if expected_minutes > 0:
                compliance = (total_minutes / expected_minutes) * 100
                # No cap - employees who work more show >100%
            else:
                compliance = 0
            
            # Determine status color
            status = self._get_status_color(compliance)
            
            weekly[emp_code] = {
                'week_start': week_start,
                'week_end': week_end,
                'total_office_minutes': total_minutes,
                'wfo_days': wfo_days,
                'expected_minutes': expected_minutes,
                'compliance_percentage': round(compliance, 2),
                'status': status
            }
        
        return weekly
    
    def _get_status_color(self, percentage: float) -> str:
        """Get status color based on percentage"""
        if percentage < self.threshold_red:
            return "RED"
        elif percentage <= self.threshold_amber:
            return "AMBER"
        else:
            return "GREEN"
    
    def get_week_bounds(self, d: date) -> Tuple[date, date]:
        """Get the Monday and Sunday of the week containing the given date"""
        # Monday is weekday 0
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
