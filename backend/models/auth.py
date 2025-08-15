"""
Authentication models for the Horoz Demir MRP System.
Contains User model for authentication and authorization.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import validates
from datetime import datetime
from typing import List

from .base import BaseModel, TimestampMixin


class User(BaseModel, TimestampMixin):
    """
    User model for authentication and authorization.
    Supports role-based access control for the MRP system.
    """
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default='viewer')
    is_active = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    permissions = Column(JSON, nullable=True, default=list)
    settings = Column(JSON, nullable=True, default=dict)
    notes = Column(Text, nullable=True)
    
    @validates('username')
    def validate_username(self, key, username):
        if not username or len(username) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if len(username) > 50:
            raise ValueError("Username cannot exceed 50 characters")
        return username.lower()
    
    @validates('email')
    def validate_email(self, key, email):
        if not email or '@' not in email:
            raise ValueError("Invalid email format")
        return email.lower()
    
    @validates('role')
    def validate_role(self, key, role):
        valid_roles = {'admin', 'manager', 'operator', 'viewer'}
        if role not in valid_roles:
            raise ValueError(f"Role must be one of: {valid_roles}")
        return role
    
    def is_locked(self) -> bool:
        """Check if user account is locked due to failed login attempts."""
        if self.locked_until:
            return datetime.utcnow() < self.locked_until
        return False
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        if not self.is_active:
            return False
        
        # Admin has all permissions
        if self.role == 'admin':
            return True
        
        # Check specific permissions
        user_permissions = self.permissions or []
        return permission in user_permissions
    
    def get_role_permissions(self) -> List[str]:
        """Get default permissions for user's role."""
        role_permissions = {
            'admin': [
                'user.create', 'user.read', 'user.update', 'user.delete',
                'product.create', 'product.read', 'product.update', 'product.delete',
                'inventory.create', 'inventory.read', 'inventory.update', 'inventory.delete',
                'bom.create', 'bom.read', 'bom.update', 'bom.delete',
                'production.create', 'production.read', 'production.update', 'production.delete',
                'procurement.create', 'procurement.read', 'procurement.update', 'procurement.delete',
                'reports.read', 'system.manage'
            ],
            'manager': [
                'product.read', 'product.update',
                'inventory.read', 'inventory.update',
                'bom.read', 'bom.update',
                'production.create', 'production.read', 'production.update',
                'procurement.create', 'procurement.read', 'procurement.update',
                'reports.read'
            ],
            'operator': [
                'product.read',
                'inventory.read', 'inventory.update',
                'production.read', 'production.update',
                'procurement.read'
            ],
            'viewer': [
                'product.read',
                'inventory.read',
                'production.read',
                'procurement.read',
                'reports.read'
            ]
        }
        return role_permissions.get(self.role, [])
    
    def update_last_login(self):
        """Update last login timestamp."""
        self.last_login = datetime.utcnow()
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def record_failed_login(self):
        """Record a failed login attempt."""
        self.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts for 30 minutes
        if self.failed_login_attempts >= 5:
            from datetime import timedelta
            self.locked_until = datetime.utcnow() + timedelta(minutes=30)
    
    def __repr__(self):
        return f"<User(id={self.user_id}, username='{self.username}', role='{self.role}')>"