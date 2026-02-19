"""
Database configuration and session management
Biometric DB = READ/WRITE (main app DB)
Redmine DB = READ ONLY (user validation only)
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings
import logging

logger = logging.getLogger(__name__)

# ============================================================
# Biometric DB (READ/WRITE) - Main application database
# ============================================================
if settings.DATABASE_URL.startswith('mysql'):
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=10,
        max_overflow=20
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for getting biometric database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# Redmine DB (READ ONLY) - User validation only
# ============================================================
redmine_engine = create_engine(
    settings.REDMINE_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=5
)
RedmineSession = sessionmaker(autocommit=False, autoflush=False, bind=redmine_engine)


def get_redmine_db():
    """Dependency for getting Redmine database session (READ ONLY)"""
    db = RedmineSession()
    try:
        yield db
    finally:
        db.close()


def validate_user_in_redmine(email: str) -> dict | None:
    """
    Check if user email exists in Redmine DB (READ ONLY).
    Returns user info dict or None if not found.
    
    Redmine schema:
      users: id, login, firstname, lastname, status
      email_addresses: id, user_id, address
    """
    db = RedmineSession()
    try:
        result = db.execute(
            text("""
                SELECT u.id, u.firstname, u.lastname, e.address as email
                FROM users u
                JOIN email_addresses e ON e.user_id = u.id
                WHERE e.address = :email
                AND u.status = 1
                LIMIT 1
            """),
            {"email": email}
        ).fetchone()

        if result:
            return {
                "id": result[0],
                "firstname": result[1],
                "lastname": result[2],
                "email": result[3]
            }
        return None
    except Exception as ex:
        logger.error(f"Error querying Redmine DB: {ex}")
        return None
    finally:
        db.close()


# ============================================================
# Database initialization
# ============================================================
def init_db():
    """Initialize database tables (Biometric DB only - never write to Redmine)"""
    from models import admin, employee, attendance, settings as settings_model
    
    # Create all tables in biometric DB
    Base.metadata.create_all(bind=engine)
    
    logger.info("Biometric database tables initialized")
    
    # Add work_mode and email columns to employees if they don't exist
    _migrate_employees_table()


def _migrate_employees_table():
    """Add new columns to employees table if they don't exist"""
    db = SessionLocal()
    try:
        # Check if work_mode column exists
        try:
            db.execute(text("SELECT work_mode FROM employees LIMIT 1"))
        except Exception:
            db.rollback()
            try:
                db.execute(text("ALTER TABLE employees ADD COLUMN work_mode VARCHAR(10) DEFAULT 'WFO'"))
                db.commit()
                logger.info("Added work_mode column to employees table")
            except Exception as e:
                db.rollback()
                logger.warning(f"Could not add work_mode column: {e}")

        # Check if email column exists
        try:
            db.execute(text("SELECT email FROM employees LIMIT 1"))
        except Exception:
            db.rollback()
            try:
                db.execute(text("ALTER TABLE employees ADD COLUMN email VARCHAR(255) DEFAULT NULL"))
                db.commit()
                logger.info("Added email column to employees table")
            except Exception as e:
                db.rollback()
                logger.warning(f"Could not add email column: {e}")
    finally:
        db.close()
