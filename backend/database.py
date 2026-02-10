"""
Database configuration and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings as cfg_settings
import logging

# Create database engine
engine = create_engine(cfg_settings.DATABASE_URL)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency for getting database session
    Yields a database session and ensures it's closed after use
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables and create default users"""
    from models import employee, attendance, settings  # Import models to register them
    from models.user import User, UserRole
    from models.employee import Employee
    from services.auth_utils import get_password_hash
    
    logger = logging.getLogger(__name__)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create a session to check and create default users
    db = SessionLocal()
    try:
        # Check if admin user exists
        admin_user = db.query(User).filter(User.username == cfg_settings.DEFAULT_ADMIN_USERNAME).first()
        if not admin_user:
            # Create default admin user
            admin_user = User(
                username=cfg_settings.DEFAULT_ADMIN_USERNAME,
                password_hash=get_password_hash(cfg_settings.DEFAULT_ADMIN_PASSWORD),
                role=UserRole.ADMIN,
                employee_code=None
            )
            db.add(admin_user)
            db.commit()
            logger.info(f"Created default admin user: {cfg_settings.DEFAULT_ADMIN_USERNAME}")
        
        # Create employee users for all employees without user accounts
        employees = db.query(Employee).all()
        for employee in employees:
            existing_user = db.query(User).filter(User.employee_code == employee.code).first()
            if not existing_user:
                # Create employee user account
                employee_user = User(
                    username=employee.code,
                    password_hash=get_password_hash(cfg_settings.DEFAULT_EMPLOYEE_PASSWORD),
                    role=UserRole.EMPLOYEE,
                    employee_code=employee.code
                )
                db.add(employee_user)
        
        db.commit()
        logger.info(f"Employee user accounts synchronized")
        
    except Exception as e:
        logger.error(f"Error initializing users: {e}")
        db.rollback()
    finally:
        db.close()

