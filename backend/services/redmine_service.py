"""
Redmine Service
Handles communication with Redmine database for leave checking
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import settings
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class RedmineService:
    """Service for interacting with Redmine database"""
    
    def __init__(self):
        self.redmine_engine = create_engine(
            f"mysql+pymysql://{settings.REDMINE_DB_USER}:{settings.REDMINE_DB_PASSWORD}"
            f"@{settings.REDMINE_DB_HOST}:{settings.REDMINE_DB_PORT}/{settings.REDMINE_DB_NAME}"
            f"?charset=utf8mb4"
        )
        self.RedmineSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.redmine_engine)
    
    def get_user_id_by_email(self, email: str) -> Optional[int]:
        """Get user_id from email_addresses table using email"""
        if not email:
            return None
            
        try:
            with self.RedmineSessionLocal() as session:
                query = text("""
                    SELECT user_id 
                    FROM email_addresses 
                    WHERE address = :email 
                    AND is_default = 1
                    LIMIT 1
                """)
                result = session.execute(query, {"email": email})
                row = result.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"Error getting user_id for email {email}: {str(e)}")
            return None
    
    def is_employee_on_leave(self, email: str, date: str) -> bool:
        """
        Check if employee is on leave for a specific date.
        
        Args:
            email: Employee email address
            date: Date in YYYY-MM-DD format
            
        Returns:
            True if employee is on leave, False otherwise
        """
        user_id = self.get_user_id_by_email(email)
        if not user_id:
            return False
        
        try:
            with self.RedmineSessionLocal() as session:
                # First get leave issue IDs (project_id = 994)
                leave_issues_query = text("""
                    SELECT id 
                    FROM issues 
                    WHERE project_id = 994
                """)
                leave_issues_result = session.execute(leave_issues_query)
                leave_issue_ids = [row[0] for row in leave_issues_result.fetchall()]
                
                if not leave_issue_ids:
                    return False
                
                # Check if user has time entry for leave on the given date
                time_entry_query = text("""
                    SELECT COUNT(*) as count
                    FROM time_entries 
                    WHERE user_id = :user_id 
                    AND issue_id IN :leave_issue_ids
                    AND spent_on = :date
                    LIMIT 1
                """)
                
                result = session.execute(
                    time_entry_query, 
                    {
                        "user_id": user_id,
                        "leave_issue_ids": tuple(leave_issue_ids),
                        "date": date
                    }
                )
                row = result.fetchone()
                return row[0] > 0 if row else False
                
        except Exception as e:
            logger.error(f"Error checking leave status for {email} on {date}: {str(e)}")
            return False
    
    def get_leave_days_for_period(self, email: str, start_date: str, end_date: str) -> list:
        """
        Get all leave days for an employee within a date range.
        
        Args:
            email: Employee email address
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of dates (YYYY-MM-DD format) when employee was on leave
        """
        user_id = self.get_user_id_by_email(email)
        if not user_id:
            return []
        
        try:
            with self.RedmineSessionLocal() as session:
                # Get leave issue IDs
                leave_issues_query = text("""
                    SELECT id 
                    FROM issues 
                    WHERE project_id = 994
                """)
                leave_issues_result = session.execute(leave_issues_query)
                leave_issue_ids = [row[0] for row in leave_issues_result.fetchall()]
                
                if not leave_issue_ids:
                    return []
                
                # Get all leave dates in the period
                time_entries_query = text("""
                    SELECT DISTINCT spent_on
                    FROM time_entries 
                    WHERE user_id = :user_id 
                    AND issue_id IN :leave_issue_ids
                    AND spent_on BETWEEN :start_date AND :end_date
                    ORDER BY spent_on
                """)
                
                result = session.execute(
                    time_entries_query,
                    {
                        "user_id": user_id,
                        "leave_issue_ids": tuple(leave_issue_ids),
                        "start_date": start_date,
                        "end_date": end_date
                    }
                )
                return [row[0] for row in result.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting leave days for {email} from {start_date} to {end_date}: {str(e)}")
            return []


# Create a singleton instance
redmine_service = RedmineService()
