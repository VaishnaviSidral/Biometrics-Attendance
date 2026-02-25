"""
Attendance Parser Service
Handles parsing of biometric attendance data from CSV/Excel files
"""
import pandas as pd
from datetime import datetime, date, time
from typing import List, Dict, Optional, Tuple
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


class AttendanceParser:
    """Parse and validate biometric attendance data"""
    
    # Expected column mappings (case-insensitive)
    COLUMN_MAPPINGS = {
        'date': ['date', 'DATE', 'Date'],
        'code': ['code', 'CODE', 'Code', 'employee_code', 'emp_code', 'id'],
        'name': ['name', 'NAME', 'Name', 'employee_name', 'emp_name'],
        'in_time': ['in', 'IN', 'In', 'in_time', 'clock_in', 'punch_in'],
        'out_time': ['out', 'OUT', 'Out', 'out_time', 'clock_out', 'punch_out'],
        'total': ['total', 'TOTAL', 'Total', 'total_time', 'hours'],
        'shift': ['shift', 'SHIFT', 'Shift'],
        'late': ['late', 'LATE', 'Late'],
        'ot': ['ot', 'OT', 'overtime', 'OVERTIME'],
        'remark': ['remark', 'REMARK', 'Remark', 'remarks', 'status']
    }
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    


    def parse_file(self, file_content: bytes, filename: str) -> Tuple[pd.DataFrame, List[Dict]]:
        """
        Parse uploaded file (CSV or Excel) into structured attendance data
        """

            
        self.errors = []
        self.warnings = []
        
        # Determine file type
        if filename.lower().endswith('.csv'):
            df = self._parse_csv(file_content)
        elif filename.lower().endswith(('.xlsx', '.xls')):
            df = self._parse_excel(file_content)
        else:
            raise ValueError(f"Unsupported file format: {filename}")
        

        
        # Normalize column names
        df = self._normalize_columns(df)

        
        # Parse and validate data
        records = self._parse_records(df)

        
        return df, records
    
    def _parse_csv(self, content: bytes) -> pd.DataFrame:
        """Parse CSV file"""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    return pd.read_csv(BytesIO(content), encoding=encoding)
                except UnicodeDecodeError:
                    continue
            raise ValueError("Could not decode CSV file")
        except Exception as e:
            raise ValueError(f"Error parsing CSV: {str(e)}")
    
    def _parse_excel(self, content: bytes) -> pd.DataFrame:
        """Parse Excel file with robust header detection"""
        import warnings
        
        try:
            # Suppress date parsing warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                # First pass: try to find the header row
                # Read first few rows without header
                df_preview = pd.read_excel(BytesIO(content), header=None, nrows=10, dtype=str)
                
                header_row_idx = 0
                found_header = False
                
                # Check each row for expected column names
                for idx, row in df_preview.iterrows():
                    row_values = [str(val).strip().lower() for val in row.values if pd.notna(val)]
                    # Check for critical columns
                    has_date = any(col in row_values for col in ['date', 'attendance date'])
                    has_code = any(col in row_values for col in ['code', 'employee code', 'emp code', 'id'])
                    
                    if has_date and has_code:
                        header_row_idx = idx
                        found_header = True
                        break
                

                
                # Second pass: read full file with correct header
                try:
                    df = pd.read_excel(
                        BytesIO(content),
                        header=header_row_idx,
                        dtype=str,
                        na_values=['', 'NA', 'N/A', 'null', 'NULL']
                    )
                except Exception:
                     # Fallback to default
                    df = pd.read_excel(BytesIO(content), header=header_row_idx)


                return df
                
        except Exception as e:
            raise ValueError(f"Error parsing Excel: {str(e)}")
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to standard format"""
        column_map = {}
        
        for standard_name, variations in self.COLUMN_MAPPINGS.items():
            for col in df.columns:
                if col.strip() in variations:
                    column_map[col] = standard_name
                    break
        
        df = df.rename(columns=column_map)
        return df
    
    def _parse_records(self, df: pd.DataFrame) -> List[Dict]:
        """Parse DataFrame rows into attendance records"""
        records = []
        
        for idx, row in df.iterrows():
            try:
                record = self._parse_row(row, idx)
                if record:
                    records.append(record)
            except Exception as e:
                self.errors.append(f"Row {idx + 2}: {str(e)}")
        
        return records
    
    def _parse_row(self, row: pd.Series, idx: int) -> Optional[Dict]:
        """Parse a single row into an attendance record"""
        # Parse date
        date_val = self._parse_date(row.get('date'))
        

            
        if not date_val:
            # Skip rows without date (often headers or empty rows)
            return None
        
        # Parse employee code
        code = str(row.get('code', '')).strip()
        if not code or code == 'nan':
            # Skip rows without code
            return None
            
        # Parse name
        name = str(row.get('name', '')).strip()
        if name == 'nan':
            name = ''
            
        # Parse times
        in_time = self._parse_time(row.get('in_time'))
        out_time = self._parse_time(row.get('out_time'))
        total_time = self._parse_time(row.get('total'))
        

        
        # Parse other fields
        shift = self._parse_int(row.get('shift'))
        late = self._parse_int(row.get('late'))
        ot = self._parse_int(row.get('ot'))
        remark = str(row.get('remark', '')).strip()
        if remark == 'nan':
            remark = ''
        
        return {
            'date': date_val,
            'code': code,
            'name': name,
            'in_time': in_time,
            'out_time': out_time,
            'total_time': total_time,
            'shift': shift,
            'late_minutes': late,
            'overtime_minutes': ot,
            'remark': remark
        }
    
    def _parse_date(self, value) -> Optional[date]:
        """Parse date from various formats"""
        if pd.isna(value):
            return None
        
        if isinstance(value, datetime):
            return value.date()
        
        if isinstance(value, date):
            return value
        
        # Try common date formats
        date_formats = [
            '%d/%m/%Y',  # DD/MM/YYYY
            '%Y-%m-%d',  # YYYY-MM-DD
            '%m/%d/%Y',  # MM/DD/YYYY
            '%d-%m-%Y',  # DD-MM-YYYY
            '%Y-%m-%d %H:%M:%S', # Pandas default string for datetime
            '%d-%b-%Y',  # 01-Dec-2025
            '%d/%m/%y',  # DD/MM/YY
        ]
        
        value_str = str(value).strip()
        
        for fmt in date_formats:
            try:
                return datetime.strptime(value_str, fmt).date()
            except ValueError:
                continue
        
        return None
    
    def _parse_time(self, value) -> Optional[time]:
        """Parse time from various formats"""
        if pd.isna(value):
            return None
        
        t = None
        
        if isinstance(value, time):
            t = value
        elif isinstance(value, datetime):
            t = value.time()
        else:
            value_str = str(value).strip()
            if not value_str or value_str == 'nan':
                return None
            
            # Try common time formats including datetime strings
            time_formats = [
                '%H:%M',      # HH:MM
                '%H:%M:%S',   # HH:MM:SS
                '%I:%M %p',   # 12-hour with AM/PM
                '%I:%M:%S %p',
                '%Y-%m-%d %H:%M:%S', # Pandas default datetime string
                '%d/%m/%Y %H:%M:%S',
            ]
            
            for fmt in time_formats:
                try:
                    t = datetime.strptime(value_str, fmt).time()
                    break
                except ValueError:
                    continue
        
        # Treat 00:00:00 as None (missing)
        if t and t.hour == 0 and t.minute == 0 and t.second == 0:
            return None
            
        return t
    
    def _parse_int(self, value) -> int:
        """Parse integer value"""
        if pd.isna(value):
            return 0
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0
    
    def get_unique_employees(self, records: List[Dict]) -> List[Dict]:
        """Extract unique employees from records"""
        employees = {}
        
        for record in records:
            code = record['code']
            if code not in employees:
                employees[code] = {
                    'code': code,
                    'name': record['name']
                }
            elif not employees[code]['name'] and record['name']:
                # Update name if previously empty
                employees[code]['name'] = record['name']
        
        return list(employees.values())
