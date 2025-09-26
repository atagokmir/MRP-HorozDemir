"""
Base Pydantic schemas for common request/response patterns.
Provides reusable schema components and response structures.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Any, Dict, Generic, TypeVar
from pydantic import BaseModel, Field, validator, ConfigDict
from enum import Enum


# Generic type for paginated responses
T = TypeVar('T')


class ResponseStatus(str, Enum):
    """Standard response status codes."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )


class TimestampMixin(BaseSchema):
    """Mixin for timestamp fields."""
    created_at: datetime
    updated_at: Optional[datetime] = None


class BaseResponse(BaseSchema):
    """Standard API response format."""
    status: ResponseStatus
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


class SuccessResponse(BaseResponse):
    """Success response format."""
    status: ResponseStatus = ResponseStatus.SUCCESS
    data: Optional[Any] = None


class ErrorResponse(BaseResponse):
    """Error response format."""
    status: ResponseStatus = ResponseStatus.ERROR
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class MessageResponse(BaseResponse):
    """Simple message response."""
    status: ResponseStatus = ResponseStatus.SUCCESS


# Pagination schemas
class PaginationParams(BaseSchema):
    """Pagination parameters for list requests."""
    page: int = Field(1, ge=1, description="Page number (1-based)")
    page_size: int = Field(20, ge=1, le=100, description="Number of items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size


class PaginationInfo(BaseSchema):
    """Pagination metadata."""
    total_count: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_previous: bool


class PaginatedResponse(BaseSchema, Generic[T]):
    """Generic paginated response."""
    items: List[T]
    pagination: PaginationInfo
    status: ResponseStatus = ResponseStatus.SUCCESS
    message: str = "Data retrieved successfully"
    timestamp: datetime = Field(default_factory=datetime.now)


# Filtering and sorting schemas
class SortOrder(str, Enum):
    """Sort order options."""
    ASC = "asc"
    DESC = "desc"


class FilterParams(BaseSchema):
    """Common filtering parameters."""
    search: Optional[str] = Field(None, description="Search term for text fields")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: SortOrder = Field(SortOrder.ASC, description="Sort direction")
    active_only: bool = Field(True, description="Show only active records")


class DateRangeFilter(BaseSchema):
    """Date range filtering."""
    start_date: Optional[date] = Field(None, description="Start date (inclusive)")
    end_date: Optional[date] = Field(None, description="End date (inclusive)")
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        """Validate end date is after start date."""
        start_date = values.get('start_date')
        if start_date and v and v < start_date:
            raise ValueError('end_date must be after start_date')
        return v


# Common field validators - simplified for compatibility
def validate_product_code(v: str) -> str:
    """Validate product code format."""
    if not v:
        raise ValueError('Product code is required')
    if not isinstance(v, str):
        raise ValueError('Product code must be a string')
    if not v.replace('-', '').replace('_', '').isalnum():
        raise ValueError('Product code must contain only alphanumeric characters, hyphens, and underscores')
    if len(v) < 3 or len(v) > 20:
        raise ValueError('Product code must be between 3 and 20 characters')
    return v.upper()


def validate_warehouse_code(v: str) -> str:
    """Validate warehouse code format."""
    if not v:
        raise ValueError('Warehouse code is required')
    if not isinstance(v, str):
        raise ValueError('Warehouse code must be a string')
    if not v.replace('-', '').replace('_', '').isalnum():
        raise ValueError('Warehouse code must contain only alphanumeric characters, hyphens, and underscores')
    if len(v) < 2 or len(v) > 20:
        raise ValueError('Warehouse code must be between 2 and 20 characters')
    return v.upper()


def validate_batch_number(v: str) -> str:
    """Validate batch number format."""
    if not v:
        raise ValueError('Batch number is required')
    if not isinstance(v, str):
        raise ValueError('Batch number must be a string')
    if len(v) < 3 or len(v) > 50:
        raise ValueError('Batch number must be between 3 and 50 characters')
    return v.upper()


# Common decimal validators
def validate_positive_decimal(v: Decimal, field_name: str = "Value") -> Decimal:
    """Validate decimal is positive."""
    if v is None:
        return v
    if v <= 0:
        raise ValueError(f'{field_name} must be greater than 0')
    return v


def validate_non_negative_decimal(v: Decimal, field_name: str = "Value") -> Decimal:
    """Validate decimal is non-negative."""
    if v is None:
        return v
    if v < 0:
        raise ValueError(f'{field_name} must be greater than or equal to 0')
    return v


def validate_percentage(v: Decimal, field_name: str = "Percentage") -> Decimal:
    """Validate decimal is a valid percentage (0-100)."""
    if v is None:
        return v
    if not (0 <= v <= 100):
        raise ValueError(f'{field_name} must be between 0 and 100')
    return v


def validate_rating(v: Decimal, field_name: str = "Rating") -> Decimal:
    """Validate decimal is a valid rating (0-5)."""
    if v is None:
        return v
    if not (0 <= v <= 5):
        raise ValueError(f'{field_name} must be between 0 and 5')
    return v


# Common enums
class QualityStatus(str, Enum):
    """Quality status options."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    QUARANTINE = "QUARANTINE"


class MovementType(str, Enum):
    """Stock movement types."""
    STOCK_IN = "STOCK_IN"
    STOCK_OUT = "STOCK_OUT"
    ADJUSTMENT = "ADJUSTMENT"
    TRANSFER = "TRANSFER"
    PRODUCTION_CONSUMPTION = "PRODUCTION_CONSUMPTION"
    PRODUCTION_OUTPUT = "PRODUCTION_OUTPUT"
    ALLOCATION = "ALLOCATION"
    RELEASE = "RELEASE"


class ProductType(str, Enum):
    """Product type categories."""
    RAW_MATERIAL = "RAW_MATERIAL"
    SEMI_FINISHED = "SEMI_FINISHED"
    FINISHED_PRODUCT = "FINISHED_PRODUCT"
    PACKAGING = "PACKAGING"


class WarehouseType(str, Enum):
    """Warehouse type categories."""
    RAW_MATERIALS = "RAW_MATERIALS"
    SEMI_FINISHED = "SEMI_FINISHED"
    FINISHED_PRODUCTS = "FINISHED_PRODUCTS"
    PACKAGING = "PACKAGING"


class ProductionOrderStatus(str, Enum):
    """Production order status options."""
    PLANNED = "PLANNED"
    RELEASED = "RELEASED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ON_HOLD = "ON_HOLD"


class PurchaseOrderStatus(str, Enum):
    """Purchase order status options."""
    DRAFT = "DRAFT"
    SENT = "SENT"
    CONFIRMED = "CONFIRMED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class BOMStatus(str, Enum):
    """BOM status options."""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    OBSOLETE = "OBSOLETE"
    ARCHIVED = "ARCHIVED"


class UserRole(str, Enum):
    """User role options."""
    ADMIN = "admin"
    PRODUCTION_MANAGER = "production_manager"
    INVENTORY_CLERK = "inventory_clerk"
    PROCUREMENT_OFFICER = "procurement_officer"
    VIEWER = "viewer"


class Permission(str, Enum):
    """Permission options."""
    # Master Data
    READ_WAREHOUSES = "read:warehouses"
    WRITE_WAREHOUSES = "write:warehouses"
    READ_PRODUCTS = "read:products"
    WRITE_PRODUCTS = "write:products"
    READ_SUPPLIERS = "read:suppliers"
    WRITE_SUPPLIERS = "write:suppliers"
    
    # Inventory
    READ_INVENTORY = "read:inventory"
    WRITE_INVENTORY = "write:inventory"
    ALLOCATE_STOCK = "allocate:stock"
    
    # Production
    READ_PRODUCTION = "read:production"
    WRITE_PRODUCTION = "write:production"
    APPROVE_PRODUCTION = "approve:production"
    
    # BOM
    READ_BOM = "read:bom"
    WRITE_BOM = "write:bom"
    
    # Procurement
    READ_PROCUREMENT = "read:procurement"
    WRITE_PROCUREMENT = "write:procurement"
    
    # Reporting
    READ_REPORTS = "read:reports"
    GENERATE_REPORTS = "generate:reports"


# ID validation schemas
class IDResponse(BaseSchema):
    """Response with ID for created resources."""
    id: int
    message: str = "Resource created successfully"
    status: ResponseStatus = ResponseStatus.SUCCESS
    timestamp: datetime = Field(default_factory=datetime.now)


class BulkOperationResponse(BaseSchema):
    """Response for bulk operations."""
    total_processed: int
    successful: int
    failed: int
    errors: List[str] = []
    status: ResponseStatus = ResponseStatus.SUCCESS
    message: str = "Bulk operation completed"
    timestamp: datetime = Field(default_factory=datetime.now)