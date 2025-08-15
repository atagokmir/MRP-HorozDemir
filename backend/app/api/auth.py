"""
Authentication API endpoints for the Horoz Demir MRP System.
Handles user login, token management, and user profile operations.
"""

from datetime import datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select, update
import redis.asyncio as redis

from app.dependencies import (
    get_db, get_redis, get_current_user, get_current_active_user,
    create_access_token, create_refresh_token, verify_token,
    verify_password, get_password_hash, security
)
from app.config import settings
from app.exceptions import AuthenticationError, ValidationError, NotFoundError
from app.schemas.auth import (
    UserLogin, RefreshTokenRequest, TokenResponse, UserInfo,
    UserCreate, UserUpdate, PasswordChange, User
)
from models.auth import User as UserModel


router = APIRouter()


@router.post("/login")  # TODO: response_model=TokenResponse
def login(
    user_credentials: UserLogin,
    session: Session = Depends(get_db)
    # redis_client: redis.Redis = Depends(get_redis)  # Disabled for debugging
) -> TokenResponse:
    """
    Authenticate user and return JWT tokens.
    
    - **username**: User's username
    - **password**: User's password
    
    Returns access token (15 min) and refresh token (7 days).
    """
    # Find user by username
    query = select(UserModel).where(UserModel.username == user_credentials.username.lower())
    result = session.execute(query)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(user_credentials.password, user.hashed_password):
        # Increment failed login attempts
        if user:
            session.execute(
                update(UserModel)
                .where(UserModel.user_id == user.user_id)
                .values(
                    failed_login_attempts=UserModel.failed_login_attempts + 1,
                    last_failed_login=datetime.now()
                )
            )
            session.commit()
        
        raise AuthenticationError("Invalid username or password")
    
    # Check if user is active
    if not user.is_active:
        raise AuthenticationError("User account is disabled")
    
    # Check if account is locked
    if (user.locked_until and 
        user.locked_until > datetime.now()):
        raise AuthenticationError("Account is locked. Try again later.")
    
    # Check failed login attempts
    if user.failed_login_attempts >= 5:
        # Lock account for 30 minutes
        lock_until = datetime.now() + timedelta(minutes=30)
        session.execute(
            update(UserModel)
            .where(UserModel.user_id == user.user_id)
            .values(locked_until=lock_until)
        )
        session.commit()
        raise AuthenticationError("Account locked due to too many failed attempts")
    
    # Create tokens
    token_data = {
        "sub": str(user.user_id),
        "username": user.username,
        "role": user.role
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # Update last login and reset failed attempts
    session.execute(
        update(UserModel)
        .where(UserModel.user_id == user.user_id)
        .values(
            last_login=datetime.now(),
            failed_login_attempts=0,
            locked_until=None
        )
    )
    session.commit()
    
    # Store refresh token in Redis for revocation tracking
    # TODO: Re-enable Redis when available
    # if redis_client:
    #     await redis_client.set(
    #         f"refresh_token:{user.user_id}",
    #         refresh_token,
    #         ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    #     )
    
    # Create user info
    user_info = UserInfo.from_orm(user)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_info=user_info
    )


@router.post("/refresh")  # TODO: response_model=TokenResponse
def refresh_token(
    refresh_request: RefreshTokenRequest,
    session: Session = Depends(get_db),
    # redis_client: redis.Redis = Depends(get_redis)  # Disabled for debugging
) -> TokenResponse:
    """
    Refresh access token using refresh token.
    
    - **refresh_token**: Valid refresh token from login
    
    Returns new access token with same expiration.
    """
    # Verify refresh token
    token_data = verify_token(refresh_request.refresh_token, "refresh")
    
    # Check if refresh token is in Redis (not revoked)
    # TODO: Re-enable Redis when available
    # if redis_client:
    #     stored_token = await redis_client.get(f"refresh_token:{token_data.user_id}")
    #     if not stored_token or stored_token.decode() != refresh_request.refresh_token:
    #         raise AuthenticationError("Invalid or revoked refresh token")
    
    # Get user from database
    user = session.get(UserModel, token_data.user_id)
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    
    # Create new access token
    new_token_data = {
        "sub": str(user.user_id),
        "username": user.username,
        "role": user.role
    }
    
    access_token = create_access_token(new_token_data)
    
    # Create user info
    user_info = UserInfo.from_orm(user)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_request.refresh_token,  # Keep same refresh token
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_info=user_info
    )


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: UserInfo = Depends(get_current_user),
    # redis_client: redis.Redis = Depends(get_redis)  # Disabled for debugging
) -> dict[str, Any]:
    """
    Logout user and revoke tokens.
    
    Blacklists the current access token and removes refresh token.
    """
    if not credentials:
        raise AuthenticationError("No token provided")
    
    # Blacklist access token
    # TODO: Re-enable Redis blacklisting for production
    # if redis_client:
    #     # Calculate remaining time until token expiry
    #     try:
    #         import jwt
    #         payload = jwt.decode(
    #             credentials.credentials, 
    #             settings.SECRET_KEY, 
    #             algorithms=[settings.ALGORITHM],
    #             options={"verify_exp": False}
    #         )
    #         exp = payload.get("exp")
    #         if exp:
    #             remaining_time = exp - int(datetime.now().timestamp())
    #             if remaining_time > 0:
    #                 await redis_client.set(
    #                     f"blacklist:{credentials.credentials}",
    #                     "revoked",
    #                     ex=remaining_time
    #                 )
    #         # Remove refresh token
    #         await redis_client.delete(f"refresh_token:{current_user.user_id}")
    #     except Exception:
    #         pass  # If token parsing fails, we still continue with logout
    
    return {
        "status": "success",
        "message": "Successfully logged out",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/me")  # TODO: response_model=UserInfo
def get_current_user_info(
    current_user: UserInfo = Depends(get_current_active_user)
) -> UserInfo:
    """
    Get current user information.
    
    Returns detailed information about the authenticated user.
    """
    return current_user


@router.put("/me")  # TODO: response_model=UserInfo
def update_current_user(
    user_update: UserUpdate,
    current_user: UserInfo = Depends(get_current_active_user),
    session: Session = Depends(get_db)
) -> UserInfo:
    """
    Update current user information.
    
    - **full_name**: Updated full name
    - **email**: Updated email address
    
    Only users can update their own basic information.
    Role changes require admin privileges.
    """
    # Get user from database
    user = session.get(UserModel, current_user.user_id)
    if not user:
        raise NotFoundError("User", current_user.user_id)
    
    # Update allowed fields
    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    if user_update.email is not None:
        user.email = user_update.email.lower() if user_update.email else None
    
    # Role and active status can only be changed by admin
    # This endpoint doesn't allow those changes for security
    
    user.updated_at = datetime.now()
    session.commit()
    session.refresh(user)
    
    return UserInfo.from_orm(user)


@router.post("/change-password")
def change_password(
    password_change: PasswordChange,
    current_user: UserInfo = Depends(get_current_active_user),
    session: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Change user password.
    
    - **current_password**: Current password for verification
    - **new_password**: New password (minimum 6 characters)
    - **confirm_password**: Password confirmation
    """
    # Get user from database
    user = session.get(UserModel, current_user.user_id)
    if not user:
        raise NotFoundError("User", current_user.user_id)
    
    # Verify current password
    if not verify_password(password_change.current_password, user.hashed_password):
        raise AuthenticationError("Current password is incorrect")
    
    # Update password
    user.hashed_password = get_password_hash(password_change.new_password)
    user.password_changed_at = datetime.now()
    user.updated_at = datetime.now()
    
    session.commit()
    
    return {
        "status": "success",
        "message": "Password changed successfully",
        "timestamp": datetime.now().isoformat()
    }


# Admin-only endpoints for user management
@router.post("/users")  # TODO: response_model=User
def create_user(
    user_create: UserCreate,
    current_user: UserInfo = Depends(get_current_active_user),
    session: Session = Depends(get_db)
) -> User:
    """
    Create new user (Admin only).
    
    - **username**: Unique username
    - **full_name**: User's full name
    - **email**: Email address (optional)
    - **password**: Initial password
    - **role**: User role
    - **is_active**: Active status
    """
    # Check admin permission
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create users"
        )
    
    # Check if username already exists
    query = select(UserModel).where(UserModel.username == user_create.username.lower())
    result = session.execute(query)
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise ValidationError("Username already exists", "username")
    
    # Create new user
    new_user = UserModel(
        username=user_create.username.lower(),
        full_name=user_create.full_name,
        email=user_create.email.lower() if user_create.email else None,
        hashed_password=get_password_hash(user_create.password),
        role=user_create.role,
        is_active=user_create.is_active,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    return User.from_orm(new_user)


@router.get("/users")  # TODO: response_model=list[User])
def list_users(
    current_user: UserInfo = Depends(get_current_active_user),
    session: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> list[User]:
    """
    List all users (Admin only).
    
    Returns paginated list of users with their information.
    """
    # Check admin permission
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can list users"
        )
    
    query = select(UserModel).offset(skip).limit(limit).order_by(UserModel.username)
    result = session.execute(query)
    users = result.scalars().all()
    
    return [User.from_orm(user) for user in users]


@router.put("/users/{user_id}")  # TODO: response_model=User
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: UserInfo = Depends(get_current_active_user),
    session: Session = Depends(get_db)
) -> User:
    """
    Update user (Admin only).
    
    - **full_name**: Updated full name
    - **email**: Updated email address
    - **role**: Updated user role
    - **is_active**: Updated active status
    """
    # Check admin permission
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update users"
        )
    
    # Get user from database
    user = session.get(UserModel, user_id)
    if not user:
        raise NotFoundError("User", user_id)
    
    # Update fields
    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    if user_update.email is not None:
        user.email = user_update.email.lower() if user_update.email else None
    if user_update.role is not None:
        user.role = user_update.role
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
    
    user.updated_at = datetime.now()
    session.commit()
    session.refresh(user)
    
    return User.from_orm(user)