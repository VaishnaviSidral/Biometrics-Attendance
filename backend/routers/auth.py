"""
Authentication Router
Handles Google OAuth login and user validation via Redmine DB
No passwords stored - per README rules
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import timedelta
import logging

from database import get_db, validate_user_in_redmine
from services.auth_utils import (
    verify_google_token,
    get_user_role,
    create_access_token,
    get_current_user,
    CurrentUser,
    UserResponse
)
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


class GoogleLoginRequest(BaseModel):
    """Google OAuth login request"""
    credential: str  # Google ID token


class EmailLoginRequest(BaseModel):
    """Simple email login request (password not validated)"""
    email: str
    password: Optional[str] = None  # Accepted but never checked


class LoginResponse(BaseModel):
    """Login response model"""
    access_token: str
    token_type: str
    user: UserResponse


class AuthConfigResponse(BaseModel):
    """Auth configuration for frontend"""
    google_client_id: str
    google_enabled: bool


@router.get("/config", response_model=AuthConfigResponse)
async def get_auth_config():
    """
    Get auth configuration for frontend.
    Returns Google Client ID so frontend can render Sign-In button.
    """
    return AuthConfigResponse(
        google_client_id=settings.GOOGLE_CLIENT_ID or "",
        google_enabled=settings.GOOGLE_ENABLED
    )



@router.post("/google", response_model=LoginResponse)
async def google_login(
    login_data: GoogleLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login via Google OAuth.
    
    Flow:
    1. Verify Google ID token
    2. Get user email
    3. Validate in Redmine DB (READ ONLY)
    4. Determine role from biometric.admins
    5. Create JWT
    """
    # Step 1: Verify Google token
    google_user = verify_google_token(login_data.credential)
    if not google_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credentials"
        )

    email = google_user["email"]
    name = google_user.get("name", email)

    # Step 2: Validate in Redmine DB (READ ONLY)
    redmine_user = validate_user_in_redmine(email)
    if not redmine_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found in organization directory. Access denied."
        )

    # Use Redmine name if available
    name = f"{redmine_user['firstname']} {redmine_user['lastname']}".strip() or name

    # Step 3: Determine role from admins table
    role, employee_code = get_user_role(email, db)

    # Step 4: Create JWT
    access_token = create_access_token(
        data={
            "sub": email,
            "role": role,
            "name": name,
            "employee_code": employee_code
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            email=email,
            name=name,
            role=role,
            employee_code=employee_code
        )
    )


@router.post("/login", response_model=LoginResponse)
async def email_login(
    login_data: EmailLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Simple email login (password can be anything).
    
    Flow:
    1. Get user email from request
    2. Validate in Redmine DB (READ ONLY)
    3. Determine role from biometric.admins
    4. Create JWT
    
    Note: Password is accepted but NEVER validated per README rules.
    """
    email = login_data.email.strip().lower()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )

    # Step 1: Validate in Redmine DB (READ ONLY)
    redmine_user = validate_user_in_redmine(email)
    if not redmine_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found in organization directory. Access denied."
        )

    name = f"{redmine_user['firstname']} {redmine_user['lastname']}".strip()

    # Step 2: Determine role from admins table
    role, employee_code = get_user_role(email, db)

    # Step 3: Create JWT
    access_token = create_access_token(
        data={
            "sub": email,
            "role": role,
            "name": name,
            "employee_code": employee_code
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            email=email,
            name=name,
            role=role,
            employee_code=employee_code
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user)
):
    """Get current authenticated user information"""
    return UserResponse(
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        employee_code=current_user.employee_code
    )


@router.post("/logout")
async def logout():
    """Logout endpoint (client-side token removal)"""
    return {"message": "Successfully logged out"}
