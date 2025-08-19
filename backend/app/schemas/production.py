"""
Pydantic schemas for Production Order API endpoints.
Handles request/response validation and documentation.
"""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import date, datetime
from pydantic import BaseModel, Field, validator, ConfigDict

from .base import TimestampMixin, ProductionOrderStatus


class ProductionOrderComponentResponse(BaseModel):
    """Schema for production order component response."""
    model_config = ConfigDict(from_attributes=True)
    
    po_component_id: int
    component_product_id: int
    required_quantity: Decimal = Field(..., description="Required quantity of component")
    allocated_quantity: Decimal = Field(..., description="Allocated quantity")
    consumed_quantity: Decimal = Field(..., description="Consumed quantity")
    unit_cost: Decimal = Field(..., description="Unit cost")
    total_cost: Optional[Decimal] = Field(None, description="Total cost (calculated)")
    allocation_status: str = Field(..., description="Allocation status")
    
    # Related object data (when included)
    component_product: Optional[Dict[str, Any]] = None


class StockAllocationResponse(BaseModel):
    """Schema for stock allocation response."""
    model_config = ConfigDict(from_attributes=True)
    
    allocation_id: int
    inventory_item_id: int
    allocated_quantity: Decimal = Field(..., description="Allocated quantity")
    consumed_quantity: Decimal = Field(..., description="Consumed quantity")
    remaining_allocation: Optional[Decimal] = Field(None, description="Remaining allocation")
    allocation_date: datetime
    consumption_date: Optional[datetime] = None
    status: str = Field(..., description="Allocation status")
    
    # Related object data (when included)
    inventory_item: Optional[Dict[str, Any]] = None


class ProductionOrderBase(BaseModel):
    """Base schema for production order."""
    product_id: int = Field(..., description="ID of the product to produce")
    bom_id: int = Field(..., description="ID of the BOM to use")
    warehouse_id: int = Field(..., description="ID of the target warehouse")
    planned_start_date: Optional[date] = Field(None, description="Planned start date")
    planned_completion_date: Optional[date] = Field(None, description="Planned completion date")
    planned_quantity: Decimal = Field(..., gt=0, description="Planned production quantity")
    priority: int = Field(5, ge=1, le=10, description="Priority from 1 (highest) to 10 (lowest)")
    notes: Optional[str] = Field(None, description="Additional notes")

    @validator('planned_completion_date')
    def completion_after_start(cls, v, values):
        """Validate completion date is after start date."""
        start_date = values.get('planned_start_date')
        if v and start_date and v <= start_date:
            raise ValueError('planned_completion_date must be after planned_start_date')
        return v


class ProductionOrderCreate(ProductionOrderBase):
    """Schema for creating production order."""
    pass


class ProductionOrderUpdate(BaseModel):
    """Schema for updating production order."""
    planned_start_date: Optional[date] = Field(None, description="Planned start date")
    planned_completion_date: Optional[date] = Field(None, description="Planned completion date")
    planned_quantity: Optional[Decimal] = Field(None, gt=0, description="Planned production quantity")
    priority: Optional[int] = Field(None, ge=1, le=10, description="Priority from 1 (highest) to 10 (lowest)")
    status: Optional[ProductionOrderStatus] = Field(None, description="Production order status")
    notes: Optional[str] = Field(None, description="Additional notes")

    @validator('planned_completion_date')
    def completion_after_start(cls, v, values):
        """Validate completion date is after start date."""
        start_date = values.get('planned_start_date')
        if v and start_date and v <= start_date:
            raise ValueError('planned_completion_date must be after planned_start_date')
        return v


class ProductionOrderStatusUpdate(BaseModel):
    """Schema for updating production order status."""
    status: ProductionOrderStatus = Field(..., description="New production order status")
    notes: Optional[str] = Field(None, description="Status change notes")


class ProductionOrderCompletion(BaseModel):
    """Schema for completing production order."""
    completed_quantity: Decimal = Field(..., gt=0, description="Quantity completed")
    scrapped_quantity: Optional[Decimal] = Field(Decimal('0'), ge=0, description="Quantity scrapped")
    notes: Optional[str] = Field(None, description="Completion notes")

    @validator('scrapped_quantity')
    def validate_scrapped_quantity(cls, v):
        """Ensure scrapped quantity is valid."""
        if v and v < 0:
            raise ValueError('scrapped_quantity must be non-negative')
        return v or Decimal('0')


class ProductionOrderResponse(ProductionOrderBase, TimestampMixin):
    """Schema for production order response."""
    model_config = ConfigDict(from_attributes=True)
    
    production_order_id: int
    order_number: str = Field(..., description="Unique production order number")
    order_date: date
    actual_start_date: Optional[date] = None
    actual_completion_date: Optional[date] = None
    completed_quantity: Decimal = Field(..., description="Completed quantity")
    scrapped_quantity: Decimal = Field(..., description="Scrapped quantity")
    status: ProductionOrderStatus
    estimated_cost: Decimal = Field(..., description="Estimated total cost")
    actual_cost: Decimal = Field(..., description="Actual total cost")
    
    # Computed properties
    remaining_quantity: Optional[Decimal] = Field(None, description="Remaining quantity to complete")
    completion_percentage: Optional[Decimal] = Field(None, description="Completion percentage")
    is_overdue: Optional[bool] = Field(None, description="Whether order is overdue")
    is_ready_for_production: Optional[bool] = Field(None, description="Whether ready for production")
    
    # Related object data (when included)
    product: Optional[Dict[str, Any]] = None
    bom: Optional[Dict[str, Any]] = None
    warehouse: Optional[Dict[str, Any]] = None
    production_order_components: Optional[List[ProductionOrderComponentResponse]] = None
    stock_allocations: Optional[List[StockAllocationResponse]] = None


class ProductionOrderFilters(BaseModel):
    """Schema for production order filtering."""
    status: Optional[ProductionOrderStatus] = Field(None, description="Filter by status")
    product_id: Optional[int] = Field(None, description="Filter by product ID")
    bom_id: Optional[int] = Field(None, description="Filter by BOM ID")
    warehouse_id: Optional[int] = Field(None, description="Filter by warehouse ID")
    priority: Optional[int] = Field(None, ge=1, le=10, description="Filter by priority")
    order_date_from: Optional[date] = Field(None, description="Filter orders from date")
    order_date_to: Optional[date] = Field(None, description="Filter orders to date")
    planned_start_from: Optional[date] = Field(None, description="Filter by planned start from date")
    planned_start_to: Optional[date] = Field(None, description="Filter by planned start to date")
    is_overdue: Optional[bool] = Field(None, description="Filter overdue orders")
    search: Optional[str] = Field(None, description="Search in order number, notes")

    @validator('order_date_to')
    def order_date_to_after_from(cls, v, values):
        """Validate order date range."""
        from_date = values.get('order_date_from')
        if v and from_date and v < from_date:
            raise ValueError('order_date_to must be after or equal to order_date_from')
        return v

    @validator('planned_start_to')
    def planned_start_to_after_from(cls, v, values):
        """Validate planned start date range."""
        from_date = values.get('planned_start_from')
        if v and from_date and v < from_date:
            raise ValueError('planned_start_to must be after or equal to planned_start_from')
        return v


class ProductionComponentList(BaseModel):
    """Schema for production order components list."""
    components: List[ProductionOrderComponentResponse]
    order_id: int
    total_components: int = Field(..., description="Total number of components")
    fully_allocated_count: int = Field(0, description="Number of fully allocated components")
    not_allocated_count: int = Field(0, description="Number of not allocated components")


# Legacy compatibility schemas (for existing code)
class ProductionOrderRequest(ProductionOrderCreate):
    """Legacy alias for ProductionOrderCreate."""
    pass


class ProductionOrder(ProductionOrderResponse):
    """Legacy alias for ProductionOrderResponse."""
    pass


class ProductionCompletion(ProductionOrderCompletion):
    """Legacy alias for ProductionOrderCompletion."""
    pass