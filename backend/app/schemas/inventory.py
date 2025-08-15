"""
Inventory management schemas for stock operations and FIFO allocation.
Defines data structures for inventory items, movements, and allocations.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from pydantic import Field, validator
from app.schemas.base import (
    BaseSchema, TimestampMixin, QualityStatus, MovementType,
    validate_batch_number, validate_positive_decimal, validate_non_negative_decimal
)
from app.schemas.master_data import ProductSummary, SupplierSummary


class WarehouseSummary(BaseSchema):
    """Warehouse summary for relationships."""
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    warehouse_type: str


# Stock operation schemas
class StockInRequest(BaseSchema):
    """Stock in operation request."""
    product_id: int = Field(..., description="Product ID")
    warehouse_id: int = Field(..., description="Warehouse ID")
    quantity: Decimal = Field(..., gt=0, description="Quantity to add")
    unit_cost: Decimal = Field(..., ge=0, description="Cost per unit")
    batch_number: str = Field(..., description="Batch/lot number")
    
    @validator('batch_number')
    def validate_batch_number_field(cls, v):
        return validate_batch_number(v)
    supplier_id: Optional[int] = Field(None, description="Supplier ID (if from purchase)")
    purchase_order_id: Optional[int] = Field(None, description="Purchase order ID")
    quality_status: QualityStatus = Field(QualityStatus.PENDING, description="Quality status")
    expiry_date: Optional[date] = Field(None, description="Product expiry date")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")
    
    @validator('quantity')
    def validate_quantity(cls, v):
        """Validate quantity is positive."""
        return validate_positive_decimal(v, "Quantity")
    
    @validator('unit_cost')
    def validate_unit_cost(cls, v):
        """Validate unit cost is non-negative."""
        return validate_non_negative_decimal(v, "Unit cost")
    
    @validator('expiry_date')
    def validate_expiry_date(cls, v):
        """Validate expiry date is in the future."""
        if v and v <= date.today():
            raise ValueError('Expiry date must be in the future')
        return v


class StockOutRequest(BaseSchema):
    """Stock out operation request."""
    product_id: int = Field(..., description="Product ID")
    warehouse_id: int = Field(..., description="Warehouse ID")
    quantity: Decimal = Field(..., gt=0, description="Quantity to remove")
    reason: str = Field(..., min_length=1, max_length=200, description="Reason for stock out")
    reference_number: Optional[str] = Field(None, max_length=50, description="Reference number")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")
    
    @validator('quantity')
    def validate_quantity(cls, v):
        """Validate quantity is positive."""
        return validate_positive_decimal(v, "Quantity")


class StockAdjustmentRequest(BaseSchema):
    """Stock adjustment operation request."""
    inventory_item_id: int = Field(..., description="Inventory item ID")
    adjustment_quantity: Decimal = Field(..., description="Adjustment quantity (can be negative)")
    reason: str = Field(..., min_length=1, max_length=200, description="Reason for adjustment")
    reference_number: Optional[str] = Field(None, max_length=50, description="Reference number")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")


class StockTransferRequest(BaseSchema):
    """Stock transfer between warehouses request."""
    product_id: int = Field(..., description="Product ID")
    from_warehouse_id: int = Field(..., description="Source warehouse ID")
    to_warehouse_id: int = Field(..., description="Destination warehouse ID")
    quantity: Decimal = Field(..., gt=0, description="Quantity to transfer")
    reason: Optional[str] = Field(None, max_length=200, description="Transfer reason")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")
    
    @validator('quantity')
    def validate_quantity(cls, v):
        """Validate quantity is positive."""
        return validate_positive_decimal(v, "Quantity")
    
    @validator('to_warehouse_id')
    def validate_different_warehouses(cls, v, values):
        """Validate source and destination warehouses are different."""
        if 'from_warehouse_id' in values and v == values['from_warehouse_id']:
            raise ValueError('Source and destination warehouses must be different')
        return v


# Inventory item schemas
class InventoryItemBase(BaseSchema):
    """Base inventory item schema."""
    product_id: int
    warehouse_id: int
    batch_number: str
    quantity_in_stock: Decimal = Field(..., ge=0)
    reserved_quantity: Decimal = Field(0, ge=0)
    unit_cost: Decimal = Field(..., ge=0)
    quality_status: QualityStatus
    expiry_date: Optional[date] = None
    supplier_id: Optional[int] = None
    purchase_order_id: Optional[int] = None
    notes: Optional[str] = None


class InventoryItem(InventoryItemBase, TimestampMixin):
    """Full inventory item information."""
    inventory_item_id: int
    entry_date: datetime
    
    # Computed properties
    @property
    def available_quantity(self) -> Decimal:
        """Calculate available quantity (stock - reserved)."""
        try:
            quantity = Decimal(str(self.quantity_in_stock or 0))
            reserved = Decimal(str(self.reserved_quantity or 0))
            return quantity - reserved
        except (TypeError, ValueError):
            return Decimal('0')
    
    @property
    def total_value(self) -> Decimal:
        """Calculate total inventory value."""
        try:
            quantity = Decimal(str(self.quantity_in_stock or 0))
            cost = Decimal(str(self.unit_cost or 0))
            return quantity * cost
        except (TypeError, ValueError):
            return Decimal('0')
    
    @property
    def is_expired(self) -> bool:
        """Check if item is expired."""
        return self.expiry_date is not None and self.expiry_date <= date.today()
    
    @property
    def days_until_expiry(self) -> Optional[int]:
        """Calculate days until expiry."""
        if self.expiry_date is None:
            return None
        delta = self.expiry_date - date.today()
        return delta.days


class InventoryItemDetail(InventoryItem):
    """Inventory item with related information."""
    product: ProductSummary
    warehouse: "WarehouseSummary"
    supplier: Optional[SupplierSummary] = None


class InventoryItemList(BaseSchema):
    """Inventory item list response."""
    items: List[InventoryItemDetail]
    total_count: int


# Stock movement schemas
class StockMovement(TimestampMixin):
    """Stock movement record."""
    stock_movement_id: int
    inventory_item_id: int
    movement_type: MovementType
    quantity: Decimal = Field(...)
    movement_date: datetime
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None


class StockMovementDetail(StockMovement):
    """Stock movement with related information."""
    inventory_item: InventoryItemDetail


class StockMovementList(BaseSchema):
    """Stock movement list response."""
    movements: List[StockMovementDetail]
    total_count: int


# Stock allocation schemas
class StockAllocationRequest(BaseSchema):
    """Stock allocation request."""
    product_id: int = Field(..., description="Product ID")
    warehouse_id: int = Field(..., description="Warehouse ID")
    quantity: Decimal = Field(..., gt=0, description="Quantity to allocate")
    production_order_id: Optional[int] = Field(None, description="Production order ID")
    reference_type: Optional[str] = Field(None, max_length=50, description="Reference type")
    reference_id: Optional[int] = Field(None, description="Reference ID")
    notes: Optional[str] = Field(None, max_length=500, description="Allocation notes")
    
    @validator('quantity')
    def validate_quantity(cls, v):
        """Validate quantity is positive."""
        return validate_positive_decimal(v, "Quantity")


class StockAllocation(TimestampMixin):
    """Stock allocation record."""
    stock_allocation_id: int
    production_order_id: Optional[int] = None
    inventory_item_id: int
    allocated_quantity: Decimal = Field(...)
    consumed_quantity: Decimal = Field(0)
    allocation_date: datetime
    consumption_date: Optional[datetime] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    notes: Optional[str] = None
    
    @property
    def remaining_quantity(self) -> Decimal:
        """Calculate remaining allocated quantity."""
        return self.allocated_quantity - self.consumed_quantity


class StockAllocationDetail(StockAllocation):
    """Stock allocation with related information."""
    inventory_item: InventoryItemDetail


class StockAllocationList(BaseSchema):
    """Stock allocation list response."""
    allocations: List[StockAllocationDetail]
    total_count: int


# Availability and FIFO schemas
class InventoryAvailability(BaseSchema):
    """Inventory availability summary."""
    product_id: int
    warehouse_id: Optional[int] = None
    total_in_stock: Decimal = Field(..., ge=0)
    total_reserved: Decimal = Field(..., ge=0)
    total_available: Decimal = Field(..., ge=0)
    weighted_average_cost: Decimal = Field(..., ge=0)
    oldest_batch_date: Optional[datetime] = None
    newest_batch_date: Optional[datetime] = None
    expired_quantity: Decimal = Field(0, ge=0)
    batches: List[InventoryItem] = []


class FIFOAllocationItem(BaseSchema):
    """FIFO allocation breakdown item."""
    inventory_item_id: int
    batch_number: str
    allocated_quantity: Decimal = Field(...)
    unit_cost: Decimal = Field(...)
    total_cost: Decimal = Field(...)
    entry_date: datetime


class FIFOAllocationResult(BaseSchema):
    """FIFO allocation result."""
    product_id: int
    warehouse_id: int
    requested_quantity: Decimal = Field(...)
    allocated_quantity: Decimal = Field(...)
    shortage_quantity: Decimal = Field(...)
    weighted_average_cost: Decimal = Field(...)
    total_cost: Decimal = Field(...)
    allocations: List[FIFOAllocationItem]


# Response schemas
class StockOperationResponse(BaseSchema):
    """Stock operation response."""
    operation_id: int
    message: str
    affected_items: List[int] = []
    movements_created: int = 0


class InventoryValuation(BaseSchema):
    """Inventory valuation summary."""
    product_id: int
    warehouse_id: Optional[int] = None
    total_quantity: Decimal = Field(...)
    total_value: Decimal = Field(...)
    average_cost: Decimal = Field(...)
    fifo_cost: Decimal = Field(...)
    cost_variance: Decimal = Field(...)


class CriticalStockItem(BaseSchema):
    """Critical stock item."""
    product_id: int
    product_code: str
    product_name: str
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    current_stock: Decimal = Field(...)
    critical_level: Decimal = Field(...)
    shortage: Decimal = Field(...)
    last_movement_date: Optional[datetime] = None
    suggested_reorder_quantity: Optional[Decimal] = Field(None)


class CriticalStockReport(BaseSchema):
    """Critical stock report."""
    items: List[CriticalStockItem]
    total_items: int
    report_date: datetime = Field(default_factory=datetime.now)