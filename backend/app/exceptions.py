"""
Custom exception classes for the Horoz Demir MRP System.
Provides structured error handling with appropriate HTTP status codes.
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class MRPException(Exception):
    """Base exception class for MRP system."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None, 
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(MRPException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTHENTICATION_ERROR", status.HTTP_401_UNAUTHORIZED)


class AuthorizationError(MRPException):
    """Raised when user lacks required permissions."""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, "AUTHORIZATION_ERROR", status.HTTP_403_FORBIDDEN)


class ValidationError(MRPException):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(message, "VALIDATION_ERROR", status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class NotFoundError(MRPException):
    """Raised when requested resource is not found."""
    
    def __init__(self, resource: str, identifier: Any):
        message = f"{resource} with identifier '{identifier}' not found"
        details = {"resource": resource, "identifier": str(identifier)}
        super().__init__(message, "NOT_FOUND", status.HTTP_404_NOT_FOUND, details)


class ConflictError(MRPException):
    """Raised when operation conflicts with current state."""
    
    def __init__(self, message: str, resource: Optional[str] = None):
        details = {"resource": resource} if resource else {}
        super().__init__(message, "CONFLICT", status.HTTP_409_CONFLICT, details)


class InsufficientStockError(MRPException):
    """Raised when there's insufficient stock for allocation."""
    
    def __init__(self, message: str, product_id: Optional[int] = None, required: Optional[float] = None, available: Optional[float] = None):
        details = {}
        if product_id:
            details["product_id"] = product_id
        if required is not None:
            details["required_quantity"] = required
        if available is not None:
            details["available_quantity"] = available
        super().__init__(message, "INSUFFICIENT_STOCK", status.HTTP_409_CONFLICT, details)


class CircularBOMError(MRPException):
    """Raised when circular reference detected in BOM."""
    
    def __init__(self, message: str, bom_id: Optional[int] = None):
        details = {"bom_id": bom_id} if bom_id else {}
        super().__init__(message, "CIRCULAR_BOM", status.HTTP_400_BAD_REQUEST, details)


class InvalidBOMError(MRPException):
    """Raised when BOM validation fails."""
    
    def __init__(self, message: str, bom_id: Optional[int] = None):
        details = {"bom_id": bom_id} if bom_id else {}
        super().__init__(message, "INVALID_BOM", status.HTTP_400_BAD_REQUEST, details)


class ProductionOrderError(MRPException):
    """Raised for production order related errors."""
    
    def __init__(self, message: str, order_id: Optional[int] = None):
        details = {"production_order_id": order_id} if order_id else {}
        super().__init__(message, "PRODUCTION_ORDER_ERROR", status.HTTP_400_BAD_REQUEST, details)


class InvalidStatusTransitionError(MRPException):
    """Raised when attempting invalid status transition."""
    
    def __init__(self, current_status: str, target_status: str, resource_type: str = "resource"):
        message = f"Cannot transition {resource_type} from '{current_status}' to '{target_status}'"
        details = {
            "current_status": current_status,
            "target_status": target_status,
            "resource_type": resource_type
        }
        super().__init__(message, "INVALID_STATUS_TRANSITION", status.HTTP_400_BAD_REQUEST, details)


class BusinessRuleViolationError(MRPException):
    """Raised when business rule is violated."""
    
    def __init__(self, message: str, rule: str):
        details = {"business_rule": rule}
        super().__init__(message, "BUSINESS_RULE_VIOLATION", status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class ExternalServiceError(MRPException):
    """Raised when external service call fails."""
    
    def __init__(self, message: str, service: str):
        details = {"service": service}
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", status.HTTP_503_SERVICE_UNAVAILABLE, details)


class DataIntegrityError(MRPException):
    """Raised when data integrity constraint is violated."""
    
    def __init__(self, message: str, table: Optional[str] = None, constraint: Optional[str] = None):
        details = {}
        if table:
            details["table"] = table
        if constraint:
            details["constraint"] = constraint
        super().__init__(message, "DATA_INTEGRITY_ERROR", status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class RateLimitExceededError(MRPException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMIT_EXCEEDED", status.HTTP_429_TOO_MANY_REQUESTS)


class FileProcessingError(MRPException):
    """Raised when file processing fails."""
    
    def __init__(self, message: str, filename: Optional[str] = None):
        details = {"filename": filename} if filename else {}
        super().__init__(message, "FILE_PROCESSING_ERROR", status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class ReportGenerationError(MRPException):
    """Raised when report generation fails."""
    
    def __init__(self, message: str, report_type: Optional[str] = None):
        details = {"report_type": report_type} if report_type else {}
        super().__init__(message, "REPORT_GENERATION_ERROR", status.HTTP_500_INTERNAL_SERVER_ERROR, details)


class CacheError(MRPException):
    """Raised when cache operation fails."""
    
    def __init__(self, message: str = "Cache operation failed"):
        super().__init__(message, "CACHE_ERROR", status.HTTP_503_SERVICE_UNAVAILABLE)


# HTTP Exception factory functions
def create_http_exception(exc: MRPException) -> HTTPException:
    """Convert MRPException to FastAPI HTTPException."""
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "message": exc.message,
            "error_code": exc.error_code,
            "details": exc.details
        }
    )


# Common validation helpers
def validate_positive_decimal(value: float, field_name: str) -> None:
    """Validate that a decimal value is positive."""
    if value <= 0:
        raise ValidationError(f"{field_name} must be greater than 0", field_name)


def validate_non_negative_decimal(value: float, field_name: str) -> None:
    """Validate that a decimal value is non-negative."""
    if value < 0:
        raise ValidationError(f"{field_name} must be greater than or equal to 0", field_name)


def validate_percentage(value: float, field_name: str) -> None:
    """Validate that a value is a valid percentage (0-100)."""
    if not (0 <= value <= 100):
        raise ValidationError(f"{field_name} must be between 0 and 100", field_name)


def validate_rating(value: float, field_name: str) -> None:
    """Validate that a value is a valid rating (0-5)."""
    if not (0 <= value <= 5):
        raise ValidationError(f"{field_name} must be between 0 and 5", field_name)


def validate_priority(value: int, field_name: str) -> None:
    """Validate that a value is a valid priority (1-10)."""
    if not (1 <= value <= 10):
        raise ValidationError(f"{field_name} must be between 1 and 10", field_name)


def validate_required_field(value: Any, field_name: str) -> None:
    """Validate that a required field has a value."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{field_name} is required", field_name)