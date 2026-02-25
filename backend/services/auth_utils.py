"""
Authentication utilities for JWT token handling
No passwords - auth via Google OAuth + Redmine DB validation
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from database import get_db, validate_user_in_redmine
from models.admin import Admin
from models.employee import Employee

import logging
logger = logging.getLogger(__name__)


# HTTP Bearer token security
security = HTTPBearer()


class TokenData(BaseModel):
    """Token data model"""
    email: Optional[str] = None
    role: Optional[str] = None


class UserResponse(BaseModel):
    """User response model"""
    email: str
    name: str
    role: str
    employee_code: Optional[str] = None


class CurrentUser(BaseModel):
    """Current authenticated user"""
    email: str
    name: str
    role: str  # "ADMIN" or "EMPLOYEE"
    employee_code: Optional[str] = None


def verify_google_token(token: str) -> dict | None:
    """
    Verify Google OAuth ID token.
    Returns user info dict or None if invalid.
    """
    print("TOKEN RECEIVED:", token[:30])
    print("CLIENT ID USED:", settings.GOOGLE_CLIENT_ID)
    if not settings.GOOGLE_CLIENT_ID:
        logger.warning("GOOGLE_CLIENT_ID not configured")
        return None

    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )

        return {
            "email": idinfo.get("email"),
            "name": idinfo.get("name", ""),
            "picture": idinfo.get("picture", "")
        }
    except Exception as e:
        logger.error(f"Google token verification failed: {e}")
        return None


def get_user_role(email: str, db: Session) -> tuple[str, Optional[str]]:
    """
    Determine user role from biometric DB admins table.
    Returns (role, employee_code)
    
    Per README:
      If email in admins table → role = ADMIN
      Else → role = EMPLOYEE
    """
    # Check admins table
    admin = db.query(Admin).filter(
        Admin.email == email,
        Admin.is_admin == True
    ).first()

    if admin:
        return "ADMIN", None

    # For employees, try to find their employee code
    employee = db.query(Employee).filter(Employee.email == email).first()
    employee_code = employee.code if employee else None

    return "EMPLOYEE", employee_code


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify JWT access token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise credentials_exception

    email = payload.get("sub")
    role = payload.get("role")
    name = payload.get("name", "")
    employee_code = payload.get("employee_code")

    if not email or not role:
        raise credentials_exception

    return CurrentUser(
        email=email,
        name=name,
        role=role,
        employee_code=employee_code
    )


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Require admin role for access"""
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_employee(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Require employee role for access"""
    if current_user.role != "EMPLOYEE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee access required"
        )
    return current_user
