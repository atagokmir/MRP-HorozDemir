"""
Authentication and authorization schemas for the Horoz Demir MRP System.
Defines user authentication, token management, and permission models.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import Field, validator
from app.schemas.base import BaseSchema, UserRole, Permission


class TokenData(BaseSchema):
    """Token payload data."""
    user_id: int
    username: str


class UserLogin(BaseSchema):
    """User login request."""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=6, description="Password")


class RefreshTokenRequest(BaseSchema):
    """Refresh token request."""
    refresh_token: str = Field(..., description="Valid refresh token")


class UserInfo(BaseSchema):
    """Current user information."""
    user_id: int
    username: str
    full_name: str
    email: Optional[str] = None
    role: UserRole
    permissions: List[Permission]
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    
    @classmethod
    def from_orm(cls, user_orm):
        """Create UserInfo from ORM model."""
        # Get permissions based on role
        permissions = get_role_permissions(user_orm.role)
        
        return cls(
            user_id=user_orm.user_id,
            username=user_orm.username,
            full_name=user_orm.full_name,
            email=user_orm.email,
            role=user_orm.role,
            permissions=permissions,
            is_active=user_orm.is_active,
            last_login=user_orm.last_login,
            created_at=user_orm.created_at
        )


class TokenResponse(BaseSchema):
    """Token response after login."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiration in seconds")
    user_info: UserInfo


class UserCreate(BaseSchema):
    """Create new user request."""
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    password: str = Field(..., min_length=6, max_length=100)
    role: UserRole = UserRole.VIEWER
    is_active: bool = True
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, hyphens, and underscores')
        return v.lower()
    
    @validator('email')
    def validate_email(cls, v):
        """Basic email validation."""
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower() if v else v


class UserUpdate(BaseSchema):
    """Update user request."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    
    @validator('email')
    def validate_email(cls, v):
        """Basic email validation."""
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower() if v else v


class PasswordChange(BaseSchema):
    """Change password request."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=6, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """Validate password confirmation."""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class User(BaseSchema):
    """Full user information for admin operations."""
    user_id: int
    username: str
    full_name: str
    email: Optional[str] = None
    role: UserRole
    is_active: bool
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    account_locked_until: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class UserList(BaseSchema):
    """User list response."""
    users: List[User]
    total_count: int


# Role-Permission mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        Permission.READ_WAREHOUSES, Permission.WRITE_WAREHOUSES,
        Permission.READ_PRODUCTS, Permission.WRITE_PRODUCTS,
        Permission.READ_SUPPLIERS, Permission.WRITE_SUPPLIERS,
        Permission.READ_INVENTORY, Permission.WRITE_INVENTORY, Permission.ALLOCATE_STOCK,
        Permission.READ_PRODUCTION, Permission.WRITE_PRODUCTION, Permission.APPROVE_PRODUCTION,
        Permission.READ_BOM, Permission.WRITE_BOM,
        Permission.READ_PROCUREMENT, Permission.WRITE_PROCUREMENT,
        Permission.READ_REPORTS, Permission.GENERATE_REPORTS
    ],
    UserRole.PRODUCTION_MANAGER: [
        Permission.READ_WAREHOUSES, Permission.READ_PRODUCTS, Permission.READ_SUPPLIERS,
        Permission.READ_INVENTORY, Permission.ALLOCATE_STOCK,
        Permission.READ_PRODUCTION, Permission.WRITE_PRODUCTION, Permission.APPROVE_PRODUCTION,
        Permission.READ_BOM, Permission.WRITE_BOM,
        Permission.READ_PROCUREMENT,
        Permission.READ_REPORTS, Permission.GENERATE_REPORTS
    ],
    UserRole.INVENTORY_CLERK: [
        Permission.READ_WAREHOUSES, Permission.READ_PRODUCTS, Permission.READ_SUPPLIERS,
        Permission.READ_INVENTORY, Permission.WRITE_INVENTORY,
        Permission.READ_PRODUCTION,
        Permission.READ_BOM,
        Permission.READ_PROCUREMENT,
        Permission.READ_REPORTS
    ],
    UserRole.PROCUREMENT_OFFICER: [
        Permission.READ_WAREHOUSES, Permission.READ_PRODUCTS, Permission.READ_SUPPLIERS,
        Permission.READ_INVENTORY,
        Permission.READ_PRODUCTION,
        Permission.READ_BOM,
        Permission.READ_PROCUREMENT, Permission.WRITE_PROCUREMENT,
        Permission.READ_REPORTS
    ],
    UserRole.VIEWER: [
        Permission.READ_WAREHOUSES, Permission.READ_PRODUCTS, Permission.READ_SUPPLIERS,
        Permission.READ_INVENTORY,
        Permission.READ_PRODUCTION,
        Permission.READ_BOM,
        Permission.READ_PROCUREMENT,
        Permission.READ_REPORTS
    ]
}


def get_role_permissions(role: UserRole) -> List[Permission]:
    """Get permissions for a specific role."""
    return ROLE_PERMISSIONS.get(role, [])