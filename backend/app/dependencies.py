"""
FastAPI dependency injection system for the Horoz Demir MRP System.
Manages database sessions, authentication, authorization, and common utilities.
"""

from typing import AsyncGenerator, Optional, List
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
from passlib.context import CryptContext
import redis.asyncio as redis

from database import async_session
from app.config import settings
from models import User
from app.schemas.auth import UserInfo, TokenData
from app.exceptions import AuthenticationError, AuthorizationError


# Security setup
security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Database dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Database session dependency with automatic transaction management.
    Provides async database session with commit/rollback handling.
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Redis dependency
async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """Redis connection dependency for caching and session management."""
    if not settings.REDIS_URL:
        yield None
        return
        
    redis_client = redis.from_url(settings.REDIS_URL)
    try:
        yield redis_client
    finally:
        await redis_client.close()


# Authentication utilities
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token with expiration."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token with longer expiration."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


async def verify_token(token: str, token_type: str = "access") -> TokenData:
    """
    Verify JWT token and return token data.
    
    Args:
        token: JWT token string
        token_type: Expected token type (access/refresh)
        
    Returns:
        TokenData: Parsed token information
        
    Raises:
        AuthenticationError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Verify token type
        if payload.get("type") != token_type:
            raise AuthenticationError(f"Invalid token type. Expected {token_type}")
        
        # Extract user information
        user_id: int = payload.get("sub")
        username: str = payload.get("username")
        
        if user_id is None or username is None:
            raise AuthenticationError("Invalid token payload")
        
        return TokenData(user_id=user_id, username=username)
        
    except JWTError as e:
        raise AuthenticationError(f"Token validation failed: {str(e)}")


# Authentication dependencies
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> UserInfo:
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token
        session: Database session
        redis_client: Redis connection for token blacklist
        
    Returns:
        UserInfo: Current user information
        
    Raises:
        AuthenticationError: If authentication fails
    """
    if not credentials:
        raise AuthenticationError("Missing authentication token")
    
    # Verify token
    token_data = await verify_token(credentials.credentials, "access")
    
    # Check if token is blacklisted (logout)
    if redis_client:
        is_blacklisted = await redis_client.get(f"blacklist:{credentials.credentials}")
        if is_blacklisted:
            raise AuthenticationError("Token has been revoked")
    
    # Get user from database
    query = select(User).where(User.user_id == token_data.user_id)
    result = await session.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise AuthenticationError("User not found")
    
    if not user.is_active:
        raise AuthenticationError("User account is disabled")
    
    return UserInfo.from_orm(user)


async def get_current_active_user(
    current_user: UserInfo = Depends(get_current_user)
) -> UserInfo:
    """Get current active user (additional validation layer)."""
    if not current_user.is_active:
        raise AuthenticationError("User account is disabled")
    return current_user


# Authorization dependencies
class PermissionChecker:
    """Permission checker factory for role-based access control."""
    
    def __init__(self, required_permissions: List[str]):
        self.required_permissions = required_permissions
    
    def __call__(self, current_user: UserInfo = Depends(get_current_active_user)) -> UserInfo:
        """Check if user has required permissions."""
        user_permissions = set(current_user.permissions)
        required_permissions = set(self.required_permissions)
        
        if not required_permissions.issubset(user_permissions):
            missing_permissions = required_permissions - user_permissions
            raise AuthorizationError(
                f"Missing required permissions: {', '.join(missing_permissions)}"
            )
        
        return current_user


# Permission factory functions
def require_permissions(*permissions: str):
    """Create permission dependency for specific permissions."""
    return Depends(PermissionChecker(list(permissions)))


def require_admin():
    """Require admin role."""
    def admin_checker(current_user: UserInfo = Depends(get_current_active_user)) -> UserInfo:
        if current_user.role != "admin":
            raise AuthorizationError("Admin role required")
        return current_user
    
    return Depends(admin_checker)


def require_role(*roles: str):
    """Require specific user role(s)."""
    def role_checker(current_user: UserInfo = Depends(get_current_active_user)) -> UserInfo:
        if current_user.role not in roles:
            raise AuthorizationError(f"Required role: {', '.join(roles)}")
        return current_user
    
    return Depends(role_checker)


# Common query dependencies
class PaginationParams:
    """Common pagination parameters."""
    
    def __init__(
        self,
        page: int = 1,
        page_size: int = 20,
        max_page_size: int = 100
    ):
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), max_page_size)
        self.offset = (self.page - 1) * self.page_size
        self.limit = self.page_size


def get_pagination_params(
    page: int = 1,
    page_size: int = 20
) -> PaginationParams:
    """Get pagination parameters with validation."""
    return PaginationParams(page, page_size)


class FilterParams:
    """Common filtering parameters."""
    
    def __init__(
        self,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        active_only: bool = True
    ):
        self.search = search.strip() if search else None
        self.sort_by = sort_by
        self.sort_order = sort_order.lower() if sort_order.lower() in ["asc", "desc"] else "asc"
        self.active_only = active_only


def get_filter_params(
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
    active_only: bool = True
) -> FilterParams:
    """Get filtering parameters with validation."""
    return FilterParams(search, sort_by, sort_order, active_only)


# Request context dependencies
async def get_request_id(request: Request) -> str:
    """Get or generate unique request ID for logging."""
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        import uuid
        request_id = str(uuid.uuid4())
    return request_id


async def get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


# Utility dependencies
async def get_user_context(
    current_user: UserInfo = Depends(get_current_active_user),
    request_id: str = Depends(get_request_id),
    client_ip: str = Depends(get_client_ip)
) -> dict:
    """Get comprehensive user context for operations."""
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role,
        "request_id": request_id,
        "client_ip": client_ip,
        "timestamp": datetime.utcnow()
    }


# Database session with user context
async def get_db_with_user(
    session: AsyncSession = Depends(get_db),
    user_context: dict = Depends(get_user_context)
) -> AsyncSession:
    """Get database session with user context for audit trails."""
    # Add user context to session for audit purposes
    session.user_id = user_context["user_id"]
    session.request_id = user_context["request_id"]
    return session