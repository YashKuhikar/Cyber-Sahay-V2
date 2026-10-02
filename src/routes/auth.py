from __future__ import annotations

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..database.db import get_db
from ..database.models import User, FIRRecord, ChatSession
from ..services.auth_service import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter()


# ==========================================================
# Pydantic Schemas
# ==========================================================

import re

class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, example="John Doe")
    email: str = Field(..., example="john.doe@example.com")
    phone: Optional[str] = Field(None, example="9876543210")
    password: str = Field(..., min_length=6, max_length=100, example="securePassword123")
    emergency_contact: Optional[str] = Field(None, example="9123456780 (Father)")


class UserLoginRequest(BaseModel):
    email: str = Field(..., example="john.doe@example.com")
    password: str = Field(..., example="securePassword123")


class UserProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = None
    emergency_contact: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=6)


class UserResponseData(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str] = None
    emergency_contact: Optional[str] = None
    role: str
    created_at: datetime


class AuthResponse(BaseModel):
    success: bool
    message: str
    access_token: str
    token_type: str = "bearer"
    user: UserResponseData


class UserProfileResponse(BaseModel):
    success: bool
    user: UserResponseData
    total_firs: int
    total_sessions: int


from ..security.rate_limiter import rate_limit
from ..security.sanitizer import sanitize_input


# ==========================================================
# Register
# ==========================================================

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))],
    summary="Register a new CyberSahay user (Rate Limit: 5/min)",
)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    normalized_email = sanitize_input(request.email).lower().strip()
    name = sanitize_input(request.name).strip()
    phone = sanitize_input(request.phone).strip() if request.phone else None
    emergency_contact = sanitize_input(request.emergency_contact).strip() if request.emergency_contact else None

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalized_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address.",
        )

    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    new_user = User(
        name=name,
        email=normalized_email,
        phone=phone,
        hashed_password=hash_password(request.password),
        emergency_contact=emergency_contact,
        role="user",
        is_active=True,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": str(new_user.id), "email": new_user.email})

    return AuthResponse(
        success=True,
        message="User registered successfully.",
        access_token=token,
        token_type="bearer",
        user=UserResponseData(
            id=new_user.id,
            name=new_user.name,
            email=new_user.email,
            phone=new_user.phone,
            emergency_contact=new_user.emergency_contact,
            role=new_user.role,
            created_at=new_user.created_at,
        ),
    )


# ==========================================================
# Login
# ==========================================================

@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))],
    summary="Authenticate user and get JWT access token (Rate Limit: 5/min)",
)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
):
    normalized_email = sanitize_input(request.email).lower().strip()

    user = db.query(User).filter(User.email == normalized_email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been disabled.",
        )

    token = create_access_token({"sub": str(user.id), "email": user.email})

    return AuthResponse(
        success=True,
        message="Login successful.",
        access_token=token,
        token_type="bearer",
        user=UserResponseData(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            emergency_contact=user.emergency_contact,
            role=user.role,
            created_at=user.created_at,
        ),
    )


# ==========================================================
# Current User Profile
# ==========================================================

@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current authenticated user profile & stats",
)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total_firs = db.query(FIRRecord).filter(FIRRecord.user_id == current_user.id).count()
    total_sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).count()

    return UserProfileResponse(
        success=True,
        user=UserResponseData(
            id=current_user.id,
            name=current_user.name,
            email=current_user.email,
            phone=current_user.phone,
            emergency_contact=current_user.emergency_contact,
            role=current_user.role,
            created_at=current_user.created_at,
        ),
        total_firs=total_firs,
        total_sessions=total_sessions,
    )


# ==========================================================
# Update Profile
# ==========================================================

@router.put(
    "/profile",
    response_model=AuthResponse,
    summary="Update current user profile and credentials",
)
def update_profile(
    request: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if request.name:
        current_user.name = request.name.strip()

    if request.phone is not None:
        current_user.phone = request.phone.strip() if request.phone else None

    if request.emergency_contact is not None:
        current_user.emergency_contact = request.emergency_contact.strip() if request.emergency_contact else None

    if request.new_password:
        if not request.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required to set a new password.",
            )
        if not verify_password(request.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password.",
            )
        current_user.hashed_password = hash_password(request.new_password)

    db.commit()
    db.refresh(current_user)

    token = create_access_token({"sub": str(current_user.id), "email": current_user.email})

    return AuthResponse(
        success=True,
        message="Profile updated successfully.",
        access_token=token,
        token_type="bearer",
        user=UserResponseData(
            id=current_user.id,
            name=current_user.name,
            email=current_user.email,
            phone=current_user.phone,
            emergency_contact=current_user.emergency_contact,
            role=current_user.role,
            created_at=current_user.created_at,
        ),
    )
