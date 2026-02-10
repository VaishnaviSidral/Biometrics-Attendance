
import sys
import os
import pandas as pd

# Add current directory to path so we can import backend modules
sys.path.append(os.getcwd())

from services.attendance_parser import AttendanceParser

def test_parser():
    file_path = '../sample_data/biometric_export.csv'
    print(f"Testing parser with {file_path}...")
    
    with open(file_path, 'rb') as f:
        content = f.read()
        
    parser = AttendanceParser()
    try:
        df, records = parser.parse_file(content, 'biometric_export.csv')
        print(f"\nSuccess! Parsed {len(records)} records.")
        
        # Check first 3 records for time data
        print("\nChecking first 3 records for IN/OUT times:")
        for i, record in enumerate(records[:3]):
            print(f"Record {i}: Date={record['date']}, Code={record['code']}, Name={record['name']}")
            print(f"  IN: {record['in_time']} (Type: {type(record['in_time'])})")
            print(f"  OUT: {record['out_time']} (Type: {type(record['out_time'])})")
            
    except Exception as e:
        print(f"\nError parsing file: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_parser()
