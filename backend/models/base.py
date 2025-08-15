"""
Base SQLAlchemy configuration and shared components for Horoz Demir MRP System.
This module provides the declarative base and common mixins for all ORM models.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, Boolean, String, func, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Session


# Create the declarative base class
Base = declarative_base()


class TimestampMixin:
    """
    Mixin to add created_at and updated_at timestamp columns to models.
    Automatically manages timestamp updates using database triggers.
    """
    
    @declared_attr
    def created_at(cls):
        return Column(
            DateTime,
            nullable=False,
            default=func.current_timestamp(),
            server_default=func.current_timestamp(),
            comment="Record creation timestamp"
        )
    
    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime,
            nullable=False,
            default=func.current_timestamp(),
            server_default=func.current_timestamp(),
            onupdate=func.current_timestamp(),
            comment="Record last update timestamp"
        )


class ActiveRecordMixin:
    """
    Mixin to add soft delete functionality with is_active flag.
    Provides methods for soft delete operations.
    """
    
    @declared_attr
    def is_active(cls):
        return Column(
            Boolean,
            nullable=False,
            default=True,
            server_default=text('true'),
            comment="Record active status (soft delete flag)"
        )
    
    def soft_delete(self):
        """Mark record as inactive (soft delete)"""
        self.is_active = False
    
    def restore(self):
        """Restore soft-deleted record"""
        self.is_active = True
    
    @classmethod
    def active_only(cls):
        """Query filter for active records only"""
        return cls.is_active == True
    
    @classmethod
    def inactive_only(cls):
        """Query filter for inactive records only"""
        return cls.is_active == False


class BaseModel(Base, TimestampMixin):
    """
    Abstract base model with common functionality.
    All MRP models should inherit from this base class.
    """
    __abstract__ = True
    
    def to_dict(self, exclude_private: bool = True) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Args:
            exclude_private: If True, exclude columns starting with underscore
            
        Returns:
            Dictionary representation of the model
        """
        result = {}
        for column in self.__table__.columns:
            if exclude_private and column.name.startswith('_'):
                continue
            value = getattr(self, column.name)
            # Convert Decimal to float for JSON serialization
            if isinstance(value, Decimal):
                result[column.name] = float(value)
            # Convert datetime to ISO format string
            elif isinstance(value, datetime):
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value
        return result
    
    def update_from_dict(self, data: Dict[str, Any], exclude_keys: Optional[set] = None) -> None:
        """
        Update model instance from dictionary.
        
        Args:
            data: Dictionary with new values
            exclude_keys: Set of keys to exclude from update
        """
        if exclude_keys is None:
            exclude_keys = {'created_at', 'updated_at'}
        
        for key, value in data.items():
            if key in exclude_keys:
                continue
            if hasattr(self, key):
                setattr(self, key, value)
    
    def __repr__(self) -> str:
        """Generic string representation of the model"""
        class_name = self.__class__.__name__
        primary_keys = [key.name for key in self.__table__.primary_key]
        
        if primary_keys:
            pk_values = [f"{key}={getattr(self, key)}" for key in primary_keys]
            return f"<{class_name}({', '.join(pk_values)})>"
        else:
            return f"<{class_name}()>"


class AuditMixin:
    """
    Mixin to add audit trail fields for tracking who created/modified records.
    """
    
    @declared_attr
    def created_by(cls):
        return Column(
            String(100),
            nullable=True,
            comment="User who created the record"
        )
    
    @declared_attr
    def updated_by(cls):
        return Column(
            String(100),
            nullable=True,
            comment="User who last updated the record"
        )
    
    def set_audit_fields(self, user_id: str, is_update: bool = False):
        """
        Set audit fields for create or update operations.
        
        Args:
            user_id: ID of the user performing the operation
            is_update: True for update operations, False for create
        """
        if not is_update:
            self.created_by = user_id
        self.updated_by = user_id


# Event listeners for automatic audit trail updates
@event.listens_for(Session, 'before_flush')
def before_flush_listener(session, flush_context, instances):
    """
    Automatically set updated_by for modified instances.
    This requires the session to have a 'user_id' attribute set.
    """
    user_id = getattr(session, 'user_id', None)
    
    if user_id:
        for obj in session.dirty:
            if hasattr(obj, 'updated_by'):
                obj.updated_by = user_id
        
        for obj in session.new:
            if hasattr(obj, 'created_by') and obj.created_by is None:
                obj.created_by = user_id
            if hasattr(obj, 'updated_by'):
                obj.updated_by = user_id


def set_session_user(session: Session, user_id: str):
    """
    Set the user ID on a session for audit trail tracking.
    
    Args:
        session: SQLAlchemy session
        user_id: ID of the current user
    """
    session.user_id = user_id


# Validation helpers
def validate_decimal_range(value: Decimal, min_val: Decimal = None, max_val: Decimal = None) -> bool:
    """
    Validate decimal value is within specified range.
    
    Args:
        value: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        
    Returns:
        True if value is valid
    """
    if value is None:
        return False
    
    if min_val is not None and value < min_val:
        return False
    
    if max_val is not None and value > max_val:
        return False
    
    return True


def validate_percentage(value: Decimal) -> bool:
    """
    Validate percentage value is between 0 and 100.
    
    Args:
        value: Percentage value to validate
        
    Returns:
        True if value is valid percentage
    """
    return validate_decimal_range(value, Decimal('0'), Decimal('100'))


def validate_rating(value: Decimal) -> bool:
    """
    Validate rating value is between 0.0 and 5.0.
    
    Args:
        value: Rating value to validate
        
    Returns:
        True if value is valid rating
    """
    return validate_decimal_range(value, Decimal('0.0'), Decimal('5.0'))


# Custom column types for common use cases
class PercentageColumn:
    """Factory for percentage columns with validation"""
    
    @staticmethod
    def create(name: str, nullable: bool = False, default: Decimal = Decimal('0')):
        from sqlalchemy import DECIMAL
        return Column(
            name,
            DECIMAL(5, 2),
            nullable=nullable,
            default=default,
            comment=f"{name} as percentage (0.00-100.00)"
        )


class RatingColumn:
    """Factory for rating columns with validation"""
    
    @staticmethod
    def create(name: str, nullable: bool = False, default: Decimal = Decimal('0.0')):
        from sqlalchemy import DECIMAL
        return Column(
            name,
            DECIMAL(3, 2),
            nullable=nullable,
            default=default,
            comment=f"{name} rating (0.00-5.00)"
        )


class CurrencyColumn:
    """Factory for currency/cost columns with validation"""
    
    @staticmethod
    def create(name: str, nullable: bool = False, default: Decimal = Decimal('0')):
        from sqlalchemy import DECIMAL
        return Column(
            name,
            DECIMAL(15, 4),
            nullable=nullable,
            default=default,
            comment=f"{name} in currency units"
        )


class QuantityColumn:
    """Factory for quantity columns with validation"""
    
    @staticmethod
    def create(name: str, nullable: bool = False, default: Decimal = Decimal('0')):
        from sqlalchemy import DECIMAL
        return Column(
            name,
            DECIMAL(15, 4),
            nullable=nullable,
            default=default,
            comment=f"{name} quantity"
        )