"""
Holidays Router
Handles holiday upload and management API endpoints
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any
import pandas as pd
import io
from datetime import datetime

from database import get_db
from models.holidays import Holiday

router = APIRouter(prefix="/holidays", tags=["holidays"])


@router.post("/upload")
async def upload_holidays(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Upload holidays from CSV or Excel file.
    
    Expected columns:
    - date: Holiday date (YYYY-MM-DD format)
    - holiday_description: Description of the holiday
    
    If a holiday date already exists, it will be updated.
    """
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported")
    
    try:
        # Read file content
        contents = await file.read()
        
        # Parse the file based on its type
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        # Validate required columns
        required_columns = ['date', 'holiday_description']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        # Process holidays
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Parse and validate date
                # Parse and validate date
                date_value = row['date']

                if pd.isna(date_value):
                    errors.append(f"Row {index + 2}: Date is empty")
                    error_count += 1
                    continue

                try:
                    holiday_date = pd.to_datetime(date_value).date()
                except Exception:
                    errors.append(f"Row {index + 2}: Invalid date format '{date_value}'")
                    error_count += 1
                    continue
                
                # Get description
                description = str(row['holiday_description']).strip()
                if description == 'nan' or not description:
                    errors.append(f"Row {index + 2}: Holiday description is empty")
                    error_count += 1
                    continue
                
                # Check if holiday already exists
                existing_holiday = db.query(Holiday).filter(Holiday.date == holiday_date).first()
                
                if existing_holiday:
                    # Update existing holiday
                    existing_holiday.holiday_description = description
                    updated_count += 1
                else:
                    # Create new holiday
                    new_holiday = Holiday(
                        date=holiday_date,
                        holiday_description=description
                    )
                    db.add(new_holiday)
                    created_count += 1
                    
            except Exception as e:
                errors.append(f"Row {index + 2}: {str(e)}")
                error_count += 1
                continue
        
        # Commit all changes
        db.commit()
        
        return {
            "message": "Holiday upload completed",
            "summary": {
                "total_rows": len(df),
                "created": created_count,
                "updated": updated_count,
                "errors": error_count
            },
            "errors": errors if errors else None
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.get("")
async def get_holidays(
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get holidays list.
    
    Query parameters:
    - start_date: Filter holidays from this date (YYYY-MM-DD)
    - end_date: Filter holidays until this date (YYYY-MM-DD)
    """
    query = db.query(Holiday)
    
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Holiday.date >= start)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Holiday.date <= end)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")
    
    holidays = query.order_by(Holiday.date).all()
    
    return [
        {
            "id": holiday.id,
            "date": holiday.date.isoformat(),
            "holiday_description": holiday.holiday_description
        }
        for holiday in holidays
    ]


@router.delete("/{holiday_id}")
async def delete_holiday(
    holiday_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Delete a holiday by ID"""
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    
    db.delete(holiday)
    db.commit()
    
    return {"message": "Holiday deleted successfully"}


@router.get("/check/{date}")
async def check_holiday(
    date: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Check if a specific date is a holiday.
    
    Args:
        date: Date to check in YYYY-MM-DD format
    """
    try:
        check_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    holiday = db.query(Holiday).filter(Holiday.date == check_date).first()
    
    if holiday:
        return {
            "is_holiday": True,
            "date": holiday.date.isoformat(),
            "holiday_description": holiday.holiday_description
        }
    else:
        return {
            "is_holiday": False,
            "date": date
        }


def get_holidays_in_range(db: Session, start_date: str, end_date: str) -> List[str]:
    """
    Helper function to get list of holiday dates in a date range.
    
    Args:
        db: Database session
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        List of holiday dates (YYYY-MM-DD format)
    """
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return []
    
    holidays = db.query(Holiday).filter(
        Holiday.date >= start,
        Holiday.date <= end
    ).all()
    
    return [holiday.date.isoformat() for holiday in holidays]
